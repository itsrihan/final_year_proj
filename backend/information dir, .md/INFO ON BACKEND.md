# Backend Structure Guide

This document explains the backend folder and details the current implementation so humans and automation can reason about it.

Core idea (runtime flow):

1. A video frame is captured from a webcam (debug) or streamed from the frontend (WebSocket).
2. MediaPipe produces hand, pose, and face landmarks.
3. Landmarks are normalized and concatenated into a fixed-size per-frame feature vector.
4. The predictor buffers a short sequence of frames and runs a TensorFlow LSTM classifier.
5. The backend returns a label, confidence, and lightweight telemetry to the client.

## High-Level Folder Map

```text
backend/
|-- main.py
|-- predictor.py
|-- predictor_assets.py
|-- predictor_engine.py
|-- predictor_state.py
|-- requirements.txt
|-- core/
|   |-- config.py
|   |-- drawing.py
|   `-- landmarks.py
|-- debug/
|   `-- debug.py
|-- models/
|   |-- phrase_labels.json
|   |-- phrase_lstm.keras
`-- venv/
```

## Top-Level Files (quick)

- `main.py` — Production entry: FastAPI app with a health route `/` and WebSocket `/ws/asl`. It decodes base64 frames, flips them for a mirrored UX, runs MediaPipe via the shared extractor, and forwards a `MediaPipeBundle` into the predictor. Predictions are executed in a thread pool so the WebSocket stays responsive.

- `predictor.py` — Thin public facade that re-exports `PhrasePredictor` and the asset loader for stable imports.

- `predictor_assets.py` — Loads or (if necessary) rebuilds the Keras model and the label map. It will:
  - Check for the model and label JSON artifacts.
  - Try to load the saved model, warming it up with a dummy input.
  - If artifacts are missing or not-loadable, build and train a small LSTM model from `.npy` sequences in `data/phrases/`, save the model, and write `phrase_labels.json`.
  - Configure GPU memory growth when a GPU is present and log whether a GPU was found.

- `predictor_engine.py` — The inference engine: `PhrasePredictor` implements a state machine, rolling sequence buffer, raw inference wrapper (with tf.function + CPU fallback), short-window voting, and hold/reentry rules to produce stable labels.

- `predictor_state.py` — Enum for engine states (now includes `HOLD` in addition to `IDLE`, `REENTRY`, `SIGNING`, `CONFIRMED`).

- `debug/debug.py` — Local webcam visualizer that uses the same extractor and predictor, draws overlays with `core/drawing`, and exposes interactive keys (reset, toggle layers, quit).

- `core/` — Shared utilities: landmark extraction, normalization, drawing helpers, and centralized paths/constants in `config.py`.

## Core module details

### `core/config.py`

- `FRAMES = 24` — inference window length (default).
- `THRESHOLD = 0.60` — stability threshold used by the engine as a baseline.
- Landmark subsets: `POSE_LANDMARKS` and `FACE_LANDMARKS` select compact sets used for pose/face context.
- `FEATURES_PER_FRAME` is computed from hand (two hands × 21 landmarks × 3), selected pose landmarks (x,y,z,visibility) and selected face landmarks (x,y,z). With the current subsets the per-frame length is 195.
- Canonical paths: `PHRASE_MODEL_PATH`, `PHRASE_LABELS_PATH`, `PHRASE_DATA_DIR` point to `backend/models` and `data/phrases`.

### `core/landmarks.py`

- `MediaPipeBundle` groups `hands_results`, `pose_results`, and `face_results` returned by MediaPipe.
- `LandmarkExtractor` initializes MediaPipe Hands, Pose, and FaceMesh and exposes:
  - `process_frame(frame_bgr)` → `MediaPipeBundle` (handles BGR→RGB conversion and correct flags).
  - `extract_features(mp_bundle)` → 1D NumPy array of length `FEATURES_PER_FRAME`.
- Normalization: anchor = midpoint of left/right shoulders; scale = shoulder width. Coordinates are normalized by `(xyz - anchor) / scale`. If pose landmarks are missing, zero-padding is used.
- Extractors return zero-padding when hands/pose/face are absent so feature length is stable.
- The code raises a `RuntimeError` if the produced feature vector does not match `FEATURES_PER_FRAME`.

### `core/drawing.py`

- Pure visualization helpers used by `debug/debug.py`:
  - `draw_hands`, `draw_pose_subset`, `draw_face_subset`, `draw_debug_text`.
- Used only for developer/debug display; it does not affect prediction math.

## Prediction pipeline (detailed)

1. Frame input
   - Production: frontend encodes camera frames as base64 and sends them over the WebSocket `/ws/asl`.
   - Debug: `debug/debug.py` reads from the local webcam.

2. Decoding & preprocessing
   - `main.py` decodes the base64 payload, flips frames horizontally, and then calls `extractor.process_frame(frame)` to obtain landmarks.
   - Important: `main.py` always calls `extractor.process_frame(...)` — even if hands are not detected — to ensure the pipeline behaviors and telemetry remain consistent.

3. Feature extraction
   - `LandmarkExtractor.extract_features(mp_bundle)` returns a fixed-length float32 vector (expected `FEATURES_PER_FRAME`, currently 195).

4. Sequence buffering
   - `PhrasePredictor.sequence` holds a rolling list of recent per-frame features (truncated to the most recent `FRAMES` entries).
   - `_build_input_sequence()` constructs an array of shape `(FRAMES, FEATURES_PER_FRAME)` where real frames occupy the START of the array and zeros are padded to the END (tail-padding). This preserves temporal ordering for the LSTM.

5. Inference
   - `predictor_assets.load_phrase_assets()` loads or trains a model and returns `(model, index_to_label_map)`.
   - `PhrasePredictor` wraps the model in a `tf.function` (`self._predict_fn`) for speed. `_run_inference()` calls this function and records device/mode telemetry.
   - If a CuDNN/GPU RNN backend error occurs, `_run_inference()` detects it and retries the model on CPU (`with tf.device('/CPU:0')`) and sets `inference_mode='cpu-fallback'`.

6. Post-processing & voting
   - The engine keeps a short vote buffer of recent raw `(label, confidence)` outputs and uses `VOTE_WINDOW`, `VOTE_MAJORITY`, and `VOTE_CONFIDENCE_THRESHOLD` to confirm winners.
   - `SECOND_PLACE_MAX` is enforced: if the runner-up mean confidence is too close, the winner is rejected to avoid ambiguous confirmations.
   - A special `NULL_LABEL` (string `'null'`) indicates "no meaningful sign" and causes the engine to clear buffers without producing a confirmed label.

7. State machine & HOLD behavior
   - States: `IDLE`, `REENTRY`, `SIGNING`, `CONFIRMED`, `HOLD`.
   - `HOLD` is used to keep a confirmed label visible for `HOLD_FRAMES` (default tuned value in the engine) so the UI doesn't immediately overwrite it mid-vote. `HOLD` also supports an early exit if hands disappear for `HOLD_EARLY_EXIT_FRAMES`.

8. Output
   - `predict()` returns `(label, confidence)`.
   - `main.py` builds a JSON payload with these fields plus telemetry and predictor readiness/error flags:
     - `text`, `confidence`, `status`, `model_name`, `hands_detected`, `hands_count`, `predictor_ready`, `predictor_error`, `inference_device`, `inference_mode`.

## Models and training

- Saved model: `models/phrase_lstm.keras` (Keras SavedModel format used at runtime).
- Label map: `models/phrase_labels.json` maps label → index. `predictor_assets.py` converts it to index→label for runtime mapping.
- If artifacts are missing or invalid, `predictor_assets.py` will build and train a small LSTM model from `.npy` sequences found under `data/phrases/`. The expected `.npy` arrays are `(FRAMES, FEATURES_PER_FRAME)` per example.

## Debugging and observability

- `debug/debug.py` is the recommended local tool for visual inspection — it prints engine debug info, draws landmarks, and shows the confirmed label and telemetry.
- Logs from `predictor_assets.py` indicate whether a GPU was found and whether the model warmed up successfully.
- `get_last_inference_telemetry()` returns `{'inference_device': ..., 'inference_mode': ...}` which `main.py` includes in WebSocket responses.

## Where to change what

- `main.py`: API / WebSocket framing and how frames are consumed.
- `core/config.py`: `FRAMES`, feature layout and artifact paths.
- `core/landmarks.py`: which landmarks are included and the normalization strategy.
- `predictor_assets.py`: model architecture, training procedure and artifact handling.
- `predictor_engine.py`: state machine tuning, voting thresholds, and hold/reentry logic.
- `debug/debug.py`: visualization and developer checks.

## Short summary

The backend captures frames, builds normalized per-frame feature vectors (tail-padded into `FRAMES` windows), runs a small LSTM classifier (with GPU/CPU fallback), uses short-window voting and a `HOLD` state to stabilize outputs, and returns structured JSON with label, confidence, and telemetry to the frontend or to a local debug viewer.
