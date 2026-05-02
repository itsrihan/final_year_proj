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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# PhrasePredictor
# ---------------------------------------------------------------------------

class PhrasePredictor:
    # -----------------------------------------------------------------------
    # Tuning constants — adjust these to change prediction feel
    # -----------------------------------------------------------------------

    # How many consecutive frames with hands before leaving IDLE
    IDLE_ENTRY_FRAMES = 2

    # Stabilisation frames before SIGNING begins
    REENTRY_FRAMES_REQUIRED = 4

    # How many frames without hands are tolerated mid-sign before giving up
    SIGNING_GRACE_FRAMES = 10

    # Don't attempt inference until this many frames are in the buffer
    MIN_FRAMES_TO_PREDICT = FRAMES

    # Run inference every N frames (1 = every frame, 2 = every other, etc.)
    PREDICT_EVERY_N = 1

    # -----------------------------------------------------------------------
    # Voting — made stricter than the original 3/2
    # -----------------------------------------------------------------------

    # Number of recent raw predictions to consider
    VOTE_WINDOW = 6

    # Minimum votes the winner must hold
    VOTE_MAJORITY = 4

    # Minimum mean confidence for the winner to be accepted
    VOTE_CONFIDENCE_THRESHOLD = 0.55

    # Maximum mean confidence allowed for the runner-up.
    # If second place is this close, the result is too ambiguous.
    SECOND_PLACE_MAX = 0.40

    # -----------------------------------------------------------------------
    # HOLD state — how long to display the confirmed label before re-signing
    # -----------------------------------------------------------------------

    # Frames the engine stays in HOLD after confirming a label.
    # At 30fps this is ~1.5 seconds of visible display before allowing
    # the next sign to start.  Increase for slower signers.
    HOLD_FRAMES = 45

    # During HOLD, if the signer clearly removes their hand for this many
    # frames we exit HOLD early and return to IDLE.
    HOLD_EARLY_EXIT_FRAMES = 8

    # -----------------------------------------------------------------------

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

        # Rolling feature buffer — at most FRAMES entries
        self.sequence = []

        # State transition counters
        self._idle_entry_counter = 0
        self._reentry_counter = 0
        self._signing_grace_counter = 0
        self._frames_since_predict = 0

        # HOLD state counters
        self._hold_counter = 0
        self._hold_no_hand_counter = 0

        # Short-term vote buffer
        self._vote_buffer = []

        # Telemetry
        self.last_inference_device = "not-run"
        self.last_inference_mode = "idle"
        self.last_raw_label = "None"
        self.last_raw_confidence = 0.0

    # -----------------------------------------------------------------------
    # Internal: inference
    # -----------------------------------------------------------------------

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

    def get_debug_info(self):
        return {
            "state": self._state.name if hasattr(self._state, "name") else str(self._state),
            "sequence_len": len(self.sequence),
            "vote_len": len(self._vote_buffer),
            "confirmed_label": self._confirmed_label,
            "confirmed_confidence": self._confirmed_confidence,
            "last_raw_label": self.last_raw_label,
            "last_raw_confidence": self.last_raw_confidence,
            "inference_device": self.last_inference_device,
            "inference_mode": self.last_inference_mode,
            "hold_counter": self._hold_counter,
        }

    # -----------------------------------------------------------------------
    # Internal: feature extraction and buffering
    # -----------------------------------------------------------------------

    def _extract_features(self, mp_bundle):
        from core.landmarks import LandmarkExtractor
        extractor = LandmarkExtractor.__new__(LandmarkExtractor)
        return LandmarkExtractor.extract_features(extractor, mp_bundle)

    def _append_keypoints(self, mp_bundle):
        keypoints = self._extract_features(mp_bundle)
        self.sequence.append(keypoints)
        self.sequence = self.sequence[-FRAMES:]

    def _build_input_sequence(self):
        """
        Build a (FRAMES, FEATURES_PER_FRAME) array for the model.

        FIX vs original: zero-padding is placed at the END (tail), not the
        START.  Padding at the start injects ghost all-zero frames into the
        oldest timesteps that the LSTM reads first, which biases hidden state
        towards "nothing happening".  Tail-padding keeps real data at the
        front so the LSTM sees the actual sign motion before any padding.
        """
        if not self.sequence:
            return None

        arr = np.asarray(self.sequence, dtype=np.float32)

        if arr.ndim != 2:
            return None

        normalized = np.zeros((FRAMES, FEATURES_PER_FRAME), dtype=np.float32)

        n = min(len(arr), FRAMES)
        # Place real frames at the START, padding (zeros) at the END
        normalized[:n] = arr[-n:]

        return normalized

    # -----------------------------------------------------------------------
    # Internal: raw inference
    # -----------------------------------------------------------------------

    def _raw_inference(self):
        seq = self._build_input_sequence()
        if seq is None:
            return None, None

        result = self._run_inference(np.expand_dims(seq, axis=0))

        index = int(np.argmax(result))
        confidence = float(result[index])
        label = self.index_to_label.get(index, "Unknown")

        self.last_raw_label = label
        self.last_raw_confidence = confidence

        return label, confidence

    # -----------------------------------------------------------------------
    # Internal: voting
    # -----------------------------------------------------------------------

    def _evaluate_votes(self):
        """
        Return (winner_label, mean_confidence) if the vote buffer has a clear
        winner, otherwise (None, None).

        Changes vs original:
        - SECOND_PLACE_MAX is now a real guard (0.40 default vs old 0.90).
          This prevents confirming a sign when the model is torn between two.
        - Requires VOTE_MAJORITY out of VOTE_WINDOW (now 4/6 vs old 2/3).
        """
        if len(self._vote_buffer) < self.VOTE_WINDOW:
            return None, None

        label_counts = Counter(label for label, _ in self._vote_buffer)
        ranked = label_counts.most_common()
        winner, winner_count = ranked[0]

        if winner_count < self.VOTE_MAJORITY:
            return None, None

        winner_confidences = [
            conf for lbl, conf in self._vote_buffer if lbl == winner
        ]
        winner_mean = float(np.mean(winner_confidences))

        if winner_mean < self.VOTE_CONFIDENCE_THRESHOLD:
            return None, None

        # Second-place guard: reject if runner-up is too close
        if len(ranked) > 1:
            second_label = ranked[1][0]
            second_confidences = [
                conf for lbl, conf in self._vote_buffer if lbl == second_label
            ]
            if second_confidences:
                second_mean = float(np.mean(second_confidences))
                if second_mean >= self.SECOND_PLACE_MAX:
                    return None, None

        return winner, winner_mean

    # -----------------------------------------------------------------------
    # Internal: state resets
    # -----------------------------------------------------------------------

    def _clear_for_idle(self):
        self.sequence = []
        self._vote_buffer = []
        self._signing_grace_counter = 0
        self._frames_since_predict = 0
        self._idle_entry_counter = 0
        self._reentry_counter = 0
        self._hold_counter = 0
        self._hold_no_hand_counter = 0
        self._state = PredictorState.IDLE

    def _is_null_label(self, label):
        return str(label).strip().lower() == self.NULL_LABEL

    # -----------------------------------------------------------------------
    # Public: main predict loop
    # -----------------------------------------------------------------------

    def predict(self, mp_bundle, hands_detected: bool = True) -> tuple[str, float]:
        if not isinstance(mp_bundle, MediaPipeBundle):
            raise TypeError("PhrasePredictor.predict expects a MediaPipeBundle")

        # -------------------------------------------------------------------
        # IDLE — waiting for hands to appear
        # -------------------------------------------------------------------
        if self._state == PredictorState.IDLE:
            if not hands_detected:
                self._idle_entry_counter = 0
                return "Waiting...", 0.0

            self._idle_entry_counter += 1
            if self._idle_entry_counter < self.IDLE_ENTRY_FRAMES:
                return "Waiting...", 0.0

            # Hands confirmed present — begin reentry
            self._idle_entry_counter = 0
            self._reentry_counter = 0
            self.sequence = []
            self._vote_buffer = []
            self._state = PredictorState.REENTRY

            self._append_keypoints(mp_bundle)
            return "Translating...", 0.0

        # -------------------------------------------------------------------
        # REENTRY — stabilise before running inference
        # -------------------------------------------------------------------
        if self._state == PredictorState.REENTRY:
            if not hands_detected:
                self._clear_for_idle()
                return "Waiting...", 0.0

            self._reentry_counter += 1
            self._append_keypoints(mp_bundle)

            if self._reentry_counter < self.REENTRY_FRAMES_REQUIRED:
                return "Translating...", 0.0

            self._reentry_counter = 0
            self._frames_since_predict = 0
            self._signing_grace_counter = 0
            self._vote_buffer = []
            self._confirmed_label = "Waiting..."
            self._confirmed_confidence = 0.0
            self._state = PredictorState.SIGNING
            return "Translating...", 0.0

        # -------------------------------------------------------------------
        # SIGNING — collect frames and run inference
        # -------------------------------------------------------------------
        if self._state == PredictorState.SIGNING:
            if not hands_detected:
                self._signing_grace_counter += 1
                if self._signing_grace_counter <= self.SIGNING_GRACE_FRAMES:
                    return "Translating...", 0.0
                self._clear_for_idle()
                return "Waiting...", 0.0

            self._signing_grace_counter = 0
            self._append_keypoints(mp_bundle)

            if len(self.sequence) < self.MIN_FRAMES_TO_PREDICT:
                return "Translating...", 0.0

            self._frames_since_predict += 1
            if self._frames_since_predict < self.PREDICT_EVERY_N:
                return "Translating...", 0.0
            self._frames_since_predict = 0

            label, confidence = self._raw_inference()

            if label is None:
                return "Translating...", 0.0

            if self._is_null_label(label):
                # Null label means the model sees no meaningful sign.
                # Clear the buffer and try again from SIGNING without
                # going all the way back to IDLE — the hand is still present.
                self.sequence = []
                self._vote_buffer = []
                self._frames_since_predict = 0
                # Stay in SIGNING so the user doesn't see a flash to "Waiting..."
                return "Translating...", 0.0

            self._vote_buffer.append((label, confidence))
            self._vote_buffer = self._vote_buffer[-self.VOTE_WINDOW:]

            winner, winner_confidence = self._evaluate_votes()

            if winner is None:
                return "Translating...", 0.0

            # A label has been confirmed
            self._confirmed_label = winner
            self._confirmed_confidence = winner_confidence

            # Clear buffers so re-entering SIGNING starts clean
            self.sequence = []
            self._vote_buffer = []
            self._frames_since_predict = 0
            self._reentry_counter = 0
            self._idle_entry_counter = 0

            # Move to CONFIRMED, then immediately to HOLD on the same frame
            self._state = PredictorState.CONFIRMED
            self._hold_counter = 0
            self._hold_no_hand_counter = 0
            self._state = PredictorState.HOLD  # type: ignore[attr-defined]

            return self._confirmed_label, self._confirmed_confidence

        # -------------------------------------------------------------------
        # CONFIRMED — single-frame pass-through on the frame that confirmed.
        # In practice we jump straight to HOLD above, but keep this guard
        # in case the state is set externally (e.g. from debug tools).
        # -------------------------------------------------------------------
        if self._state == PredictorState.CONFIRMED:
            self._hold_counter = 0
            self._hold_no_hand_counter = 0
            self._state = PredictorState.HOLD  # type: ignore[attr-defined]
            return self._confirmed_label, self._confirmed_confidence

        # -------------------------------------------------------------------
        # HOLD — display the confirmed label for HOLD_FRAMES frames.
        #
        # This is the key fix.  Previously CONFIRMED immediately pushed back
        # to REENTRY whenever a hand was present, causing the label to be
        # overwritten within the next vote window.  Now the engine sits in
        # HOLD, keeps emitting the same label, and only re-enters REENTRY
        # after the hold expires (or the hand disappears and reappears).
        # -------------------------------------------------------------------
        if self._state == PredictorState.HOLD:  # type: ignore[attr-defined]
            self._hold_counter += 1

            if not hands_detected:
                self._hold_no_hand_counter += 1
                # If hands have been absent long enough, exit hold early
                if self._hold_no_hand_counter >= self.HOLD_EARLY_EXIT_FRAMES:
                    self._clear_for_idle()
                    # Return the last confirmed label so the UI doesn't blank
                    # immediately — the caller can fade it out at its own pace
                    return self._confirmed_label, self._confirmed_confidence
                return self._confirmed_label, self._confirmed_confidence

            # Hand is present — reset the no-hand counter
            self._hold_no_hand_counter = 0

            if self._hold_counter < self.HOLD_FRAMES:
                # Still within the hold window — keep displaying
                return self._confirmed_label, self._confirmed_confidence

            # Hold window expired — ready for the next sign
            self._hold_counter = 0
            self._hold_no_hand_counter = 0
            self._reentry_counter = 0
            self.sequence = []
            self._vote_buffer = []
            self._state = PredictorState.REENTRY

            self._append_keypoints(mp_bundle)
            return self._confirmed_label, self._confirmed_confidence

        # Fallback (should never reach here)
        return "Waiting...", 0.0

    # -----------------------------------------------------------------------
    # Public: reset
    # -----------------------------------------------------------------------

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
        self._hold_counter = 0
        self._hold_no_hand_counter = 0
        self.last_raw_label = "None"
        self.last_raw_confidence = 0.0

    def close(self):
        pass