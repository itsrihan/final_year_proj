# backend/debug/debug.py

import os
import sys

import cv2

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.dirname(CURRENT_DIR)

if BACKEND_DIR not in sys.path:
    sys.path.append(BACKEND_DIR)

from core.config import (
    FEATURES_PER_FRAME,
    FRAMES,
    PHRASE_DATA_DIR,
    PHRASE_LABELS_PATH,
    PHRASE_MODEL_PATH,
)
from core.drawing import (
    draw_debug_text,
    draw_face_subset,
    draw_hands,
    draw_pose_subset,
)
from core.landmarks import LandmarkExtractor
from predictor import PhrasePredictor


def open_camera():
    indices_to_try = [0, 1, 2, 3]
    candidates = []

    if os.name == "nt":
        candidates.extend((idx, cv2.CAP_DSHOW) for idx in indices_to_try)

    candidates.extend((idx, None) for idx in indices_to_try)

    for idx, backend in candidates:
        cap = cv2.VideoCapture(idx, backend) if backend is not None else cv2.VideoCapture(idx)

        if cap.isOpened():
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
            return cap, idx

        cap.release()

    return None, None


def hands_detected(mp_bundle):
    return (
        mp_bundle.hands_results is not None
        and mp_bundle.hands_results.multi_hand_landmarks is not None
        and len(mp_bundle.hands_results.multi_hand_landmarks) > 0
    )


def hands_count(mp_bundle):
    if (
        mp_bundle.hands_results is not None
        and mp_bundle.hands_results.multi_hand_landmarks is not None
    ):
        return len(mp_bundle.hands_results.multi_hand_landmarks)

    return 0


def draw_hand_boxes(frame, hands_results):
    if hands_results is None:
        return

    if not hands_results.multi_hand_landmarks:
        return

    h, w, _ = frame.shape

    for hand_landmarks in hands_results.multi_hand_landmarks:
        xs = [int(lm.x * w) for lm in hand_landmarks.landmark]
        ys = [int(lm.y * h) for lm in hand_landmarks.landmark]

        x1 = max(min(xs) - 25, 0)
        y1 = max(min(ys) - 25, 0)
        x2 = min(max(xs) + 25, w)
        y2 = min(max(ys) + 25, h)

        cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)


def draw_prediction_panel(frame, label, confidence, status_lines):
    panel_x1, panel_y1 = 20, 210
    panel_x2, panel_y2 = 760, 430

    cv2.rectangle(frame, (panel_x1, panel_y1), (panel_x2, panel_y2), (0, 0, 0), -1)
    cv2.rectangle(frame, (panel_x1, panel_y1), (panel_x2, panel_y2), (0, 255, 0), 2)

    cv2.putText(
        frame,
        f"{label}  {confidence * 100:.1f}%",
        (40, 260),
        cv2.FONT_HERSHEY_SIMPLEX,
        1.1,
        (0, 255, 0),
        3,
    )

    y = 300
    for line in status_lines:
        cv2.putText(
            frame,
            line,
            (40, y),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.65,
            (230, 230, 230),
            2,
        )
        y += 28


def main():
    cap, camera_index = open_camera()

    if cap is None:
        print("Could not open webcam.")
        return

    print(f"Using webcam index: {camera_index}")
    print(f"Features per frame expected: {FEATURES_PER_FRAME}")
    print(f"Frames expected: {FRAMES}")
    print(f"Model path: {PHRASE_MODEL_PATH}")
    print(f"Labels path: {PHRASE_LABELS_PATH}")

    extractor = LandmarkExtractor()

    predictor = PhrasePredictor(
        model_path=PHRASE_MODEL_PATH,
        labels_path=PHRASE_LABELS_PATH,
        data_dir=PHRASE_DATA_DIR,
    )

    draw_all = True
    draw_hands_on = True
    draw_pose_on = True
    draw_face_on = True

    latest_label = "Waiting..."
    latest_confidence = 0.0
    feature_len = 0

    try:
        while True:
            ret, frame = cap.read()

            if not ret:
                print("Failed to read frame from webcam.")
                break

            frame = cv2.flip(frame, 1)

            mp_bundle = extractor.process_frame(frame)
            detected = hands_detected(mp_bundle)

            try:
                features = extractor.extract_features(mp_bundle)
                feature_len = len(features)

                latest_label, latest_confidence = predictor.predict(
                    mp_bundle,
                    hands_detected=detected,
                )

            except Exception as e:
                feature_len = -1
                latest_label = "Error"
                latest_confidence = 0.0
                print("Error:", str(e))

            debug_info = predictor.get_debug_info()

            status_lines = [
                f"state: {debug_info['state']}",
                f"sequence: {debug_info['sequence_len']}/{FRAMES}",
                f"votes: {debug_info['vote_len']}",
                f"raw: {debug_info['last_raw_label']} {debug_info['last_raw_confidence'] * 100:.1f}%",
                f"hands: {hands_count(mp_bundle)} | detected: {detected}",
                f"device: {debug_info['inference_device']} | mode: {debug_info['inference_mode']}",
            ]

            display = frame.copy()

            if draw_all or draw_hands_on:
                draw_hands(display, mp_bundle.hands_results)

            if draw_all or draw_pose_on:
                draw_pose_subset(display, mp_bundle.pose_results)

            if draw_all or draw_face_on:
                draw_face_subset(display, mp_bundle.face_results)

            draw_hand_boxes(display, mp_bundle.hands_results)

            draw_debug_text(
                display,
                feature_len=feature_len,
                draw_all=draw_all,
                draw_hands_on=draw_hands_on,
                draw_pose_on=draw_pose_on,
                draw_face_on=draw_face_on,
            )

            draw_prediction_panel(
                display,
                latest_label,
                latest_confidence,
                status_lines,
            )

            cv2.imshow("ASL Debug Capture - Real Predictor Engine", display)

            key = cv2.waitKey(1) & 0xFF

            if key == ord("q"):
                break
            elif key == ord("d"):
                draw_all = not draw_all
            elif key == ord("h"):
                draw_hands_on = not draw_hands_on
            elif key == ord("p"):
                draw_pose_on = not draw_pose_on
            elif key == ord("f"):
                draw_face_on = not draw_face_on
            elif key == ord("r"):
                predictor.reset()
                latest_label = "Reset"
                latest_confidence = 0.0

    finally:
        cap.release()
        predictor.close()
        extractor.close()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()