import json
import os
import sys
import time
from pathlib import Path

import cv2
import numpy as np

CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parent
BACKEND_DIR = PROJECT_ROOT / "backend"
DATASET_DIR = PROJECT_ROOT / "dataset" / "phrases"
PHRASES_FILE = CURRENT_DIR / "phrases.json"

if str(BACKEND_DIR) not in sys.path:
    sys.path.append(str(BACKEND_DIR))

from core.config import FEATURES_PER_FRAME, FRAMES
from core.drawing import draw_face_subset, draw_hands, draw_pose_subset
from core.landmarks import LandmarkExtractor


class SequenceCollector:
    def __init__(self, phrases, dataset_dir):
        self.phrases = phrases
        self.dataset_dir = Path(dataset_dir)
        self.dataset_dir.mkdir(parents=True, exist_ok=True)

        self.current_phrase_index = 0
        self.recording = False
        self.current_sequence = []
        self.draw_overlays = True
        self.auto_advance_phrase = False

        self.countdown_active = False
        self.countdown_start = 0.0
        self.countdown_seconds = 1

        self.last_saved_file = ""
        self.status_message = "Ready"
        self.feature_len = 0

        self.extractor = LandmarkExtractor()

    @property
    def current_phrase(self):
        return self.phrases[self.current_phrase_index]

    def get_phrase_dir(self):
        phrase_dir = self.dataset_dir / self.current_phrase
        phrase_dir.mkdir(parents=True, exist_ok=True)
        return phrase_dir

    def get_next_sample_index(self):
        phrase_dir = self.get_phrase_dir()
        existing = [p for p in phrase_dir.glob("*.npy") if p.is_file()]
        numeric_stems = []

        for path in existing:
            try:
                numeric_stems.append(int(path.stem))
            except ValueError:
                continue

        return 0 if not numeric_stems else max(numeric_stems) + 1

    def start_countdown(self):
        if self.recording or self.countdown_active:
            return
        self.countdown_active = True
        self.countdown_start = time.time()
        self.current_sequence = []
        self.status_message = f"Get ready for '{self.current_phrase}'"

    def start_recording(self):
        self.recording = True
        self.countdown_active = False
        self.current_sequence = []
        self.status_message = f"Recording '{self.current_phrase}'..."

    def cancel_recording(self):
        self.recording = False
        self.countdown_active = False
        self.current_sequence = []
        self.status_message = "Recording cancelled"

    def save_sequence(self):
        if len(self.current_sequence) != FRAMES:
            self.status_message = f"Cannot save. Sequence has {len(self.current_sequence)} / {FRAMES} frames"
            self.recording = False
            self.current_sequence = []
            return

        sequence_array = np.asarray(self.current_sequence, dtype=np.float32)

        if sequence_array.shape != (FRAMES, FEATURES_PER_FRAME):
            self.status_message = (
                f"Invalid shape {sequence_array.shape}, expected ({FRAMES}, {FEATURES_PER_FRAME})"
            )
            self.recording = False
            self.current_sequence = []
            return

        sample_index = self.get_next_sample_index()
        output_path = self.get_phrase_dir() / f"{sample_index}.npy"
        np.save(output_path, sequence_array)

        self.last_saved_file = str(output_path)
        self.status_message = f"Saved sample {sample_index} for '{self.current_phrase}'"
        self.recording = False
        self.current_sequence = []

        if self.auto_advance_phrase:
            self.next_phrase()

    def next_phrase(self):
        self.current_phrase_index = (self.current_phrase_index + 1) % len(self.phrases)
        self.cancel_recording()
        self.status_message = f"Switched to '{self.current_phrase}'"

    def prev_phrase(self):
        self.current_phrase_index = (self.current_phrase_index - 1) % len(self.phrases)
        self.cancel_recording()
        self.status_message = f"Switched to '{self.current_phrase}'"

    def count_samples_for_phrase(self, phrase):
        phrase_dir = self.dataset_dir / phrase
        if not phrase_dir.exists():
            return 0
        return len(list(phrase_dir.glob("*.npy")))

    def process_frame(self, frame):
        frame = cv2.flip(frame, 1)
        mp_bundle = self.extractor.process_frame(frame)
        features = self.extractor.extract_features(mp_bundle)
        self.feature_len = len(features)

        display = frame.copy()

        if self.draw_overlays:
            draw_hands(display, mp_bundle.hands_results)
            draw_pose_subset(display, mp_bundle.pose_results)
            draw_face_subset(display, mp_bundle.face_results)

        self.draw_ui(display)

        if self.countdown_active:
            elapsed = time.time() - self.countdown_start
            remaining = self.countdown_seconds - elapsed

            if remaining > 0:
                self.draw_countdown(display, int(np.ceil(remaining)))
            else:
                self.start_recording()

        if self.recording:
            self.current_sequence.append(features)
            self.current_sequence = self.current_sequence[:FRAMES]

            if len(self.current_sequence) >= FRAMES:
                self.save_sequence()

        return display

    def draw_countdown(self, image, seconds_left):
        text = str(seconds_left)
        h, w, _ = image.shape
        font = cv2.FONT_HERSHEY_SIMPLEX
        scale = 4
        thickness = 8
        (text_w, text_h), _ = cv2.getTextSize(text, font, scale, thickness)
        x = (w - text_w) // 2
        y = (h + text_h) // 2
        cv2.putText(image, text, (x, y), font, scale, (0, 255, 255), thickness)

    def draw_ui(self, image):
        pass

    def build_status_panel(self):
        panel = np.zeros((420, 520, 3), dtype=np.uint8)
        panel[:] = (25, 25, 25)

        phrase_count = self.count_samples_for_phrase(self.current_phrase)

        lines = [
            "DATA COLLECTION",
            f"Phrase: {self.current_phrase}",
            f"Samples: {phrase_count}",
            f"Features: {self.feature_len}/{FEATURES_PER_FRAME}",
            f"Recording: {self.recording}",
            f"Frames: {len(self.current_sequence)}/{FRAMES}",
            f"Draw: {self.draw_overlays}",
            f"Auto-next: {self.auto_advance_phrase}",
            f"Status: {self.status_message}",
            "",
            "SPACE start",
            "r reset",
            "n next | p prev",
            "d draw toggle",
            "a auto toggle",
            "q quit",
        ]

        y = 40
        for i, line in enumerate(lines):
            scale = 0.8 if i == 0 else 0.6
            thickness = 2 if i == 0 else 1
            cv2.putText(
                panel,
                line,
                (20, y),
                cv2.FONT_HERSHEY_SIMPLEX,
                scale,
                (255, 255, 255),
                thickness,
            )
            y += 26

        if self.last_saved_file:
            cv2.putText(
                panel,
                "Saved OK",
                (20, y + 10),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.55,
                (100, 255, 100),
                1,
            )

        return panel


