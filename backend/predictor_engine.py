from collections import Counter
import time

import numpy as np
import tensorflow as tf

from core.config import (
    FEATURES_PER_FRAME,
    FRAMES,
    HAND_MAX_INTERP_FRAMES,
    HAND_SMOOTH_ALPHA,
    PHRASE_DATA_DIR,
    PHRASE_LABELS_PATH,
    PHRASE_MODEL_PATH,
    THRESHOLD,
)
from core.landmarks import MediaPipeBundle
from predictor_assets import load_phrase_assets
from predictor_state import PredictorState, CaptureState


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
# CaptureStateMachine
# ---------------------------------------------------------------------------

class CaptureStateMachine:
    """
    Demo-stable capture state machine for ASL sign prediction.
    
    Flow:
    1. READY: wait for hand debounce
    2. CAPTURING: collect 35 frames with dropout tolerance
    3. PREDICTING: run inference once
    4. WAIT_FOR_RELEASE: require the signer to remove hands before next capture
    5. Back to READY
    """

    HAND_DEBOUNCE_REQUIRED = 2
    MAX_MISSED_CAPTURE_FRAMES = 2
    RELEASE_REQUIRED_FRAMES = 5
    REQUIRED_FRAMES = 35
    CAPTURE_TARGET_FRAMES = 45  # Grace: collect 45, then downsample to 35 for model
    MODEL_FRAMES = 35  # Model always takes 35 frames

    def __init__(self, model_fn):
        """
        Args:
            model_fn: callable(features_array) -> (label, confidence)
        """
        self.model_fn = model_fn
        
        self.state = CaptureState.READY
        self.captured_frames = []
        self.last_valid_features = None
        self.hand_debounce_frames = 0
        self.missed_frames_during_capture = 0
        self.last_prediction = ("", 0.0)
        self.release_counter = 0
        self._last_prediction_accepted = False

    def process_frame(self, features, hands_detected):
        """
        Process one frame with given features and hand detection status.
        
        Returns:
            {
                'asl_capture_state': str,
                'captured_frames': int,
                'required_frames': int,
                'hands_detected': bool,
                'hand_debounce_frames': int,
                'prediction': str,
                'confidence': float
            }
        """
        if self.state == CaptureState.READY:
            return self._handle_ready(features, hands_detected)
        elif self.state == CaptureState.CAPTURING:
            return self._handle_capturing(features, hands_detected)
        elif self.state == CaptureState.PREDICTING:
            return self._handle_predicting(features, hands_detected)
        elif self.state == CaptureState.WAIT_FOR_RELEASE:
            return self._handle_wait_for_release(features, hands_detected)
        else:
            return self._make_response()

    def _handle_ready(self, features, hands_detected):
        """READY state: debounce hand detection."""
        if hands_detected:
            self.hand_debounce_frames += 1
            if self.hand_debounce_frames >= self.HAND_DEBOUNCE_REQUIRED:
                # Hand debounce passed, start capturing
                self.state = CaptureState.CAPTURING
                self.captured_frames = []
                self.missed_frames_during_capture = 0
                self.last_valid_features = features
                print(f"[CAPTURE] Debounce complete, starting CAPTURING")
        else:
            # Reset debounce
            if self.hand_debounce_frames > 0:
                print(f"[CAPTURE] Hand lost, debounce reset")
            self.hand_debounce_frames = 0

        return self._make_response()

    def _handle_capturing(self, features, hands_detected):
        """CAPTURING state: collect frames with dropout tolerance (45-frame grace)."""
        if hands_detected:
            self.missed_frames_during_capture = 0
            self.captured_frames.append(features)
            self.last_valid_features = features
            
            # Log every 5 frames
            if len(self.captured_frames) % 5 == 0:
                print(f"[CAPTURE] Progress: {len(self.captured_frames)}/{self.CAPTURE_TARGET_FRAMES} frames")
            
            # Check if capture complete (45 frames for grace, will downsample to 35 for model)
            if len(self.captured_frames) >= self.CAPTURE_TARGET_FRAMES:
                self.state = CaptureState.PREDICTING
                print(f"[CAPTURE] Capture complete, {len(self.captured_frames)} frames collected, starting PREDICTING")
        else:
            # Hand lost during capture
            self.missed_frames_during_capture += 1
            
            if self.missed_frames_during_capture <= self.MAX_MISSED_CAPTURE_FRAMES:
                # Reuse last valid features
                if self.last_valid_features is not None:
                    self.captured_frames.append(self.last_valid_features)
                print(f"[CAPTURE] Hand lost (missed {self.missed_frames_during_capture} frame(s)), reusing last features")
            else:
                # Hand missing too long, cancel capture and enter WAIT_FOR_RELEASE
                print(f"[CAPTURE] Hand missing for {self.missed_frames_during_capture} frames, cancelling capture and waiting for release")
                self.state = CaptureState.WAIT_FOR_RELEASE
                self.captured_frames = []
                self.hand_debounce_frames = 0
                self.missed_frames_during_capture = 0
                self.release_counter = 0

        return self._make_response()

    def _handle_predicting(self, features, hands_detected):
        """PREDICTING state: run inference once (with 45->35 downsampling)."""
        # Only run inference once during this state
        if len(self.captured_frames) >= self.CAPTURE_TARGET_FRAMES:
            try:
                # Downsample 45 frames to 35 for model input
                indices = np.linspace(0, len(self.captured_frames) - 1, self.MODEL_FRAMES).astype(int)
                downsampled_frames = np.asarray(self.captured_frames, dtype=np.float32)[indices]
                # Prepare input: (1, 35, FEATURES_PER_FRAME)
                model_input = np.expand_dims(downsampled_frames, axis=0)
                label, confidence = self.model_fn(model_input)
                
                # Post-process prediction: apply null/uncertain rules with 0.60 threshold
                ACCEPT_THRESHOLD = 0.60
                display_label = label
                if label == "null":
                    display_label = "No clear sign"
                elif confidence < ACCEPT_THRESHOLD:
                    display_label = "Uncertain"

                # Only accept if confidence >= 0.60 and label != "null"
                accepted = (label != "null" and confidence >= ACCEPT_THRESHOLD)

                # Store displayed text and raw confidence
                self.last_prediction = (display_label, float(confidence))
                self._last_prediction_accepted = accepted
                
                # Detailed logging
                print(f"[PREDICT] raw_label={label}, raw_confidence={confidence:.4f}, final_display={display_label}, "
                      f"captured_raw_frames={len(self.captured_frames)}, model_frames={self.MODEL_FRAMES}, "
                      f"state=PREDICTING, accepted={accepted}")
            except Exception as e:
                print(f"[PREDICT] Error during inference: {e}")
                self.last_prediction = ("Error", 0.0)
                self._last_prediction_accepted = False
        # Move to WAIT_FOR_RELEASE and keep showing last_prediction until release
        self.state = CaptureState.WAIT_FOR_RELEASE
        self.release_counter = 0
        # Clear capture buffer but keep last_prediction displayed
        self.captured_frames = []
        self.hand_debounce_frames = 0
        self.missed_frames_during_capture = 0

        return self._make_response()

    def _handle_cooldown(self, features, hands_detected):
        # Backwards-compat: should not be used. Fallback to READY.
        self.state = CaptureState.READY
        self.hand_debounce_frames = 0
        return self._make_response()

    def _handle_wait_for_release(self, features, hands_detected):
        """WAIT_FOR_RELEASE: require consecutive no-hand frames before returning to READY."""
        # raw hands_detected is used here
        if not hands_detected:
            self.release_counter += 1
            print(f"[CAPTURE] Release progress: {self.release_counter}/{self.RELEASE_REQUIRED_FRAMES}")
            if self.release_counter >= self.RELEASE_REQUIRED_FRAMES:
                # Fully released, move to READY and clear displayed prediction
                self.state = CaptureState.READY
                self.hand_debounce_frames = 0
                self.release_counter = 0
                # Clear last prediction display
                self.last_prediction = ("", 0.0)
                self._last_prediction_accepted = False
                print(f"[CAPTURE] Release confirmed, returning to READY")
        else:
            # Hand visible again — reset release counter and remain WAIT_FOR_RELEASE
            if self.release_counter > 0:
                print(f"[CAPTURE] Hand returned during release, resetting release counter")
            self.release_counter = 0

        return self._make_response()

    def reset(self):
        """Hard reset the capture machine to READY state (used for camera-off)."""
        self.state = CaptureState.READY
        self.captured_frames = []
        self.last_valid_features = None
        self.hand_debounce_frames = 0
        self.missed_frames_during_capture = 0
        self.last_prediction = ("", 0.0)
        self.release_counter = 0
        self._last_prediction_accepted = False
        print(f"[CAPTURE] Hard reset to READY (camera-off or other trigger)")

    def _make_response(self):
        """Build standard response dictionary."""
        return {
            'asl_capture_state': self.state.name.lower(),
            'captured_frames': len(self.captured_frames),
            'required_frames': self.CAPTURE_TARGET_FRAMES,  # Show user the 45-frame target
            'hand_debounce_frames': self.hand_debounce_frames,
            'prediction': self.last_prediction[0],
            'confidence': float(self.last_prediction[1]),
        }


