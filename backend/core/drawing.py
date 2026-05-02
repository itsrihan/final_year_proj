# backend/core/drawing.py

import cv2
import mediapipe as mp

from core.config import FACE_LANDMARKS, FEATURES_PER_FRAME, POSE_LANDMARKS

mp_draw = mp.solutions.drawing_utils
mp_hands = mp.solutions.hands
mp_pose = mp.solutions.pose


def draw_hands(image, hands_results):
    if hands_results is None:
        return

    if not hands_results.multi_hand_landmarks:
        return

    for hand_landmarks in hands_results.multi_hand_landmarks:
        mp_draw.draw_landmarks(
            image,
            hand_landmarks,
            mp_hands.HAND_CONNECTIONS,
        )


def draw_pose_subset(image, pose_results):
    if pose_results is None:
        return

    if not pose_results.pose_landmarks:
        return

    pose_landmarks = pose_results.pose_landmarks.landmark
    h, w, _ = image.shape

    for landmark_name in POSE_LANDMARKS:
        idx = POSE_LANDMARKS[landmark_name]
        lm = pose_landmarks[idx]
        x = int(lm.x * w)
        y = int(lm.y * h)
        cv2.circle(image, (x, y), 5, (0, 200, 255), -1)

    pairs = [
        ("left_shoulder", "right_shoulder"),
        ("left_shoulder", "left_elbow"),
        ("left_elbow", "left_wrist"),
        ("right_shoulder", "right_elbow"),
        ("right_elbow", "right_wrist"),
    ]

    for a_name, b_name in pairs:
        a = pose_landmarks[POSE_LANDMARKS[a_name]]
        b = pose_landmarks[POSE_LANDMARKS[b_name]]
        ax, ay = int(a.x * w), int(a.y * h)
        bx, by = int(b.x * w), int(b.y * h)
        cv2.line(image, (ax, ay), (bx, by), (0, 180, 255), 2)


def draw_face_subset(image, face_results):
    if face_results is None:
        return

    if not face_results.multi_face_landmarks:
        return

    face_landmarks = face_results.multi_face_landmarks[0].landmark
    h, w, _ = image.shape

    for landmark_name in FACE_LANDMARKS:
        idx = FACE_LANDMARKS[landmark_name]
        lm = face_landmarks[idx]
        x = int(lm.x * w)
        y = int(lm.y * h)
        cv2.circle(image, (x, y), 2, (255, 120, 0), -1)


def draw_debug_text(
    image,
    feature_len,
    draw_all,
    draw_hands_on,
    draw_pose_on,
    draw_face_on,
):
    panel_x1, panel_y1 = 15, 15
    panel_x2, panel_y2 = 620, 190
    cv2.rectangle(image, (panel_x1, panel_y1), (panel_x2, panel_y2), (30, 30, 30), -1)

    lines = [
        "DEBUG VIEW",
        f"features/frame: {feature_len} / {FEATURES_PER_FRAME}",
        f"draw all: {draw_all}",
        f"draw hands: {draw_hands_on}",
        f"draw pose: {draw_pose_on}",
        f"draw face: {draw_face_on}",
        "keys: q quit | r reset | d all | h hands | p pose | f face",
    ]

    y = 42
    for i, line in enumerate(lines):
        scale = 0.8 if i == 0 else 0.65
        thickness = 2 if i == 0 else 1
        color = (255, 255, 255) if i == 0 else (220, 220, 220)
        cv2.putText(
            image,
            line,
            (28, y),
            cv2.FONT_HERSHEY_SIMPLEX,
            scale,
            color,
            thickness,
        )
        y += 25