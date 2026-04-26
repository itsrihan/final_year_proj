import json
import os
from collections import Counter
from enum import Enum, auto
from functools import lru_cache

import numpy as np
import tensorflow as tf
from tensorflow import keras
from tensorflow.keras.models import load_model

from core.config import (
    FEATURES_PER_FRAME,
    FRAMES,
    PHRASE_DATA_DIR,
    PHRASE_LABELS_PATH,
    PHRASE_MODEL_PATH,
    THRESHOLD,
)
from core.landmarks import MediaPipeBundle

# GPU Configuration
gpus = tf.config.list_physical_devices('GPU')
if gpus:
    tf.config.experimental.set_memory_growth(gpus[0], True)
    print(f"[INFO] Using GPU: {gpus[0]}")
else:
    print("[WARN] No GPU found, falling back to CPU")


def _is_cudnn_backend_error(error):
    message = str(error)
    return "CudnnRNNV3" in message or "Dnn is not supported" in message


def _format_device_name(device_name):
    if not device_name:
        return "unknown"
    marker = "/device/"
    index = device_name.lower().find(marker)
    if index >= 0:
        return device_name[index + len(marker):].upper()
    return device_name.upper()


def _is_valid_artifact(path):
    return os.path.exists(path) and os.path.getsize(path) > 0


def _load_label_map(labels_path):
    if not _is_valid_artifact(labels_path):
        return None
    try:
        with open(labels_path, "r", encoding="utf-8") as f:
            label_map = json.load(f)
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(label_map, dict) or not label_map:
        return None
    return {str(label): int(index) for label, index in label_map.items()}


def _normalize_sequence(sequence):
    array = np.asarray(sequence, dtype=np.float32)
    if array.ndim != 2:
        return None
    normalized = np.zeros((FRAMES, FEATURES_PER_FRAME), dtype=np.float32)
    frame_count = min(array.shape[0], FRAMES)
    feature_count = min(array.shape[1], FEATURES_PER_FRAME)
    normalized[:frame_count, :feature_count] = array[:frame_count, :feature_count]
    return normalized


def _load_training_data(data_dir):
    sequences, labels = [], []
    if not os.path.isdir(data_dir):
        return (
            np.empty((0, FRAMES, FEATURES_PER_FRAME), dtype=np.float32),
            np.empty((0,), dtype=np.int32),
            [],
        )
    for phrase_name in sorted(os.listdir(data_dir)):
        phrase_dir = os.path.join(data_dir, phrase_name)
        if not os.path.isdir(phrase_dir):
            continue
        phrase_files = sorted(
            [f for f in os.listdir(phrase_dir) if f.endswith(".npy")],
            key=lambda f: int(os.path.splitext(f)[0]) if os.path.splitext(f)[0].isdigit() else f,
        )
        for file_name in phrase_files:
            file_path = os.path.join(phrase_dir, file_name)
            try:
                sequence = np.load(file_path, allow_pickle=False)
            except Exception:
                continue
            normalized = _normalize_sequence(sequence)
            if normalized is None:
                continue
            sequences.append(normalized)
            labels.append(phrase_name)
    if not sequences:
        return (
            np.empty((0, FRAMES, FEATURES_PER_FRAME), dtype=np.float32),
            np.empty((0,), dtype=np.int32),
            [],
        )
    label_names = sorted(set(labels))
    label_to_index = {label: i for i, label in enumerate(label_names)}
    x_values = np.asarray(sequences, dtype=np.float32)
    y_values = np.array([label_to_index[l] for l in labels], dtype=np.int32)
    return x_values, y_values, label_names


def _build_model(num_classes):
    model = keras.Sequential([
        keras.layers.Input(shape=(FRAMES, FEATURES_PER_FRAME)),
        keras.layers.Masking(mask_value=0.0),
        keras.layers.LSTM(64, return_sequences=False),
        keras.layers.Dense(32, activation="relu"),
        keras.layers.Dropout(0.2),
        keras.layers.Dense(num_classes, activation="softmax"),
    ])
    model.compile(
        optimizer="adam",
        loss="sparse_categorical_crossentropy",
        metrics=["accuracy"],
    )
    return model


