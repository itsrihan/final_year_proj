# Predictor Engine — Detailed Explanation

This document explains the implementation details of `predictor_engine.py` and the runtime decisions made by `PhrasePredictor`. It covers inputs/outputs, feature handling, buffering, voting, the state machine (including HOLD behavior), telemetry and device fallbacks, and integration points with the rest of the backend.

Overview / high-level flow
--------------------------

1. A `MediaPipeBundle` (hands, pose, face results) is produced by `core/landmarks.py`.
2. The engine converts that bundle into a fixed-length per-frame vector of size `FEATURES_PER_FRAME`.
3. Feature vectors are appended to `PhrasePredictor.sequence` (rolling buffer limited to `FRAMES`).
4. When enough frames are present, the engine builds an input tensor `(1, FRAMES, FEATURES_PER_FRAME)` and runs the TensorFlow model (via a compiled `tf.function`) to get a probability vector.
5. The engine accumulates short-window raw outputs in a vote buffer and applies heuristics (majority, mean confidence, second-place gap, null filtering) to confirm labels.

Key constants and where to find them
-----------------------------------

- `core/config.py`:
  - `FRAMES` — number of frames for the model window (default 24).
  - `FEATURES_PER_FRAME` — per-frame vector length (computed from selected hand/pose/face subsets).
  - Paths: `PHRASE_MODEL_PATH`, `PHRASE_LABELS_PATH`, `PHRASE_DATA_DIR`.

- `predictor_engine.py` (engine-level tuning / defaults used in code):
  - `MIN_FRAMES_TO_PREDICT = FRAMES` — don't run inference until you have a full window.
  - `PREDICT_EVERY_N = 1` — cadence for running inference.
  - Voting: `VOTE_WINDOW = 6`, `VOTE_MAJORITY = 4`, `VOTE_CONFIDENCE_THRESHOLD = 0.55`, `SECOND_PLACE_MAX = 0.40`.
  - HOLD: `HOLD_FRAMES` (how long to display confirmed label), `HOLD_EARLY_EXIT_FRAMES` (early exit if hands disappear).
  - State transition counters: `IDLE_ENTRY_FRAMES`, `REENTRY_FRAMES_REQUIRED`, `SIGNING_GRACE_FRAMES`, etc.

Inputs and outputs
------------------

- Input to `PhrasePredictor.predict(mp_bundle, hands_detected)`:
  - `mp_bundle`: `MediaPipeBundle` returned by `LandmarkExtractor.process_frame`.
  - `hands_detected`: boolean (True when MediaPipe returns one or more detected hands).

- Output: `(label: str, confidence: float)` — the label to display and its confidence.

- At the server level (`main.py`) the return values are packaged into a JSON payload with telemetry: `text`, `confidence`, `status`, `model_name`, `hands_detected`, `hands_count`, `predictor_ready`, `predictor_error`, `inference_device`, `inference_mode`.

Feature extraction and normalization
-----------------------------------

- `PhrasePredictor` delegates per-frame parsing to `LandmarkExtractor.extract_features(mp_bundle)`.
- The extractor builds an anchor (shoulder midpoint) and a scale (shoulder width) and normalizes 3D coordinates by `(xyz - anchor) / scale` when pose is available; otherwise it zero-pads.
- The final feature vector order is: left-hand landmarks (21 × 3), right-hand landmarks (21 × 3), selected pose landmarks (x,y,z,visibility each), selected face landmarks (x,y,z each). The implementation enforces the final length equals `FEATURES_PER_FRAME` and raises if it does not.

Sequence buffering and input tensor
----------------------------------

- `self.sequence` contains appended per-frame NumPy arrays; it is always truncated to the most recent `FRAMES` elements.
- `_build_input_sequence()` returns a `(FRAMES, FEATURES_PER_FRAME)` array where real frames are placed at the START and zero padding is placed at the END (tail-padding). This ordering preserves temporal locality for the LSTM (real data comes first, padding last).
- If `self.sequence` is empty or malformed, `_build_input_sequence()` returns `None` and no inference is attempted.

Model execution and telemetry
-----------------------------

- The model and label map are obtained via `load_phrase_assets()` from `predictor_assets.py` (model may be loaded or trained on-demand).
- `PhrasePredictor` wraps the model in a `tf.function` bound to the model (`self._predict_fn`) to reduce Python overhead.
- `_run_inference(input_data)` calls the `tf.function`. It records `last_inference_device` and `last_inference_mode` (e.g., `tf-function`).
- If the `tf.function` raises a GPU/CuDNN-related error (checked by `_is_cudnn_backend_error()` which inspects the exception message for markers such as `CudnnRNNV3` or `Dnn is not supported`), the engine retries on CPU inside `with tf.device('/CPU:0')` and records `inference_mode='cpu-fallback'`.
- `_format_device_name()` normalizes the device string so telemetry is concise (e.g., returns `CPU:0`, `GPU:0` when possible).