def load_phrases():
    if not PHRASES_FILE.exists():
        raise FileNotFoundError(f"Missing phrases file: {PHRASES_FILE}")

    with open(PHRASES_FILE, "r", encoding="utf-8") as f:
        phrases = json.load(f)

    if not isinstance(phrases, list) or not phrases:
        raise ValueError("phrases.json must contain a non-empty list of phrases")

    cleaned = [str(p).strip() for p in phrases if str(p).strip()]
    if not cleaned:
        raise ValueError("phrases.json contains no valid phrases")

    return cleaned


def main():
    phrases = load_phrases()
    collector = SequenceCollector(phrases, DATASET_DIR)

    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("Could not open webcam.")
        return

    print("Starting data collection...")
    print(f"Phrases: {phrases}")
    print(f"Saving to: {DATASET_DIR}")
    print(f"Expected sample shape: ({FRAMES}, {FEATURES_PER_FRAME})")

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                print("Failed to read frame from webcam.")
                break

            try:
                display = collector.process_frame(frame)
            except Exception as e:
                display = cv2.flip(frame, 1)
                cv2.rectangle(display, (10, 10), (900, 80), (20, 20, 20), -1)
                cv2.putText(
                    display,
                    f"Processing error: {str(e)}",
                    (24, 50),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.7,
                    (0, 0, 255),
                    2,
                )

            cv2.imshow("ASL Data Collection", display)

            status_panel = collector.build_status_panel()
            cv2.imshow("ASL Data Status", status_panel)

            key = cv2.waitKey(1) & 0xFF

            if key == ord("q"):
                break
            elif key == ord(" "):
                collector.start_countdown()
            elif key == ord("r"):
                collector.cancel_recording()
            elif key == ord("n"):
                collector.next_phrase()
            elif key == ord("p"):
                collector.prev_phrase()
            elif key == ord("d"):
                collector.draw_overlays = not collector.draw_overlays
                collector.status_message = f"Draw overlays set to {collector.draw_overlays}"
            elif key == ord("a"):
                collector.auto_advance_phrase = not collector.auto_advance_phrase
                collector.status_message = f"Auto-advance set to {collector.auto_advance_phrase}"

    finally:
        cap.release()
        collector.close()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()