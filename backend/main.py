import base64
import json
import os

import cv2
import numpy as np
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware

from predictor import PhrasePredictor
from predictor_assets import get_phrase_assets_debug_info, load_phrase_assets
from predictor_engine import CaptureStateMachine, ManualCaptureMachine
from core.config import PHRASE_DATA_DIR, PHRASE_LABELS_PATH, PHRASE_MODEL_PATH, FEATURES_PER_FRAME
from core.landmarks import LandmarkExtractor

MODEL_FILE_NAME = os.path.basename(PHRASE_MODEL_PATH)

# Set to True to include annotated landmark data in every response for debugging.
# Keep False for presentation — has no effect on prediction.
DEBUG_LANDMARK_OVERLAY = False

DEFAULT_CORS_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]


def get_allowed_origins():
    raw_origins = os.getenv("CORS_ALLOW_ORIGINS", "").strip()
    if not raw_origins:
        return DEFAULT_CORS_ORIGINS

    cleaned = raw_origins.strip("[]")
    origins = [origin.strip() for origin in cleaned.split(",") if origin.strip()]
    return origins or DEFAULT_CORS_ORIGINS

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_allowed_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root():
    return {"message": "ASL backend running"}


@app.on_event("startup")
def preload_phrase_model():
    print(f"[MODEL] PHRASE_MODEL_PATH={PHRASE_MODEL_PATH}")
    print(f"[MODEL] PHRASE_LABELS_PATH={PHRASE_LABELS_PATH}")
    print(f"[MODEL] model_path_exists={os.path.exists(PHRASE_MODEL_PATH)} labels_path_exists={os.path.exists(PHRASE_LABELS_PATH)}")

    try:
        load_phrase_assets(PHRASE_MODEL_PATH, PHRASE_LABELS_PATH, PHRASE_DATA_DIR)
        print("[MODEL] Phrase model loaded successfully on startup")
    except Exception as error:
        app.state.model_load_error = str(error)
        print(f"[MODEL] Phrase model failed to load on startup: {error}")

    app.state.model_debug_info = get_phrase_assets_debug_info(PHRASE_MODEL_PATH, PHRASE_LABELS_PATH, PHRASE_DATA_DIR)


def _build_model_debug_response():
    debug_info = getattr(app.state, "model_debug_info", None)
    if not debug_info:
        debug_info = get_phrase_assets_debug_info(PHRASE_MODEL_PATH, PHRASE_LABELS_PATH, PHRASE_DATA_DIR)

    return {
        "model_available": bool(debug_info.get("model_available", False)),
        "model_path": debug_info.get("model_path", PHRASE_MODEL_PATH),
        "labels_path": debug_info.get("labels_path", PHRASE_LABELS_PATH),
        "model_path_exists": bool(debug_info.get("model_path_exists", False)),
        "labels_path_exists": bool(debug_info.get("labels_path_exists", False)),
        "model_input_shape": debug_info.get("model_input_shape"),
        "model_output_shape": debug_info.get("model_output_shape"),
        "labels_count": int(debug_info.get("labels_count", 0) or 0),
        "labels": debug_info.get("labels", []),
        "error": debug_info.get("error") or getattr(app.state, "model_load_error", None),
    }


@app.get("/health")
def health():
    return _build_model_debug_response()


@app.get("/debug/model")
def debug_model():
    return _build_model_debug_response()


def decode_base64_image(data_url: str):
    if "," in data_url:
        _, encoded = data_url.split(",", 1)
    else:
        encoded = data_url

    image_bytes = base64.b64decode(encoded)
    np_arr = np.frombuffer(image_bytes, np.uint8)
    frame = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
    return frame