Raw inference and label selection
---------------------------------

- `_raw_inference()` builds the input sequence, runs `_run_inference()`, then:
  - finds the argmax index,
  - takes the probability at that index as `confidence`,
  - maps index → label (via the loaded `index_to_label` mapping).
- These raw `(label, confidence)` pairs are appended to the short vote buffer for later evaluation.

Voting, confirmation guards and NULL handling
--------------------------------------------

- The engine keeps a short vote history `self._vote_buffer` (windowed to `VOTE_WINDOW` entries).
- `_evaluate_votes()` inspects votes and returns `(winner_label, mean_confidence)` only when:
  - the winner has at least `VOTE_MAJORITY` votes,
  - the winner's mean confidence ≥ `VOTE_CONFIDENCE_THRESHOLD`,
  - the runner-up mean confidence (if any) < `SECOND_PLACE_MAX`.
- If the model outputs the configured `NULL_LABEL` (string `'null'`), the engine treats it as "no meaningful sign": clears sequence/votes and stays in `SIGNING` (so the UI doesn't flash back to Waiting immediately).

State machine and HOLD behavior
-------------------------------

- States: `IDLE`, `REENTRY`, `SIGNING`, `CONFIRMED`, `HOLD`.
- `IDLE`: waits for hands to be present for `IDLE_ENTRY_FRAMES` consecutive frames before moving to `REENTRY`.
- `REENTRY`: collects `REENTRY_FRAMES_REQUIRED` frames to stabilise before entering `SIGNING`.
- `SIGNING`: runs inference on cadence (controlled by `PREDICT_EVERY_N`) and accumulates votes. If a winner passes voting/guards, the engine sets `_confirmed_label` and transitions to `CONFIRMED` and immediately to `HOLD`.
- `HOLD`: the engine keeps returning the confirmed label for `HOLD_FRAMES` frames, preventing rapid re-signing or label overwrites. If the signer removes their hands for `HOLD_EARLY_EXIT_FRAMES`, the engine exits HOLD early and returns to `IDLE` (while returning the last label once so the UI can fade it out).

State reset and recovery
------------------------

- `reset()` clears all counters, buffers, last raw values and returns the engine to `IDLE` state.
- `_clear_for_idle()` is used internally to reset buffers when hands disappear or when an unrecoverable condition occurs.

Debug info and observability
---------------------------

- `get_debug_info()` returns a compact dict with `state`, `sequence_len`, `vote_len`, `confirmed_label`, `confirmed_confidence`, `last_raw_label`, `last_raw_confidence`, `inference_device`, `inference_mode`, and `hold_counter` for use by `debug/debug.py` and logging.
- `main.py` calls `get_last_inference_telemetry()` after predictions and includes `inference_device` and `inference_mode` in the WebSocket response.

Practical tuning guidance (how to adjust behavior)
-------------------------------------------------

- Reduce false positives:
  - increase `VOTE_CONFIDENCE_THRESHOLD` (require higher mean confidence),
  - increase `VOTE_MAJORITY` or `VOTE_WINDOW` so more consistent votes are required.

- Make confirmations faster:
  - reduce `VOTE_WINDOW` or `VOTE_MAJORITY`,
  - lower `MIN_FRAMES_TO_PREDICT` (careful: increases noise).

- Reduce CPU fallbacks:
  - verify TensorFlow / GPU compatibility and drivers, or reduce model complexity in `predictor_assets._build_model()`.

Integration points and responsibilities
--------------------------------------

- `main.py`: prepares frame data, calls `LandmarkExtractor.process_frame()`, and calls `predictor.predict()` inside `run_in_threadpool` to avoid blocking the WebSocket thread.
- `debug/debug.py`: runs the same predictor synchronously and visualizes overlays and telemetry.
- `predictor_assets.py`: supplies the Keras model and index→label mapping used by `PhrasePredictor`.
- `core/landmarks.py`: supplies `MediaPipeBundle` objects and `extract_features()` used by the engine.

Summary
-------

`PhrasePredictor` is a production-focused sequence classifier that wraps a small LSTM, enforces stable per-frame features, applies short-window voting with runner-up guards, uses a `HOLD` state to avoid overwriting confirmed labels too quickly, and records minimal telemetry about where inference ran. The engine includes a GPU-friendly `tf.function` fast path and a CPU fallback when necessary. The debug tool and the production WebSocket share the same engine and extractor code so behaviors are consistent across development and production flows.