def _save_label_map(labels_path, label_names):
    labels_dir = os.path.dirname(labels_path)
    if labels_dir:
        os.makedirs(labels_dir, exist_ok=True)
    label_map = {label: i for i, label in enumerate(label_names)}
    with open(labels_path, "w", encoding="utf-8") as f:
        json.dump(label_map, f, indent=2)
    return label_map


def _train_phrase_model(model_path, labels_path, data_dir):
    x_values, y_values, label_names = _load_training_data(data_dir)
    if x_values.size == 0 or y_values.size == 0 or not label_names:
        raise RuntimeError(
            "No valid phrase training data found in data/phrases. "
            "Each class folder must contain .npy sequences shaped like (frames, 195)."
        )
    model = _build_model(len(label_names))
    callbacks = [keras.callbacks.EarlyStopping(monitor="val_loss", patience=5, restore_best_weights=True)]
    validation_split = 0.2 if len(x_values) >= 10 else 0.0
    model.fit(
        x_values, y_values,
        epochs=25, batch_size=8,
        validation_split=validation_split,
        verbose=1,
        callbacks=callbacks if validation_split > 0 else None,
        shuffle=True,
    )
    model_dir = os.path.dirname(model_path)
    if model_dir:
        os.makedirs(model_dir, exist_ok=True)
    model.save(model_path)
    _save_label_map(labels_path, label_names)
    return model, {i: label for i, label in enumerate(label_names)}


def _try_load_model(model_path):
    try:
        return load_model(model_path, compile=False)
    except Exception as first_error:
        try:
            return tf.keras.models.load_model(model_path, compile=False)
        except Exception:
            raise RuntimeError(str(first_error))


@lru_cache(maxsize=1)
def load_phrase_assets(
    model_path=PHRASE_MODEL_PATH,
    labels_path=PHRASE_LABELS_PATH,
    data_dir=PHRASE_DATA_DIR,
):
    label_map = _load_label_map(labels_path)
    if _is_valid_artifact(model_path) and label_map:
        try:
            model = _try_load_model(model_path)
            dummy = np.zeros((1, FRAMES, FEATURES_PER_FRAME), dtype=np.float32)
            model(dummy, training=False)
            print("[INFO] Model warmed up")
            return model, {index: label for label, index in label_map.items()}
        except Exception as e:
            print(f"[WARN] Existing model could not be loaded: {e}")
            print("[INFO] Rebuilding model from local phrase data...")
    else:
        print("[INFO] Existing model or labels missing. Training a fresh model...")

    model, label_index_map = _train_phrase_model(model_path, labels_path, data_dir)
    dummy = np.zeros((1, FRAMES, FEATURES_PER_FRAME), dtype=np.float32)
    model(dummy, training=False)
    print("[INFO] Model warmed up")
    return model, label_index_map


class _State(Enum):
    IDLE      = auto()   # No hands, no recent prediction
    REENTRY   = auto()   # Hands appeared — absorbing sign tail / debouncing
    SIGNING   = auto()   # Actively collecting frames for a new sign
    CONFIRMED = auto()   # Word confirmed, showing it