@app.websocket("/ws/asl")
async def asl_socket(websocket: WebSocket):
    await websocket.accept()

    # Initialize variables
    extractor = LandmarkExtractor()
    predictor = None
    predictor_error = None
    capture_machine = None
    manual_machine = None

    try:
        predictor = PhrasePredictor(PHRASE_MODEL_PATH, PHRASE_LABELS_PATH, PHRASE_DATA_DIR)
        label_order = [predictor.index_to_label[index] for index in sorted(predictor.index_to_label)]

        # Create capture machine with inference function
        def predict_fn(frames_array):
            """Wrapper for model prediction."""
            label, confidence = predictor._raw_inference_from_sequence(frames_array)
            return label if label else "No result", confidence

        def manual_predict_fn(frames_array):
            """Return raw probabilities for manual debug logging."""
            return predictor._run_inference(frames_array)

        capture_machine = CaptureStateMachine(predict_fn)
        manual_machine = ManualCaptureMachine(manual_predict_fn, label_order)
        print("[BACKEND] Capture machine initialized")

    except Exception as error:
        predictor_error = str(error)
        print(f"[WARN] Predictor unavailable: {error}")

    try:
        while True:
            raw_message = await websocket.receive_text()
            payload = json.loads(raw_message)

            frame_data = payload.get("frame")
            asl_enabled = payload.get("asl_enabled", True)
            camera_on = payload.get("camera_on", True)
            mode = payload.get("mode", "auto")  # "auto" or "manual"
            manual_command = payload.get("manual_command")  # "start", "cancel", or None

            print(
                "[ASL] camera_on=",
                camera_on,
                "frame_present=",
                bool(frame_data),
                "mode=",
                mode,
                "manual_command=",
                manual_command,
            )

            # Handle camera-off: hard reset both capture machines
            if not camera_on or frame_data is None:
                if capture_machine is not None:
                    capture_machine.reset()
                if manual_machine is not None:
                    manual_machine.reset()
                response = {
                    "text": "Waiting...",
                    "confidence": 0.0,
                    "status": "Camera off" if not camera_on else "No frame",
                    "model_name": MODEL_FILE_NAME,
                    "capture_mode": mode,
                    "asl_capture_state": "ready",
                    "manual_capture_state": "manual_ready",
                    "captured_frames": 0,
                    "required_frames": 35,
                    "hands_detected": False,
                    "hand_debounce_frames": 0,
                }
                await websocket.send_text(json.dumps(response))
                continue

            if not frame_data:
                response = {
                    "text": "No frame received",
                    "confidence": 0.0,
                    "status": "idle",
                    "model_name": MODEL_FILE_NAME,
                    "capture_mode": mode,
                    "asl_capture_state": "error",
                    "manual_capture_state": "manual_ready",
                    "captured_frames": 0,
                    "required_frames": 35,
                    "hands_detected": False,
                    "hand_debounce_frames": 0,
                }
                await websocket.send_text(json.dumps(response))
                continue

            frame = decode_base64_image(frame_data)

            if frame is None:
                response = {
                    "text": "Invalid frame",
                    "confidence": 0.0,
                    "status": "error",
                    "model_name": MODEL_FILE_NAME,
                    "capture_mode": mode,
                    "asl_capture_state": "error",
                    "manual_capture_state": "manual_ready",
                    "captured_frames": 0,
                    "required_frames": 35,
                    "hands_detected": False,
                    "hand_debounce_frames": 0,
                }
                await websocket.send_text(json.dumps(response))
                continue

            frame = cv2.flip(frame, 1)
            mp_bundle = extractor.process_frame(frame)
            features = extractor.extract_features(mp_bundle)
            
            hands_detected = bool(
                mp_bundle.hands_results
                and mp_bundle.hands_results.multi_hand_landmarks
            )
            hands_count = (
                len(mp_bundle.hands_results.multi_hand_landmarks)
                if hands_detected
                else 0
            )

            # Validate feature shape
            if len(features) != FEATURES_PER_FRAME:
                print(f"[WARN] Feature shape mismatch: {len(features)} vs expected {FEATURES_PER_FRAME}")

            # Route to appropriate capture machine based on mode
            if mode == "manual":
                # Manual mode: user-controlled capture
                if manual_machine is None:
                    detected_text = predictor_error or "Model unavailable"
                    confidence = 0.0
                    status = predictor_error or "Model unavailable"
                    inference_device = "unavailable"
                    inference_mode = "manual-unavailable"
                    manual_capture_state = "manual_ready"
                    captured_frames = 0
                    required_frames = 45
                    hand_debounce_frames = 0
                    prediction = ""
                else:
                    # Process frame through manual capture machine
                    manual_state_dict = await run_in_threadpool(
                        manual_machine.process_frame,
                        features,
                        hands_detected,
                        manual_command
                    )
                    
                    manual_capture_state = manual_state_dict.get('manual_capture_state', 'manual_ready')
                    detected_text = manual_state_dict.get('prediction', '')
                    confidence = manual_state_dict.get('confidence', 0.0)
                    captured_frames = manual_state_dict.get('captured_frames', 0)
                    required_frames = manual_state_dict.get('required_frames', 45)
                    hand_debounce_frames = 0  # No debounce in manual mode
                    
                    if manual_capture_state == 'manual_ready':
                        if not detected_text:
                            detected_text = 'Waiting...'
                        status = "Manual | ready"
                    elif manual_capture_state == 'manual_capturing':
                        detected_text = 'Capturing...'
                        status = f"Manual | capturing {captured_frames}/{required_frames}"
                    elif manual_capture_state == 'manual_result':
                        status = f"Manual | result (press R to capture again)"
                    else:
                        detected_text = 'Waiting...'
                        status = "Manual | idle"
                    
                    inference_device = "gpu"
                    inference_mode = "manual"

                asl_capture_state = "manual"  # Different from auto mode
            else:
                # Auto mode: hand-triggered capture (existing behavior)
                if not asl_enabled:
                    detected_text = "ASL off"
                    confidence = 0.0
                    status = "ASL off"
                    inference_device = "idle"
                    inference_mode = "asl-off"
                    capture_state_dict = {
                        'asl_capture_state': 'off',
                        'captured_frames': 0,
                        'required_frames': 45,
                        'hand_debounce_frames': 0,
                        'prediction': '',
                        'confidence': 0.0,
                    }
                    manual_capture_state = "manual_ready"
                elif capture_machine is None:
                    detected_text = predictor_error or "Model unavailable"
                    confidence = 0.0
                    status = predictor_error or "Model unavailable"
                    inference_device = "unavailable"
                    inference_mode = "predictor-unavailable"
                    capture_state_dict = {
                        'asl_capture_state': 'error',
                        'captured_frames': 0,
                        'required_frames': 45,
                        'hand_debounce_frames': 0,
                        'prediction': '',
                        'confidence': 0.0,
                    }
                    manual_capture_state = "manual_ready"
                else:
                    # Process frame through auto capture state machine
                    capture_state_dict = await run_in_threadpool(
                        capture_machine.process_frame,
                        features,
                        hands_detected
                    )
                    
                    # Map capture state to UI text
                    cap_state = capture_state_dict.get('asl_capture_state', 'ready')
                    detected_text = capture_state_dict.get('prediction', 'Waiting...')
                    confidence = capture_state_dict.get('confidence', 0.0)
                    
                    if cap_state == 'ready':
                        if detected_text == '':
                            detected_text = 'Waiting...'
                        status = "ASL on | ready"
                    elif cap_state == 'capturing':
                        detected_text = 'Translating...'
                        status = f"ASL on | capturing {capture_state_dict.get('captured_frames', 0)}/{capture_state_dict.get('required_frames', 35)}"
                    elif cap_state == 'predicting':
                        detected_text = 'Processing...'
                        status = "ASL on | predicting"
                    elif cap_state == 'wait_for_release':
                        # Keep showing the prediction while waiting for the signer to release
                        status = "ASL on | wait_for_release (release hand to repeat)"
                    else:
                        detected_text = 'Waiting...'
                        status = "ASL on | idle"
                    
                    inference_device = "gpu" if capture_machine is not None else "cpu"
                    inference_mode = cap_state
                    manual_capture_state = "manual_ready"

                asl_capture_state = capture_state_dict.get('asl_capture_state', 'off')

            # Build full response
            response = {
                "text": detected_text,
                "confidence": round(confidence, 4),  # <-- ONLY ONE
                "status": status,
                "model_name": MODEL_FILE_NAME,
                "capture_mode": mode,
                "asl_capture_state": asl_capture_state if mode == "auto" else "manual",
                "manual_capture_state": manual_capture_state,
                "hands_detected": hands_detected,
                "hands_count": hands_count,
                "predictor_ready": (capture_machine if mode == "auto" else manual_machine) is not None,
                "predictor_error": predictor_error,
                "inference_device": inference_device,
                "inference_mode": inference_mode,
                "captured_frames": captured_frames if mode == "manual" else capture_state_dict.get('captured_frames', 0),
                "required_frames": 45,
                "hand_debounce_frames": hand_debounce_frames if mode == "manual" else capture_state_dict.get('hand_debounce_frames', 0),
            }

            await websocket.send_text(json.dumps(response))

    except WebSocketDisconnect:
        print("Client disconnected")
    except Exception as e:
        print(f"[ERROR] WebSocket exception: {e}")
        try:
            await websocket.send_text(json.dumps({
                "text": "Server error",
                "confidence": 0.0,
                "status": str(e),
                "asl_capture_state": "error",
            }))
        except Exception:
            pass
    finally:
        extractor.close()
        if predictor is not None:
            predictor.close()