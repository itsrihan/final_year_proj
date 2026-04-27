import json
import os
from functools import lru_cache

import numpy as np
import tensorflow as tf
from tensorflow import keras
from tensorflow.keras.models import load_model

from core.config import (
    FEATURES_PER_FRAME,
    FRAMES,
    PHRASE_DATA_DIR,
    PHRASE_LABELS_PATH,
    PHRASE_MODEL_PATH,
)


gpus = tf.config.list_physical_devices("GPU")
if gpus:
    tf.config.experimental.set_memory_growth(gpus[0], True)
    print(f"[INFO] Using GPU: {gpus[0]}")
else:
    print("[WARN] No GPU found, falling back to CPU")


def _is_valid_artifact(path):
    return os.path.exists(path) and os.path.getsize(path) > 0


def _load_label_map(labels_path):
    if not _is_valid_artifact(labels_path):
        return None

    try:
        with open(labels_path, "r", encoding="utf-8") as f:
            label_map = json.load(f)
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
            key=lambda f: int(os.path.splitext(f)[0])
            if os.path.splitext(f)[0].isdigit()
            else f,
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

    if "null" in label_names:
        label_names.remove("null")
        label_names = ["null"] + label_names

    label_to_index = {label: i for i, label in enumerate(label_names)}

    x_values = np.asarray(sequences, dtype=np.float32)
    y_values = np.array([label_to_index[label] for label in labels], dtype=np.int32)

    return x_values, y_values, label_names


def _build_model(num_classes):
    model = keras.Sequential(
        [
            keras.layers.Input(shape=(FRAMES, FEATURES_PER_FRAME)),
            keras.layers.LayerNormalization(),
            keras.layers.LSTM(64, return_sequences=False),
            keras.layers.Dense(64, activation="relu"),
            keras.layers.Dropout(0.3),
            keras.layers.Dense(num_classes, activation="softmax"),
        ]
    )

    model.compile(
        optimizer=keras.optimizers.Adam(learning_rate=0.001),
        loss="sparse_categorical_crossentropy",
        metrics=["accuracy"],
    )

    return model


def _save_label_map(labels_path, label_names):
    labels_dir = os.path.dirname(labels_path)

    if labels_dir:
        os.makedirs(labels_dir, exist_ok=True)

    label_map = {label: i for i, label in enumerate(label_names)}

    with open(labels_path, "w", encoding="utf-8") as f:
        json.dump(label_map, f, indent=2)

    return label_map


def _train_phrase_model(model_path, labels_path, data_dir):
    x_values, y_values, label_names = _load_training_data(data_dir)

    if x_values.size == 0 or y_values.size == 0 or not label_names:
        raise RuntimeError(
            "No valid phrase training data found. "
            "Each class folder must contain .npy sequences shaped like "
            f"({FRAMES}, {FEATURES_PER_FRAME})."
        )

    model = _build_model(len(label_names))

    callbacks = [
        keras.callbacks.EarlyStopping(
            monitor="val_accuracy",
            mode="max",
            patience=15,
            restore_best_weights=True,
        )
    ]

    validation_split = 0.2 if len(x_values) >= 10 else 0.0

    model.fit(
        x_values,
        y_values,
        epochs=80,
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

    return model, {i: label for i, label in enumerate(label_names)}


def _try_load_model(model_path):
    try:
        return load_model(model_path, compile=False)
    except Exception as first_error:
        try:
            return tf.keras.models.load_model(model_path, compile=False)
        except Exception:
            raise RuntimeError(str(first_error))


@lru_cache(maxsize=1)
def load_phrase_assets(
    model_path=PHRASE_MODEL_PATH,
    labels_path=PHRASE_LABELS_PATH,
    data_dir=PHRASE_DATA_DIR,
):
    label_map = _load_label_map(labels_path)

    if _is_valid_artifact(model_path) and label_map:
        try:
            model = _try_load_model(model_path)

            dummy = np.zeros((1, FRAMES, FEATURES_PER_FRAME), dtype=np.float32)
            model(dummy, training=False)

            print("[INFO] Model warmed up")
            print(f"[INFO] Loaded labels: {label_map}")

            return model, {index: label for label, index in label_map.items()}

        except Exception as e:
            print(f"[WARN] Existing model could not be loaded: {e}")
            print("[INFO] Rebuilding model from local phrase data...")
    else:
        print("[INFO] Existing model or labels missing. Training a fresh model...")

    model, label_index_map = _train_phrase_model(model_path, labels_path, data_dir)

    dummy = np.zeros((1, FRAMES, FEATURES_PER_FRAME), dtype=np.float32)
    model(dummy, training=False)

    print("[INFO] Model warmed up")

    return model, label_index_map
