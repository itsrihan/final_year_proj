import base64
import json
import os

import cv2
import numpy as np
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware

from predictor import PhrasePredictor
from core.config import PHRASE_DATA_DIR, PHRASE_LABELS_PATH, PHRASE_MODEL_PATH
from core.landmarks import LandmarkExtractor

MODEL_FILE_NAME = os.path.basename(PHRASE_MODEL_PATH)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def root():
    return {"message": "ASL backend running"}


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

    extractor = LandmarkExtractor()
    predictor = None
    predictor_error = None

    try:
        predictor = PhrasePredictor(
            PHRASE_MODEL_PATH,
            PHRASE_LABELS_PATH,
            PHRASE_DATA_DIR,
        )
    except Exception as error:
        predictor_error = str(error)
        print(f"[WARN] Predictor unavailable: {predictor_error}")

    try:
        while True:
            raw_message = await websocket.receive_text()
            payload = json.loads(raw_message)

            frame_data = payload.get("frame")
            asl_enabled = payload.get("asl_enabled", True)

            if not frame_data:
                await websocket.send_text(json.dumps({
                    "text": "No frame received",
                    "confidence": 0.0,
                    "status": "idle",
                    "model_name": MODEL_FILE_NAME,
                }))
                continue

            frame = decode_base64_image(frame_data)

            if frame is None:
                await websocket.send_text(json.dumps({
                    "text": "Invalid frame",
                    "confidence": 0.0,
                    "status": "error",
                    "model_name": MODEL_FILE_NAME,
                }))
                continue

            frame = cv2.flip(frame, 1)
            
            # Always process frame — always use MediaPipe result (Bug 1 fix)
            mp_bundle = extractor.process_frame(frame)
            hands_count = (
                len(mp_bundle.hands_results.multi_hand_landmarks)
                if (
                    mp_bundle.hands_results
                    and mp_bundle.hands_results.multi_hand_landmarks
                )
                else 0
            )
            hands_detected = bool(
                mp_bundle.hands_results
                and mp_bundle.hands_results.multi_hand_landmarks
            )

            if not asl_enabled:
                detected_text = "ASL off"
                confidence = 0.0
                status = "ASL off"
                inference_device = "idle"
                inference_mode = "asl-off"
            elif predictor is None:
                detected_text = "Model unavailable"
                confidence = 0.0
                if hands_detected:
                    status = "ASL on | hand detected | predictor unavailable"
                else:
                    status = "ASL on | no hand | predictor unavailable"
                inference_device = "unavailable"
                inference_mode = "predictor-unavailable"
            else:
                # Run prediction in thread pool to avoid blocking WebSocket (Fix 2)
                detected_text, confidence = await run_in_threadpool(
                    predictor.predict,
                    mp_bundle,
                    hands_detected
                )
                telemetry = predictor.get_last_inference_telemetry()
                inference_device = telemetry.get("inference_device", "unknown")
                inference_mode = telemetry.get("inference_mode", "unknown")

                if hands_detected:
                    status = "ASL on | hand detected"
                else:
                    status = "ASL on | no hand"

            await websocket.send_text(json.dumps({
                "text": detected_text,
                "confidence": round(confidence, 4),
                "status": status,
                "model_name": MODEL_FILE_NAME,
                "hands_detected": hands_detected,
                "hands_count": hands_count,
                "predictor_ready": predictor is not None,
                "predictor_error": predictor_error,
                "inference_device": inference_device,
                "inference_mode": inference_mode,
            }))

    except WebSocketDisconnect:
        print("Client disconnected")
    except Exception as e:
        try:
            await websocket.send_text(json.dumps({
                "text": "Server error",
                "confidence": 0.0,
                "status": str(e)
            }))
        except Exception:
            pass
    finally:
        extractor.close()
        if predictor is not None:
            predictor.close()