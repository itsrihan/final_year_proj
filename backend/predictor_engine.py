from collections import Counter

import numpy as np
import tensorflow as tf

from core.config import (
    FEATURES_PER_FRAME,
    FRAMES,
    PHRASE_DATA_DIR,
    PHRASE_LABELS_PATH,
    PHRASE_MODEL_PATH,
    THRESHOLD,
)
from core.landmarks import MediaPipeBundle
from predictor_assets import load_phrase_assets
from predictor_state import PredictorState


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


class PhrasePredictor:
    REENTRY_FRAMES_REQUIRED = 0
    IDLE_ENTRY_FRAMES = 1
    SIGNING_GRACE_FRAMES = 4

    MIN_FRAMES_TO_PREDICT = 1
    PREDICT_EVERY_N = 1

    VOTE_WINDOW = 1
    VOTE_MAJORITY = 1

    VOTE_CONFIDENCE_THRESHOLD = 0.35
    SECOND_PLACE_MAX = 0.95

    NULL_LABEL = "null"

    def __init__(
        self,
        model_path=PHRASE_MODEL_PATH,
        labels_path=PHRASE_LABELS_PATH,
        data_dir=PHRASE_DATA_DIR,
    ):
        self.model, self.index_to_label = load_phrase_assets(
            model_path,
            labels_path,
            data_dir,
        )

        self._predict_fn = tf.function(self.model, reduce_retracing=True)
        self.stable_threshold = THRESHOLD

        self._state = PredictorState.IDLE
        self._confirmed_label = "Waiting..."
        self._confirmed_confidence = 0.0

        self.sequence = []

        self._idle_entry_counter = 0
        self._reentry_counter = 0
        self._signing_grace_counter = 0
        self._frames_since_predict = 0

        self._vote_buffer = []

        self.last_inference_device = "not-run"
        self.last_inference_mode = "idle"

    def _run_inference(self, input_data):
        try:
            output = self._predict_fn(input_data, training=False)

            self.last_inference_device = _format_device_name(
                getattr(output, "device", "")
            )
            self.last_inference_mode = "tf-function"

            return output.numpy()[0]

        except Exception as error:
            if not _is_cudnn_backend_error(error):
                raise

            with tf.device("/CPU:0"):
                output = self.model(input_data, training=False)

            self.last_inference_device = _format_device_name(
                getattr(output, "device", "")
            )
            self.last_inference_mode = "cpu-fallback"

            return output.numpy()[0]

    def get_last_inference_telemetry(self):
        return {
            "inference_device": self.last_inference_device,
            "inference_mode": self.last_inference_mode,
        }

    def _extract_features(self, mp_bundle):
        from core.landmarks import LandmarkExtractor

        extractor = LandmarkExtractor.__new__(LandmarkExtractor)
        return LandmarkExtractor.extract_features(extractor, mp_bundle)

    def _append_keypoints(self, mp_bundle):
        keypoints = self._extract_features(mp_bundle)
        self.sequence.append(keypoints)
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
        seq = self._build_input_sequence()

        if seq is None:
            return None, None

        result = self._run_inference(np.expand_dims(seq, axis=0))

        index = int(np.argmax(result))
        confidence = float(result[index])
        label = self.index_to_label.get(index, "Unknown")

        return label, confidence

    def _evaluate_votes(self):
        if len(self._vote_buffer) < self.VOTE_WINDOW:
            return None, None

        label_counts = Counter(label for label, _ in self._vote_buffer)
        winner, winner_count = label_counts.most_common(1)[0]

        if winner_count < self.VOTE_MAJORITY:
            return None, None

        winner_confidences = [
            confidence
            for label, confidence in self._vote_buffer
            if label == winner
        ]

        winner_mean_confidence = float(np.mean(winner_confidences))

        if winner_mean_confidence < self.VOTE_CONFIDENCE_THRESHOLD:
            return None, None

        if len(label_counts) > 1:
            runner_up = label_counts.most_common(2)[1][0]

            runner_confidences = [
                confidence
                for label, confidence in self._vote_buffer
                if label == runner_up
            ]

            if runner_confidences:
                runner_mean_confidence = float(np.mean(runner_confidences))

                if runner_mean_confidence >= self.SECOND_PLACE_MAX:
                    return None, None

        return winner, winner_mean_confidence

    def _clear_for_idle(self):
        self.sequence = []
        self._vote_buffer = []
        self._signing_grace_counter = 0
        self._frames_since_predict = 0
        self._idle_entry_counter = 0
        self._reentry_counter = 0
        self._state = PredictorState.IDLE

    def _is_null_label(self, label):
        return str(label).strip().lower() == self.NULL_LABEL

    def predict(self, mp_bundle, hands_detected: bool = True) -> tuple[str, float]:
        if not isinstance(mp_bundle, MediaPipeBundle):
            raise TypeError("PhrasePredictor.predict expects a MediaPipeBundle")

        if self._state == PredictorState.IDLE:
            if not hands_detected:
                self._idle_entry_counter = 0
                return "Waiting...", 0.0

            self._idle_entry_counter += 1

            if self._idle_entry_counter < self.IDLE_ENTRY_FRAMES:
                return "Waiting...", 0.0

            self._idle_entry_counter = 0
            self._reentry_counter = 0
            self.sequence = []
            self._vote_buffer = []
            self._state = PredictorState.REENTRY

            self._append_keypoints(mp_bundle)

            return "Waiting...", 0.0

        if self._state == PredictorState.REENTRY:
            if not hands_detected:
                self._clear_for_idle()
                return "Waiting...", 0.0

            self._reentry_counter += 1
            self._append_keypoints(mp_bundle)

            if self.REENTRY_FRAMES_REQUIRED > 0 and self._reentry_counter < self.REENTRY_FRAMES_REQUIRED:
                return self._confirmed_label, self._confirmed_confidence

            self._reentry_counter = 0
            self._frames_since_predict = 0
            self._signing_grace_counter = 0
            self._vote_buffer = []
            self._confirmed_label = "Waiting..."
            self._confirmed_confidence = 0.0
            self._state = PredictorState.SIGNING

            return "Waiting...", 0.0

        if self._state == PredictorState.SIGNING:
            if not hands_detected:
                self._signing_grace_counter += 1

                if self._signing_grace_counter <= self.SIGNING_GRACE_FRAMES:
                    return "Waiting...", 0.0

                self._clear_for_idle()
                return "Waiting...", 0.0

            self._signing_grace_counter = 0
            self._append_keypoints(mp_bundle)

            if len(self.sequence) < self.MIN_FRAMES_TO_PREDICT:
                return "Waiting...", 0.0

            self._frames_since_predict += 1

            if self._frames_since_predict < self.PREDICT_EVERY_N:
                return "Waiting...", 0.0

            self._frames_since_predict = 0

            label, confidence = self._raw_inference()

            if label is None:
                return "Waiting...", 0.0

            self._vote_buffer.append((label, confidence))
            self._vote_buffer = self._vote_buffer[-self.VOTE_WINDOW:]

            winner, winner_confidence = self._evaluate_votes()

            if winner is None:
                return "Waiting...", 0.0

            if self._is_null_label(winner):
                self.sequence = []
                self._vote_buffer = []
                self._frames_since_predict = 0
                self._state = PredictorState.IDLE
                return "Waiting...", 0.0

            self._confirmed_label = winner
            self._confirmed_confidence = winner_confidence

            self.sequence = []
            self._vote_buffer = []
            self._frames_since_predict = 0
            self._reentry_counter = 0
            self._idle_entry_counter = 0
            self._state = PredictorState.CONFIRMED

            return self._confirmed_label, self._confirmed_confidence

        if self._state == PredictorState.CONFIRMED:
            if not hands_detected:
                self._reentry_counter = 0
                self._idle_entry_counter = 0
                return self._confirmed_label, self._confirmed_confidence

            self._reentry_counter = 0
            self._vote_buffer = []
            self.sequence = []
            self._state = PredictorState.REENTRY

            self._append_keypoints(mp_bundle)

            return self._confirmed_label, self._confirmed_confidence

        return "Waiting...", 0.0

    def reset(self):
        self._state = PredictorState.IDLE
        self._confirmed_label = "Waiting..."
        self._confirmed_confidence = 0.0
        self.sequence = []
        self._vote_buffer = []
        self._idle_entry_counter = 0
        self._reentry_counter = 0
        self._signing_grace_counter = 0
        self._frames_since_predict = 0

    def close(self):
        pass