# ---------------------------------------------------------------------------
# ManualCaptureMachine
# ---------------------------------------------------------------------------

class ManualCaptureMachine:
    """
    Manual capture mode for reliable demo capture.
    User triggers capture via button/keyboard.

    States:
    - manual_ready
    - manual_waiting_for_hands
    - manual_capturing
    - manual_predicting
    - manual_result
    """

    CAPTURE_TARGET_FRAMES = 35
    MODEL_FRAMES = 35
    ACCEPT_THRESHOLD = 0.60
    HAND_DEBOUNCE_REQUIRED = 2
    MAX_MISSED_HAND_FRAMES = 3
    MIN_HAND_RATIO_TO_PREDICT = 0.70
    RESULT_HOLD_FRAMES = 45

    def __init__(self, model_fn, labels=None):
        """
        Args:
            model_fn: callable(frames_array (1,35,FEATURES_PER_FRAME)) -> raw probabilities
            labels: optional index-ordered label list used for debug output
        """
        self.model_fn = model_fn
        self.labels = self._normalize_labels(labels)
        self.state = "manual_ready"
        self.captured_frames = []
        self.last_prediction = ("", 0.0)
        self.last_display_label = ""
        self.result_hold_counter = 0
        self.waiting_hand_counter = 0
        self.capture_missed_hand_counter = 0
        self.hands_true_count = 0
        self.hands_false_count = 0
        self.last_capture_hand_ratio = 0.0

    def _normalize_labels(self, labels):
        if labels is None:
            return []
        if isinstance(labels, dict):
            return [label for _, label in sorted(labels.items(), key=lambda item: item[0])]
        return list(labels)

    def _reset_capture_buffers(self):
        self.captured_frames = []
        self.capture_missed_hand_counter = 0
        self.hands_true_count = 0
        self.hands_false_count = 0
        self.last_capture_hand_ratio = 0.0

    def _finalize_capture_hand_stats(self):
        total = self.hands_true_count + self.hands_false_count
        self.last_capture_hand_ratio = (self.hands_true_count / total) if total > 0 else 0.0

    def process_frame(self, features, hands_detected, manual_command=None):
        """
        Process one frame in manual mode.
        manual_command must be an edge-triggered one-shot: "start" | "cancel" | "ack" | None.
        """
        state_before = self.state
        did_start = False
        did_predict = False

        if manual_command == "cancel":
            self.state = "manual_ready"
            self._reset_capture_buffers()
            self.waiting_hand_counter = 0
            self.result_hold_counter = 0
            print(f"[MANUAL] cancel | state {state_before}→manual_ready")
            return self._make_response(did_start=False, did_predict=False)

        if manual_command == "ack":
            self.state = "manual_ready"
            self._reset_capture_buffers()
            self.waiting_hand_counter = 0
            self.last_prediction = ("", 0.0)
            self.last_display_label = ""
            self.result_hold_counter = 0
            print(f"[MANUAL] ack | state {state_before}→manual_ready")
            return self._make_response(did_start=False, did_predict=False)

        if manual_command == "start":
            if self.state in ("manual_ready", "manual_result"):
                self.state = "manual_waiting_for_hands"
                self._reset_capture_buffers()
                self.waiting_hand_counter = 0
                self.last_prediction = ("", 0.0)
                self.last_display_label = ""
                self.result_hold_counter = 0
                did_start = True
                print(f"[MANUAL] start | state {state_before}→manual_waiting_for_hands")
                print("MANUAL_WAITING_FOR_HANDS")
            else:
                print(f"[MANUAL] start ignored | already in state={self.state}")

        if self.state == "manual_waiting_for_hands":
            if hands_detected:
                self.waiting_hand_counter += 1
                print(
                    f"MANUAL_WAITING_FOR_HANDS | hands=True | "
                    f"debounce={self.waiting_hand_counter}/{self.HAND_DEBOUNCE_REQUIRED}"
                )
                if self.waiting_hand_counter >= self.HAND_DEBOUNCE_REQUIRED:
                    self.state = "manual_capturing"
                    self.waiting_hand_counter = 0
                    self._reset_capture_buffers()
                    print("MANUAL_CAPTURE_STARTED")
            else:
                if self.waiting_hand_counter > 0:
                    print("[MANUAL] waiting_for_hands reset | hands lost before debounce")
                self.waiting_hand_counter = 0
                print("MANUAL_WAITING_FOR_HANDS | hands=False | debounce=0/2")

            return self._make_response(did_start=did_start, did_predict=False)

        if self.state == "manual_result":
            self.result_hold_counter += 1
            print(
                f"[MANUAL] frame | state=manual_result | cmd={manual_command} "
                f"| hands={hands_detected} | frames={len(self.captured_frames)} "
                f"| hold={self.result_hold_counter}/{self.RESULT_HOLD_FRAMES} "
                f"| did_start={did_start} | did_predict=False"
            )

            if self.result_hold_counter >= self.RESULT_HOLD_FRAMES:
                print("[MANUAL] result timeout | manual_result→manual_ready")
                self.state = "manual_ready"
                self._reset_capture_buffers()
                self.last_prediction = ("", 0.0)
                self.last_display_label = ""
                self.result_hold_counter = 0

            return self._make_response(did_start=did_start, did_predict=False)

        if self.state == "manual_ready":
            print(
                f"[MANUAL] frame | state={self.state} | cmd={manual_command} "
                f"| hands={hands_detected} | frames={len(self.captured_frames)} "
                f"| did_start={did_start} | did_predict=False"
            )
            return self._make_response(did_start=did_start, did_predict=False)

        if self.state == "manual_capturing":
            if hands_detected:
                self.capture_missed_hand_counter = 0
                self.hands_true_count += 1
                self.captured_frames.append(features)
            else:
                self.hands_false_count += 1
                self.capture_missed_hand_counter += 1

            progress = len(self.captured_frames)
            print(f"MANUAL_CAPTURE_FRAME hands={hands_detected} frame_count={progress}/{self.CAPTURE_TARGET_FRAMES}")

            if not hands_detected and self.capture_missed_hand_counter > self.MAX_MISSED_HAND_FRAMES:
                print("MANUAL_CAPTURE_CANCELLED_TOO_MANY_MISSED_HANDS")
                self.state = "manual_waiting_for_hands"
                self._reset_capture_buffers()
                self.waiting_hand_counter = 0
                return self._make_response(did_start=did_start, did_predict=False)

            if progress % 5 == 0 or progress == 1:
                print(f"[MANUAL] progress {progress}/{self.CAPTURE_TARGET_FRAMES} | hands={hands_detected}")

            if progress >= self.CAPTURE_TARGET_FRAMES:
                self._finalize_capture_hand_stats()
                print(
                    f"[MANUAL] hand stats | hands_true_count={self.hands_true_count} "
                    f"hands_false_count={self.hands_false_count} hands_ratio={self.last_capture_hand_ratio:.3f}"
                )

                if self.last_capture_hand_ratio < self.MIN_HAND_RATIO_TO_PREDICT:
                    print(
                        f"[MANUAL] prediction skipped | hands_ratio={self.last_capture_hand_ratio:.3f} "
                        f"below threshold={self.MIN_HAND_RATIO_TO_PREDICT:.2f}"
                    )
                    self.state = "manual_waiting_for_hands"
                    self._reset_capture_buffers()
                    self.waiting_hand_counter = 0
                    return self._make_response(did_start=did_start, did_predict=False)

                self.state = "manual_predicting"
                print("ENTER_PREDICT")
                label, confidence = self._run_inference()
                print("PRED_COMPLETE")
                self.last_prediction = (label, confidence)
                self.state = "manual_result"
                self.result_hold_counter = 0
                did_predict = True
                print(
                    f"[MANUAL] frame | state=manual_predicting→manual_result "
                    f"| cmd={manual_command} | hands={hands_detected} "
                    f"| frames={progress} | did_start={did_start} | did_predict=True"
                )
                return self._make_response(did_start=did_start, did_predict=True)

            print(
                f"[MANUAL] frame | state=manual_capturing | cmd={manual_command} "
                f"| hands={hands_detected} | frames={progress}/{self.CAPTURE_TARGET_FRAMES} "
                f"| did_start={did_start} | did_predict=False"
            )
            return self._make_response(did_start=did_start, did_predict=False)

        print(f"[MANUAL] fallback | state={self.state}")
        return self._make_response(did_start=False, did_predict=False)

    def _run_inference(self):
        """Run inference on exactly 35 frames — no downsampling."""
        print(f"[MANUAL] predicting {len(self.captured_frames)} frames (no downsampling)")

        frames_arr = np.asarray(self.captured_frames, dtype=np.float32)
        model_input = np.expand_dims(frames_arr, axis=0)  # (1, 35, FEATURES_PER_FRAME)

        print("RUNNING_MODEL")
        prediction = np.asarray(self.model_fn(model_input), dtype=np.float32)
        if prediction.ndim == 1:
            prediction = np.expand_dims(prediction, axis=0)

        probs = prediction[0]
        top_indices = probs.argsort()[-3:][::-1]
        labels = self.labels or [str(index) for index in range(len(probs))]
        print("RAW_TOP3:", [(labels[int(index)] if int(index) < len(labels) else str(int(index)), float(probs[index])) for index in top_indices])
        print("MAX_CONF:", float(probs[top_indices[0]]))
        print("THRESHOLD:", THRESHOLD)
        print("INPUT_SHAPE:", frames_arr.shape)
        print(
            "INPUT_MIN_MAX_MEAN:",
            float(frames_arr.min()),
            float(frames_arr.max()),
            float(frames_arr.mean()),
        )

        index = int(np.argmax(probs))
        confidence = float(probs[index])
        label = labels[index] if index < len(labels) else str(index)

        if label == "null":
            display_label = "No clear sign"
        elif confidence < self.ACCEPT_THRESHOLD:
            display_label = "Uncertain"
        else:
            display_label = label

        self.last_display_label = display_label
        print(f"[MANUAL] result label={label}, confidence={confidence:.4f}, display={display_label}")
        return display_label, confidence

    def _make_response(self, did_start=False, did_predict=False):
        label, conf = self.last_prediction
        return {
            'manual_capture_state': self.state,
            'captured_frames': len(self.captured_frames),
            'required_frames': self.CAPTURE_TARGET_FRAMES,
            'prediction': label,
            'confidence': conf,
            'did_start_capture': did_start,
            'did_run_prediction': did_predict,
            'hands_true_count': self.hands_true_count,
            'hands_false_count': self.hands_false_count,
            'hands_ratio': round(self.last_capture_hand_ratio, 4),
        }

    def reset(self):
        """Hard reset to manual_ready (used for camera-off)."""
        self.state = "manual_ready"
        self._reset_capture_buffers()
        self.last_prediction = ("", 0.0)
        self.last_display_label = ""
        self.waiting_hand_counter = 0
        self.result_hold_counter = 0
        print("[MANUAL] reset to manual_ready")


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

        # Feature-only extractor state used by LandmarkExtractor.extract_features.
        # We intentionally avoid constructing full MediaPipe pipelines here.
        self._feature_extractor = self._build_feature_extractor()

    def _build_feature_extractor(self):
        from core.landmarks import LandmarkExtractor

        extractor = LandmarkExtractor.__new__(LandmarkExtractor)
        extractor._smooth_alpha = HAND_SMOOTH_ALPHA
        extractor._prev_hand_features = None
        extractor._last_detected_hand_features = None
        extractor._hand_dropout_frames = 0
        extractor._max_interp_frames = HAND_MAX_INTERP_FRAMES
        return extractor

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
            return output.numpy()

        except Exception as error:
            if not _is_cudnn_backend_error(error):
                raise
            with tf.device("/CPU:0"):
                output = self.model(input_data, training=False)
            self.last_inference_device = _format_device_name(
                getattr(output, "device", "")
            )
            self.last_inference_mode = "cpu-fallback"
            return output.numpy()

    def _log_prediction_probe(self, sequence, prediction):
        probs = prediction[0]
        top_indices = probs.argsort()[-3:][::-1]
        print("RAW_TOP3:", [(self.index_to_label.get(int(i), "Unknown"), float(probs[i])) for i in top_indices])
        print("MAX_CONF:", float(probs[top_indices[0]]))
        print("THRESHOLD:", THRESHOLD)
        print("INPUT_SHAPE:", sequence.shape)
        print(
            "INPUT_MIN_MAX_MEAN:",
            float(sequence.min()),
            float(sequence.max()),
            float(sequence.mean()),
        )

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
        return LandmarkExtractor.extract_features(self._feature_extractor, mp_bundle)

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

        prediction = self._run_inference(np.expand_dims(seq, axis=0))
        self._log_prediction_probe(seq, prediction)

        result = prediction[0]

        index = int(np.argmax(result))
        confidence = float(result[index])
        label = self.index_to_label.get(index, "Unknown")

        self.last_raw_label = label
        self.last_raw_confidence = confidence

        return label, confidence

    def _raw_inference_from_sequence(self, frames_array):
        """
        Run inference directly on a frames array.
        
        Args:
            frames_array: shape (1, FRAMES, FEATURES_PER_FRAME) or (FRAMES, FEATURES_PER_FRAME)
        
        Returns:
            (label, confidence)
        """
        if frames_array.ndim == 2:
            # (FRAMES, FEATURES_PER_FRAME) -> add batch dimension
            frames_array = np.expand_dims(frames_array, axis=0)
        
        sequence = frames_array[0]
        prediction = self._run_inference(frames_array)
        self._log_prediction_probe(sequence, prediction)

        result = prediction[0]

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

        # Reset feature smoothing/interpolation memory between sessions.
        self._feature_extractor = self._build_feature_extractor()

    def close(self):
        pass