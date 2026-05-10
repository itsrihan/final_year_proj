#landmarks.py - Extracts and normalizes MediaPipe hand, pose, and face landmarks into a fixed-size feature vector per frame. Implements smoothing and interpolation to handle hand tracking dropouts gracefully.

from dataclasses import dataclass

import cv2
import mediapipe as mp
import numpy as np

from core.config import (
    FACE_LANDMARKS,
    FEATURES_PER_FRAME,
    HAND_MAX_INTERP_FRAMES,
    HAND_SMOOTH_ALPHA,
    POSE_LANDMARKS,
)
from core.config import HAND_FEATURES_PER_HAND, TOTAL_HAND_FEATURES

mp_hands = mp.solutions.hands
mp_pose = mp.solutions.pose
mp_face_mesh = mp.solutions.face_mesh


@dataclass
class MediaPipeBundle:
    hands_results: object
    pose_results: object
    face_results: object


class LandmarkExtractor:
    def __init__(self):
        # --- Smoothing and interpolation state ---
        # Exponential smoothing alpha: 0 = fully smooth, 1 = no smoothing
        self._smooth_alpha = HAND_SMOOTH_ALPHA

        # Last known good hand features (used for interpolation)
        self._prev_hand_features = None

        # Raw hand features from last frame hands were actually detected
        # Used as the interpolation start point
        self._last_detected_hand_features = None

        # How many consecutive frames hands have been lost
        self._hand_dropout_frames = 0

        # Max frames to interpolate across before giving up and zeroing out
        self._max_interp_frames = HAND_MAX_INTERP_FRAMES

        # FIX: model_complexity matched to collection (1 not 0)
        # FIX: confidence thresholds matched to collection file
        self.hands = mp_hands.Hands(
            static_image_mode=False,
            max_num_hands=2,
            model_complexity=1,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.4,
        )

        self.pose = mp_pose.Pose(
            static_image_mode=False,
            model_complexity=1,
            smooth_landmarks=True,
            enable_segmentation=False,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.4,
        )

        self.face_mesh = mp_face_mesh.FaceMesh(
            static_image_mode=False,
            max_num_faces=1,
            refine_landmarks=False,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.4,
        )

    def process_frame(self, frame_bgr):
        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        rgb.flags.writeable = False

        hands_results = self.hands.process(rgb)
        pose_results = self.pose.process(rgb)
        face_results = self.face_mesh.process(rgb)

        rgb.flags.writeable = True

        return MediaPipeBundle(
            hands_results=hands_results,
            pose_results=pose_results,
            face_results=face_results,
        )

    def close(self):
        self.hands.close()
        self.pose.close()
        self.face_mesh.close()

    def _get_pose_anchor_and_scale(self, pose_results):
        if not pose_results or not pose_results.pose_landmarks:
            return None, None

        lm = pose_results.pose_landmarks.landmark
        left_shoulder = lm[POSE_LANDMARKS["left_shoulder"]]
        right_shoulder = lm[POSE_LANDMARKS["right_shoulder"]]

        anchor = np.array(
            [
                (left_shoulder.x + right_shoulder.x) / 2.0,
                (left_shoulder.y + right_shoulder.y) / 2.0,
                (left_shoulder.z + right_shoulder.z) / 2.0,
            ],
            dtype=np.float32,
        )

        shoulder_width = np.linalg.norm(
            np.array(
                [
                    left_shoulder.x - right_shoulder.x,
                    left_shoulder.y - right_shoulder.y,
                    left_shoulder.z - right_shoulder.z,
                ],
                dtype=np.float32,
            )
        )

        if shoulder_width < 1e-6:
            shoulder_width = 1.0

        return anchor, shoulder_width

    def _normalize_xyz(self, xyz, anchor, scale):
        if anchor is None or scale is None:
            return xyz.astype(np.float32)
        return ((xyz - anchor) / scale).astype(np.float32)

    def extract_hand_features(self, hands_results, anchor, scale):
        # FIX: old code appended None to hand_list causing iteration bugs.
        # Now builds clean list and pads separately.
        hands_data = []

        if hands_results and hands_results.multi_hand_landmarks:
            for hand_landmarks in hands_results.multi_hand_landmarks[:2]:
                hand_features = []
                for lm in hand_landmarks.landmark:
                    xyz = np.array([lm.x, lm.y, lm.z], dtype=np.float32)
                    xyz = self._normalize_xyz(xyz, anchor, scale)
                    hand_features.extend(xyz.tolist())
                hands_data.append(hand_features)

        # Pad missing hands with zeros
        while len(hands_data) < 2:
            hands_data.append([0.0] * HAND_FEATURES_PER_HAND)

        features = []
        for hand in hands_data:
            features.extend(hand)

        return features

    def extract_pose_features(self, pose_results, anchor, scale):
        features = []

        if pose_results and pose_results.pose_landmarks:
            landmarks = pose_results.pose_landmarks.landmark

            for landmark_name in POSE_LANDMARKS:
                idx = POSE_LANDMARKS[landmark_name]
                lm = landmarks[idx]

                xyz = np.array([lm.x, lm.y, lm.z], dtype=np.float32)
                xyz = self._normalize_xyz(xyz, anchor, scale)

                features.extend(xyz.tolist())
                features.append(float(lm.visibility))
        else:
            features.extend([0.0] * (len(POSE_LANDMARKS) * 4))

        return features

    def extract_face_features(self, face_results, anchor, scale):
        features = []

        if face_results and face_results.multi_face_landmarks:
            face_landmarks = face_results.multi_face_landmarks[0].landmark

            for landmark_name in FACE_LANDMARKS:
                idx = FACE_LANDMARKS[landmark_name]
                lm = face_landmarks[idx]

                xyz = np.array([lm.x, lm.y, lm.z], dtype=np.float32)
                xyz = self._normalize_xyz(xyz, anchor, scale)

                features.extend(xyz.tolist())
        else:
            features.extend([0.0] * (len(FACE_LANDMARKS) * 3))

        return features

    def _apply_hand_smoothing(self, features, hands_detected):
        """
        Two-stage hand smoothing:

        Stage 1 - Exponential smoothing (always active when hands detected):
            Blends current frame with previous to reduce per-frame jitter.
            formula: output = alpha * current + (1 - alpha) * previous

        Stage 2 - Linear interpolation across dropout frames:
            When hands are briefly lost (fast movement), instead of snapping
            to zeros, we bridge from the last known position toward zeros
            over _max_interp_frames frames. This fills the gap caused by
            MediaPipe losing tracking mid-motion.

            t=0 (last detected) ... t=1 (max_interp_frames reached) -> zeros
            Each dropout frame moves t forward proportionally.
        """
        hand_len = TOTAL_HAND_FEATURES
        current_hand = features[:hand_len].copy()

        if hands_detected:
            # Reset dropout counter - hands are visible again
            self._hand_dropout_frames = 0

            if self._prev_hand_features is not None:
                # Stage 1: exponential smoothing over jitter
                smoothed = (
                    self._smooth_alpha * current_hand
                    + (1.0 - self._smooth_alpha) * self._prev_hand_features
                )
            else:
                smoothed = current_hand

            self._prev_hand_features = smoothed.copy()
            self._last_detected_hand_features = smoothed.copy()
            features[:hand_len] = smoothed

        else:
            # Hands not detected this frame
            self._hand_dropout_frames += 1

            if (
                self._last_detected_hand_features is not None
                and self._hand_dropout_frames <= self._max_interp_frames
            ):
                # Stage 2: interpolate from last known position toward zeros
                # t goes from 0 (just lost) to 1 (max gap reached)
                t = self._hand_dropout_frames / self._max_interp_frames
                interpolated = (
                    (1.0 - t) * self._last_detected_hand_features
                )
                self._prev_hand_features = interpolated.copy()
                features[:hand_len] = interpolated
            else:
                # Gap too long or no prior detection - genuine absence, zero out
                self._prev_hand_features = None
                self._last_detected_hand_features = None
                features[:hand_len] = 0.0

        return features

    def extract_features(self, mp_bundle):
        anchor, scale = self._get_pose_anchor_and_scale(mp_bundle.pose_results)

        hand_features = self.extract_hand_features(mp_bundle.hands_results, anchor, scale)
        pose_features = self.extract_pose_features(mp_bundle.pose_results, anchor, scale)
        face_features = self.extract_face_features(mp_bundle.face_results, anchor, scale)

        features = hand_features + pose_features + face_features
        features = np.asarray(features, dtype=np.float32)

        # Determine if hands were actually detected this frame
        hands_detected = (
            mp_bundle.hands_results is not None
            and mp_bundle.hands_results.multi_hand_landmarks is not None
        )

        features = self._apply_hand_smoothing(features, hands_detected)

        if features.shape[0] != FEATURES_PER_FRAME:
            raise RuntimeError(
                f"Feature size mismatch. Got {features.shape[0]}, expected {FEATURES_PER_FRAME}"
            )

        return features