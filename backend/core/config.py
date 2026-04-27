# backend/core/config.py

import os

FRAMES = 24

# Confidence threshold will matter later during prediction
THRESHOLD = 0.50

# Pose landmarks we actually care about
POSE_LANDMARKS = {
    "left_shoulder": 11,
    "right_shoulder": 12,
    "left_elbow": 13,
    "right_elbow": 14,
    "left_wrist": 15,
    "right_wrist": 16,
}

# Compact face subset
# These are selected useful facial points for expression/mouth context
# You can refine these later, but lock them BEFORE data collection
FACE_LANDMARKS = {
    "nose_tip": 1,
    "left_mouth_corner": 61,
    "right_mouth_corner": 291,
    "upper_lip_center": 13,
    "lower_lip_center": 14,
    "upper_lip_left": 37,
    "upper_lip_right": 267,
    "lower_lip_left": 84,
    "lower_lip_right": 314,
    "chin_center": 152,
    "left_cheek": 234,
    "right_cheek": 454,
    "left_eyebrow_inner": 70,
    "right_eyebrow_inner": 300,
    "philtrum": 0,
}

HAND_LANDMARKS_PER_HAND = 21
HAND_FEATURES_PER_HAND = HAND_LANDMARKS_PER_HAND * 3
TOTAL_HAND_FEATURES = HAND_FEATURES_PER_HAND * 2  # 126

POSE_FEATURES = len(POSE_LANDMARKS) * 4  # x, y, z, visibility
FACE_FEATURES = len(FACE_LANDMARKS) * 3  # x, y, z

FEATURES_PER_FRAME = TOTAL_HAND_FEATURES + POSE_FEATURES + FACE_FEATURES

# Centralized backend paths for model artifacts and phrase dataset.
BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJECT_ROOT = os.path.dirname(BACKEND_DIR)

PHRASE_MODEL_PATH = os.path.join(BACKEND_DIR, "models", "phrase_lstm.keras")
PHRASE_LABELS_PATH = os.path.join(BACKEND_DIR, "models", "phrase_labels.json")
PHRASE_DATA_DIR = os.path.join(PROJECT_ROOT, "data", "phrases")