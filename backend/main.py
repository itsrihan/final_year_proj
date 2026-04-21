import base64
import json

import cv2
import numpy as np
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from predictor import PhrasePredictor
from core.landmarks import LandmarkExtractor

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

MODEL_PATH = "models/phrase_lstm.keras"
LABELS_PATH = "models/phrase_labels.json"
DATA_PATH = "data/phrases"


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
    predictor = PhrasePredictor(MODEL_PATH, LABELS_PATH, DATA_PATH)

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
                    "status": "idle"
                }))
                continue

            frame = decode_base64_image(frame_data)

            if frame is None:
                await websocket.send_text(json.dumps({
                    "text": "Invalid frame",
                    "confidence": 0.0,
                    "status": "error"
                }))
                continue

            frame = cv2.flip(frame, 1)
            mp_bundle = extractor.process_frame(frame)

            hands_detected = bool(
                mp_bundle.hands_results
                and mp_bundle.hands_results.multi_hand_landmarks
            )

            if not asl_enabled:
                detected_text = "ASL off"
                confidence = 0.0
                status = "ASL off"
            else:
                detected_text, confidence = predictor.predict(
                    mp_bundle,
                    hands_detected=hands_detected
                )

                if hands_detected:
                    status = "ASL on | hand detected"
                else:
                    status = "ASL on | no hand"

            await websocket.send_text(json.dumps({
                "text": detected_text,
                "confidence": round(confidence, 4),
                "status": status,
                "hands_detected": hands_detected
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
        predictor.close()