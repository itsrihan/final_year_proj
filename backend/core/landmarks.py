# backend/core/landmarks.py

from dataclasses import dataclass

import cv2
import mediapipe as mp
import numpy as np

from core.config import FACE_LANDMARKS, FEATURES_PER_FRAME, POSE_LANDMARKS

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
        self.hands = mp_hands.Hands(
            static_image_mode=False,
            max_num_hands=2,
            model_complexity=0,
            min_detection_confidence=0.25,
            min_tracking_confidence=0.25,
)

        self.pose = mp_pose.Pose(
            static_image_mode=False,
            model_complexity=0,
            smooth_landmarks=True,
            enable_segmentation=False,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5,
        )

        self.face_mesh = mp_face_mesh.FaceMesh(
            static_image_mode=False,
            max_num_faces=1,
            refine_landmarks=False,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5,
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
        features = []

        if hands_results and hands_results.multi_hand_landmarks:
            hand_list = hands_results.multi_hand_landmarks[:2]

            for hand_landmarks in hand_list:
                for lm in hand_landmarks.landmark:
                    xyz = np.array([lm.x, lm.y, lm.z], dtype=np.float32)
                    xyz = self._normalize_xyz(xyz, anchor, scale)
                    features.extend(xyz.tolist())

            while len(hand_list) < 2:
                features.extend([0.0] * 63)
                hand_list.append(None)
        else:
            features.extend([0.0] * 126)

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

    def extract_features(self, mp_bundle):
        anchor, scale = self._get_pose_anchor_and_scale(mp_bundle.pose_results)

        hand_features = self.extract_hand_features(mp_bundle.hands_results, anchor, scale)
        pose_features = self.extract_pose_features(mp_bundle.pose_results, anchor, scale)
        face_features = self.extract_face_features(mp_bundle.face_results, anchor, scale)

        features = hand_features + pose_features + face_features
        features = np.asarray(features, dtype=np.float32)

        if features.shape[0] != FEATURES_PER_FRAME:
            raise RuntimeError(
                f"Feature size mismatch. Got {features.shape[0]}, expected {FEATURES_PER_FRAME}"
            )

        return features