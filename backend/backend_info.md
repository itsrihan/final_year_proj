# Backend Info

This file merges the important parts of the backend documentation into one brief guide for both humans and AI.

## What the backend does
- Receives webcam frames from the frontend over WebSocket.
- Extracts MediaPipe hands, pose, and face landmarks.
- Converts landmarks into fixed-length feature vectors.
- Runs the phrase LSTM model through `PhrasePredictor`.
- Returns the predicted sign plus confidence and telemetry.

## Main runtime flow
1. Frontend captures a camera frame and sends it as base64 over `/ws/asl`.
2. `main.py` decodes the image, flips it, and passes it into `LandmarkExtractor`.
3. `LandmarkExtractor.extract_features()` builds a normalized feature vector.
4. `PhrasePredictor.predict()` runs the TensorFlow model with a rolling frame buffer.
5. The backend returns JSON with the prediction result and debug metadata.

## Key files
- `main.py` - FastAPI app, CORS, health route, and ASL WebSocket.
- `core/config.py` - central paths and feature constants.
- `core/landmarks.py` - MediaPipe bundle creation and feature extraction.
- `predictor_assets.py` - loads or rebuilds the model and labels.
- `predictor_engine.py` - predictor state machine, voting, and hold logic.
- `predictor_state.py` - state enum used by the engine.
- `debug/debug.py` - local webcam debugging viewer.

## Model / feature summary
- `FRAMES` is the prediction window length, currently 35.
- `FEATURES_PER_FRAME` is the combined hand, pose, and face feature length.
- Hand-feature post-processing: `HAND_SMOOTH_ALPHA` and `HAND_MAX_INTERP_FRAMES` are configurable in `core/config.py` and used by `LandmarkExtractor` and the predictor's feature path so smoothing/interpolation is consistent.
- The predictor stores a rolling sequence and only predicts once enough frames exist.
- The engine uses vote windows, confidence thresholds, and HOLD behavior to reduce flicker.
- The engine can fall back to CPU if the TensorFlow GPU backend errors.
 - If the on-disk model or label artifacts are missing, or if the model fails to warm with the expected input shape `(1, FRAMES, FEATURES_PER_FRAME)`, the backend will rebuild/train a model. Make sure `backend/models/phrase_lstm.keras` and `backend/models/phrase_labels.json` are present and match `FRAMES` to avoid accidental retraining.

## Current routes
- `GET /` - health check, returns a simple message.
- `WebSocket /ws/asl` - receives frames and returns ASL predictions.

## Current backend behavior updates
- CORS is environment-driven through `CORS_ALLOW_ORIGINS`.
- If the environment variable is missing, localhost origins are used as fallback.
- WebSocket prediction is run in a thread pool so the socket stays responsive.
- The backend still only handles ASL camera streaming; speech transcription is not implemented here yet.

## Important output fields
The WebSocket response includes:
- `text`
- `confidence`
- `status`
- `model_name`
- `hands_detected`
- `hands_count`
- `predictor_ready`
- `predictor_error`
- `inference_device`
- `inference_mode`

## Practical notes
- Keep `main.py` focused on request handling and transport.
- Keep model logic in the predictor files.
- Keep MediaPipe extraction in `core/landmarks.py`.
- For debugging, use `debug/debug.py` to inspect the same predictor stack without the frontend.
- If prediction flickers, adjust voting or hold values in `predictor_engine.py`.

## Short version
This backend is a FastAPI ASL inference service: it accepts frames, extracts landmarks, runs the LSTM model, applies stability logic, and returns structured JSON for the frontend.
