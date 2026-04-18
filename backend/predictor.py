import json
import os
from functools import lru_cache

import numpy as np
import tensorflow as tf
from tensorflow import keras
from tensorflow.keras.models import load_model

from core.config import FEATURES_PER_FRAME, FRAMES, THRESHOLD
from core.landmarks import MediaPipeBundle


def _is_valid_artifact(path):
    return os.path.exists(path) and os.path.getsize(path) > 0


def _load_label_map(labels_path):
    if not _is_valid_artifact(labels_path):
        return None

    try:
        with open(labels_path, "r", encoding="utf-8") as file_handle:
            label_map = json.load(file_handle)
    except (OSError, json.JSONDecodeError):
        return None

    if not isinstance(label_map, dict) or not label_map:
        return None

    return {str(label): int(index) for label, index in label_map.items()}


def _normalize_sequence(sequence):
    array = np.asarray(sequence, dtype=np.float32)

    if array.ndim != 2:
        return None

    normalized = np.zeros((FRAMES, FEATURES_PER_FRAME), dtype=np.float32)
    frame_count = min(array.shape[0], FRAMES)
    feature_count = min(array.shape[1], FEATURES_PER_FRAME)
    normalized[:frame_count, :feature_count] = array[:frame_count, :feature_count]
    return normalized


def _load_training_data(data_dir):
    sequences = []
    labels = []

    if not os.path.isdir(data_dir):
        return (
            np.empty((0, FRAMES, FEATURES_PER_FRAME), dtype=np.float32),
            np.empty((0,), dtype=np.int32),
            [],
        )

    for phrase_name in sorted(os.listdir(data_dir)):
        phrase_dir = os.path.join(data_dir, phrase_name)
        if not os.path.isdir(phrase_dir):
            continue

        phrase_files = sorted(
            [f for f in os.listdir(phrase_dir) if f.endswith(".npy")],
            key=lambda f: int(os.path.splitext(f)[0]) if os.path.splitext(f)[0].isdigit() else f,
        )

        for file_name in phrase_files:
            file_path = os.path.join(phrase_dir, file_name)
            try:
                sequence = np.load(file_path, allow_pickle=False)
            except Exception:
                continue

            normalized = _normalize_sequence(sequence)
            if normalized is None:
                continue

            sequences.append(normalized)
            labels.append(phrase_name)

    if not sequences:
        return (
            np.empty((0, FRAMES, FEATURES_PER_FRAME), dtype=np.float32),
            np.empty((0,), dtype=np.int32),
            [],
        )

    label_names = sorted(set(labels))
    label_to_index = {label: index for index, label in enumerate(label_names)}

    x_values = np.asarray(sequences, dtype=np.float32)
    y_values = np.array([label_to_index[label] for label in labels], dtype=np.int32)

    return x_values, y_values, label_names


def _build_model(num_classes):
    model = keras.Sequential(
        [
            keras.layers.Input(shape=(FRAMES, FEATURES_PER_FRAME)),
            keras.layers.Masking(mask_value=0.0),
            keras.layers.LSTM(64, return_sequences=False),
            keras.layers.Dense(32, activation="relu"),
            keras.layers.Dropout(0.2),
            keras.layers.Dense(num_classes, activation="softmax"),
        ]
    )

    model.compile(
        optimizer="adam",
        loss="sparse_categorical_crossentropy",
        metrics=["accuracy"],
    )
    return model


def _save_label_map(labels_path, label_names):
    labels_dir = os.path.dirname(labels_path)
    if labels_dir:
        os.makedirs(labels_dir, exist_ok=True)

    label_map = {label: index for index, label in enumerate(label_names)}

    with open(labels_path, "w", encoding="utf-8") as file_handle:
        json.dump(label_map, file_handle, indent=2)

    return label_map


def _train_phrase_model(model_path, labels_path, data_dir):
    x_values, y_values, label_names = _load_training_data(data_dir)

    if x_values.size == 0 or y_values.size == 0 or not label_names:
        raise RuntimeError(
            "No valid phrase training data found in data/phrases. "
            "Each class folder must contain .npy sequences shaped like (frames, 195)."
        )

    model = _build_model(len(label_names))

    callbacks = [
        keras.callbacks.EarlyStopping(
            monitor="val_loss",
            patience=5,
            restore_best_weights=True,
        )
    ]

    validation_split = 0.2 if len(x_values) >= 10 else 0.0

    model.fit(
        x_values,
        y_values,
        epochs=25,
        batch_size=8,
        validation_split=validation_split,
        verbose=1,
        callbacks=callbacks if validation_split > 0 else None,
        shuffle=True,
    )

    model_dir = os.path.dirname(model_path)
    if model_dir:
        os.makedirs(model_dir, exist_ok=True)

    model.save(model_path)
    _save_label_map(labels_path, label_names)

    return model, {index: label for index, label in enumerate(label_names)}


def _try_load_model(model_path):
    try:
        model = load_model(model_path, compile=False)
        return model
    except Exception as first_error:
        try:
            model = tf.keras.models.load_model(model_path, compile=False)
            return model
        except Exception:
            raise RuntimeError(str(first_error))


@lru_cache(maxsize=1)
def load_phrase_assets(
    model_path="models/phrase_lstm.keras",
    labels_path="models/phrase_labels.json",
    data_dir="data/phrases",
):
    label_map = _load_label_map(labels_path)

    if _is_valid_artifact(model_path) and label_map:
        try:
            model = _try_load_model(model_path)
            return model, {index: label for label, index in label_map.items()}
        except Exception as e:
            print(f"[WARN] Existing model could not be loaded: {e}")
            print("[INFO] Rebuilding model from local phrase data...")
            return _train_phrase_model(model_path, labels_path, data_dir)

    print("[INFO] Existing model or labels missing. Training a fresh model...")
    return _train_phrase_model(model_path, labels_path, data_dir)


class PhrasePredictor:
    def __init__(
        self,
        model_path="models/phrase_lstm.keras",
        labels_path="models/phrase_labels.json",
        data_dir="data/phrases",
    ):
        self.model, self.index_to_label = load_phrase_assets(model_path, labels_path, data_dir)
        self.sequence = []

    def extract_keypoints(self, mp_bundle):
        if not isinstance(mp_bundle, MediaPipeBundle):
            raise TypeError("PhrasePredictor.predict expects a MediaPipeBundle")

        return self._extract_features(mp_bundle)

    def _extract_features(self, mp_bundle):
        from core.landmarks import LandmarkExtractor

        extractor = LandmarkExtractor.__new__(LandmarkExtractor)
        return LandmarkExtractor.extract_features(extractor, mp_bundle)

    def predict(self, mp_bundle):
        keypoints = self.extract_keypoints(mp_bundle)
        self.sequence.append(keypoints)
        self.sequence = self.sequence[-FRAMES:]

        if len(self.sequence) < FRAMES:
            return "Waiting...", 0.0

        input_data = np.expand_dims(np.asarray(self.sequence, dtype=np.float32), axis=0)
        res = self.model.predict(input_data, verbose=0)[0]

        predicted_index = int(np.argmax(res))
        confidence = float(res[predicted_index])

        label = self.index_to_label.get(predicted_index, "Unknown")

        if confidence >= THRESHOLD:
            return label, confidence

        return "Uncertain", confidence

    def reset(self):
        self.sequence = []

    def close(self):
        pass