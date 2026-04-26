# backend/debug/debug_capture.py

import os
import sys

import cv2

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.dirname(CURRENT_DIR)

if BACKEND_DIR not in sys.path:
    sys.path.append(BACKEND_DIR)

from core.config import FEATURES_PER_FRAME
from core.drawing import (
    draw_debug_text,
    draw_face_subset,
    draw_hands,
    draw_pose_subset,
)
from core.landmarks import LandmarkExtractor


def open_camera():
    indices_to_try = [0, 1, 2, 3]
    candidates = []

    # Prefer DirectShow on Windows for more reliable webcam open/read behavior.
    if os.name == "nt":
        candidates.extend((idx, cv2.CAP_DSHOW) for idx in indices_to_try)

    candidates.extend((idx, None) for idx in indices_to_try)

    for idx, backend in candidates:
        cap = cv2.VideoCapture(idx, backend) if backend is not None else cv2.VideoCapture(idx)
        if cap.isOpened():
            return cap, idx
        cap.release()

    return None, None


def main():
    cap, camera_index = open_camera()

    if cap is None:
        print("Could not open webcam.")
        return

    print(f"Using webcam index: {camera_index}")

    extractor = LandmarkExtractor()

    draw_all = True
    draw_hands_on = True
    draw_pose_on = True
    draw_face_on = True

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                print("Failed to read frame from webcam.")
                break

            frame = cv2.flip(frame, 1)

            mp_bundle = extractor.process_frame(frame)

            try:
                features = extractor.extract_features(mp_bundle)
                feature_len = len(features)
            except Exception as e:
                feature_len = -1
                cv2.putText(
                    frame,
                    f"Feature extraction error: {str(e)}",
                    (20, frame.shape[0] - 20),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.6,
                    (0, 0, 255),
                    2,
                )

            display = frame.copy()

            if draw_all or draw_hands_on:
                draw_hands(display, mp_bundle.hands_results)

            if draw_all or draw_pose_on:
                draw_pose_subset(display, mp_bundle.pose_results)

            if draw_all or draw_face_on:
                draw_face_subset(display, mp_bundle.face_results)

            draw_debug_text(
                display,
                feature_len=feature_len,
                draw_all=draw_all,
                draw_hands_on=draw_hands_on,
                draw_pose_on=draw_pose_on,
                draw_face_on=draw_face_on,
            )

            cv2.imshow("ASL Debug Capture", display)

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

    finally:
        cap.release()
        extractor.close()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()