class PhrasePredictor:
    """
    Temporal-voting LSTM predictor.

    The core insight: an LSTM on 4 classes will almost always push one class
    above 0.70 even on garbage input (resting hand, mid-transition pose) because
    softmax probabilities must sum to 1.  Threshold alone cannot fix this.

    The solution is temporal consensus voting:
      - Run inference every PREDICT_EVERY_N frames
      - Store the last VOTE_WINDOW raw predictions in a ring buffer
      - Only confirm a label when:
          (a) it appears in >= VOTE_MAJORITY of the last VOTE_WINDOW predictions
          (b) its mean confidence across those votes >= THRESHOLD
          (c) the runner-up label's mean confidence is < SECOND_PLACE_MAX
              (ensures the model is not split between two similar signs)

    This kills random shuffling because transient spikes don't survive the
    consensus window, while a real sign produces consistent predictions across
    multiple consecutive windows.

    State machine (same as before, voting added inside SIGNING):

        IDLE ──(hands appear, debounced)──► REENTRY
          ▲                                     │
          │  hands drop during buffer           │ buffer satisfied
          └─────────────────────────────── SIGNING
                                               │
                                        vote consensus hit
                                               ▼
                                           CONFIRMED
                                         (word stays visible,
                                          hands-off = forever,
                                          hands-on = REENTRY)
    """

    # ── frame rate context ─────────────────────────────────────────────────
    # Frontend sends frames every 150 ms → ~6-7 fps at the backend

    # Re-entry: frames of continuous hand presence after CONFIRMED before
    # we commit to a new sign.  Absorbs natural sign-tail hand movement.
    REENTRY_FRAMES_REQUIRED = 8    # ~1.2 s

    # Tiny debounce: frames of hand presence required to leave IDLE
    IDLE_ENTRY_FRAMES = 2

    # MediaPipe dropout tolerance inside SIGNING
    SIGNING_GRACE_FRAMES = 6       # ~0.9 s

    # Minimum frames buffered before we start running inference
    MIN_FRAMES_TO_PREDICT = 10

    # Run inference every N frames (reduces compute, smooths output)
    PREDICT_EVERY_N = 3

    # ── temporal voting ────────────────────────────────────────────────────
    # How many inference results to keep in the vote window
    VOTE_WINDOW = 5

    # How many of those must agree on the same label  (majority)
    VOTE_MAJORITY = 4              # 4-out-of-5

    # Mean confidence of the winner across its votes must exceed this
    VOTE_CONFIDENCE_THRESHOLD = 0.82   # higher than THRESHOLD to avoid weak wins

    # Runner-up's mean confidence must stay below this (gap enforcement)
    # Prevents confirmation when the model is split between two similar signs
    SECOND_PLACE_MAX = 0.55

    def __init__(
        self,
        model_path=PHRASE_MODEL_PATH,
        labels_path=PHRASE_LABELS_PATH,
        data_dir=PHRASE_DATA_DIR,
    ):
        self.model, self.index_to_label = load_phrase_assets(model_path, labels_path, data_dir)
        self._predict_fn = tf.function(self.model, reduce_retracing=True)
        self.stable_threshold = THRESHOLD

        self._state                 = _State.IDLE
        self._confirmed_label       = "Waiting..."
        self._confirmed_confidence  = 0.0
        self.sequence: list         = []

        # State counters
        self._idle_entry_counter    = 0
        self._reentry_counter       = 0
        self._signing_grace_counter = 0
        self._frames_since_predict  = 0

        # Temporal vote buffer: list of (label, confidence) tuples
        self._vote_buffer: list     = []

        # Telemetry
        self.last_inference_device  = "not-run"
        self.last_inference_mode    = "idle"

    # ── inference ─────────────────────────────────────────────────────────

    def _run_inference(self, input_data):
        try:
            output = self._predict_fn(input_data, training=False)
            self.last_inference_device = _format_device_name(getattr(output, "device", ""))
            self.last_inference_mode   = "tf-function"
            return output.numpy()[0]
        except Exception as error:
            if not _is_cudnn_backend_error(error):
                raise
            with tf.device("/CPU:0"):
                output = self.model(input_data, training=False)
            self.last_inference_device = _format_device_name(getattr(output, "device", ""))
            self.last_inference_mode   = "cpu-fallback"
            return output.numpy()[0]

    def get_last_inference_telemetry(self):
        return {
            "inference_device": self.last_inference_device,
            "inference_mode":   self.last_inference_mode,
        }

    def _extract_features(self, mp_bundle):
        from core.landmarks import LandmarkExtractor
        extractor = LandmarkExtractor.__new__(LandmarkExtractor)
        return LandmarkExtractor.extract_features(extractor, mp_bundle)

    def _append_keypoints(self, mp_bundle):
        kp = self._extract_features(mp_bundle)
        self.sequence.append(kp)
        self.sequence = self.sequence[-FRAMES:]

    def _build_input_sequence(self):
        if not self.sequence:
            return None
        arr = np.asarray(self.sequence, dtype=np.float32)
        if arr.ndim != 2:
            return None
        normalized = np.zeros((FRAMES, FEATURES_PER_FRAME), dtype=np.float32)
        if len(arr) >= FRAMES:
            normalized[:] = arr[-FRAMES:]
        else:
            normalized[:len(arr)] = arr
        return normalized

    def _raw_inference(self):
        """
        Run the model and return (label, confidence) for the top class.
        Does NOT apply any threshold — voting logic handles that.
        """
        seq = self._build_input_sequence()
        if seq is None:
            return None, None
        res = self._run_inference(np.expand_dims(seq, axis=0))
        idx        = int(np.argmax(res))
        confidence = float(res[idx])
        label      = self.index_to_label.get(idx, "Unknown")
        return label, confidence

    def _evaluate_votes(self):
        """
        Apply temporal consensus voting to the current vote buffer.

        Returns (label, mean_confidence) if consensus is reached, else (None, None).

        Rules:
          1. The most-voted label must appear >= VOTE_MAJORITY times.
          2. Its mean confidence across those votes >= VOTE_CONFIDENCE_THRESHOLD.
          3. The runner-up's mean confidence < SECOND_PLACE_MAX  (gap check).
        """
        if len(self._vote_buffer) < self.VOTE_WINDOW:
            return None, None

        # Tally votes
        label_counts = Counter(label for label, _ in self._vote_buffer)
        winner, winner_count = label_counts.most_common(1)[0]

        if winner_count < self.VOTE_MAJORITY:
            return None, None

        # Mean confidence of the winner's votes
        winner_confidences = [c for l, c in self._vote_buffer if l == winner]
        winner_mean_conf   = float(np.mean(winner_confidences))

        if winner_mean_conf < self.VOTE_CONFIDENCE_THRESHOLD:
            return None, None

        # Gap check: runner-up must not be too close
        if len(label_counts) > 1:
            runner_up = label_counts.most_common(2)[1][0]
            runner_confidences = [c for l, c in self._vote_buffer if l == runner_up]
            if runner_confidences:
                runner_mean_conf = float(np.mean(runner_confidences))
                if runner_mean_conf >= self.SECOND_PLACE_MAX:
                    return None, None

        return winner, winner_mean_conf

    # ── public API ────────────────────────────────────────────────────────

    def predict(self, mp_bundle, hands_detected: bool = True) -> tuple[str, float]:
        if not isinstance(mp_bundle, MediaPipeBundle):
            raise TypeError("PhrasePredictor.predict expects a MediaPipeBundle")

        # ── IDLE ──────────────────────────────────────────────────────────
        if self._state == _State.IDLE:
            if not hands_detected:
                self._idle_entry_counter = 0
                return "Waiting...", 0.0

            self._idle_entry_counter += 1
            if self._idle_entry_counter < self.IDLE_ENTRY_FRAMES:
                return "Waiting...", 0.0

            # Sustained presence — enter re-entry buffer
            self._idle_entry_counter = 0
            self._reentry_counter    = 0
            self.sequence            = []
            self._vote_buffer        = []
            self._state              = _State.REENTRY
            self._append_keypoints(mp_bundle)
            return "Waiting...", 0.0

        # ── REENTRY ───────────────────────────────────────────────────────
        if self._state == _State.REENTRY:
            if not hands_detected:
                # Hand dropped during buffer — likely sign tail, go back to IDLE
                # but keep showing the confirmed word if there is one
                self._reentry_counter    = 0
                self._idle_entry_counter = 0
                self._state              = _State.IDLE
                return self._confirmed_label, self._confirmed_confidence

            self._reentry_counter += 1
            self._append_keypoints(mp_bundle)

            if self._reentry_counter < self.REENTRY_FRAMES_REQUIRED:
                # Still absorbing — show previous word (no premature "Waiting...")
                return self._confirmed_label, self._confirmed_confidence

            # Buffer satisfied — genuine new sign starting
            self._reentry_counter       = 0
            self._frames_since_predict  = 0
            self._signing_grace_counter = 0
            self._vote_buffer           = []
            # Clear the label NOW — single clean "Waiting..." transition
            self._confirmed_label       = "Waiting..."
            self._confirmed_confidence  = 0.0
            self._state                 = _State.SIGNING
            return "Waiting...", 0.0

        # ── SIGNING ───────────────────────────────────────────────────────
        if self._state == _State.SIGNING:
            if not hands_detected:
                self._signing_grace_counter += 1
                if self._signing_grace_counter <= self.SIGNING_GRACE_FRAMES:
                    return "Waiting...", 0.0
                # Long dropout — hand genuinely left without a prediction
                self.sequence               = []
                self._vote_buffer           = []
                self._signing_grace_counter = 0
                self._frames_since_predict  = 0
                self._idle_entry_counter    = 0
                self._state                 = _State.IDLE
                return "Waiting...", 0.0

            self._signing_grace_counter = 0
            self._append_keypoints(mp_bundle)

            if len(self.sequence) < self.MIN_FRAMES_TO_PREDICT:
                return "Waiting...", 0.0

            self._frames_since_predict += 1
            if self._frames_since_predict < self.PREDICT_EVERY_N:
                return "Waiting...", 0.0

            self._frames_since_predict = 0

            # Run inference and push into vote buffer
            label, confidence = self._raw_inference()
            if label is not None:
                self._vote_buffer.append((label, confidence))
                # Keep buffer trimmed to window size
                self._vote_buffer = self._vote_buffer[-self.VOTE_WINDOW:]

            # Check if we have consensus
            winner, winner_conf = self._evaluate_votes()
            if winner is not None:
                self._confirmed_label      = winner
                self._confirmed_confidence = winner_conf
                self.sequence              = []
                self._vote_buffer          = []
                self._frames_since_predict = 0
                self._reentry_counter      = 0
                self._idle_entry_counter   = 0
                self._state                = _State.CONFIRMED
                return self._confirmed_label, self._confirmed_confidence

            return "Waiting...", 0.0

        # ── CONFIRMED ─────────────────────────────────────────────────────
        if self._state == _State.CONFIRMED:
            if not hands_detected:
                # Word stays visible indefinitely while hands are off screen
                self._reentry_counter    = 0
                self._idle_entry_counter = 0
                return self._confirmed_label, self._confirmed_confidence

            # Hands reappeared — enter re-entry buffer
            # Label stays visible during the buffer (no premature "Waiting...")
            self._reentry_counter = 0
            self._vote_buffer     = []
            self.sequence         = []
            self._state           = _State.REENTRY
            self._append_keypoints(mp_bundle)
            return self._confirmed_label, self._confirmed_confidence

        # Fallback
        return "Waiting...", 0.0

    def reset(self):
        self._state                 = _State.IDLE
        self._confirmed_label       = "Waiting..."
        self._confirmed_confidence  = 0.0
        self.sequence               = []
        self._vote_buffer           = []
        self._idle_entry_counter    = 0
        self._reentry_counter       = 0
        self._signing_grace_counter = 0
        self._frames_since_predict  = 0

    def close(self):
        pass