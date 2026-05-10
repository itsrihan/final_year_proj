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


_LAST_PHRASE_ASSET_DEBUG_INFO = None


gpus = tf.config.list_physical_devices("GPU")
if gpus:
    tf.config.experimental.set_memory_growth(gpus[0], True)
    print(f"[INFO] Using GPU: {gpus[0]}")
else:
    print("[WARN] No GPU found, falling back to CPU")


def _is_valid_artifact(path):
    return os.path.exists(path) and os.path.getsize(path) > 0


def _coerce_int(value):
    if isinstance(value, bool):
        raise ValueError("boolean values are not valid indexes")

    if isinstance(value, int):
        return value

    if isinstance(value, str) and value.strip().isdigit():
        return int(value.strip())

    raise ValueError(f"cannot convert {value!r} to int")


def _normalize_labels_payload(payload):
    if isinstance(payload, list):
        labels = [str(label) for label in payload]
        if not labels:
            raise ValueError("label list is empty")
        return labels

    if not isinstance(payload, dict) or not payload:
        raise ValueError("labels JSON must be a non-empty list or dict")

    keys = list(payload.keys())
    values = list(payload.values())

    keys_are_numeric = all(isinstance(key, str) and key.strip().isdigit() for key in keys)
    values_are_numeric = all(isinstance(value, (int, str)) and str(value).strip().isdigit() for value in values)

    if keys_are_numeric:
        sorted_items = sorted(payload.items(), key=lambda item: int(str(item[0]).strip()))
        labels = [str(label) for _, label in sorted_items]
        if not labels:
            raise ValueError("numeric-key label dict is empty")
        return labels

    if values_are_numeric:
        index_to_label = {}
        for label, index in payload.items():
            index_to_label[_coerce_int(index)] = str(label)

        if not index_to_label:
            raise ValueError("label-to-index dict is empty")

        return [label for _, label in sorted(index_to_label.items(), key=lambda item: item[0])]

    raise ValueError("unsupported labels JSON format")


def _load_label_list(labels_path):
    if not _is_valid_artifact(labels_path):
        return None

    try:
        with open(labels_path, "r", encoding="utf-8") as f:
            payload = json.load(f)
    except (OSError, json.JSONDecodeError) as error:
        raise RuntimeError(f"failed to read labels file {labels_path}: {error}") from error

    return _normalize_labels_payload(payload)


def _shape_to_text(shape):
    if shape is None:
        return "None"

    try:
        return str(tuple(shape))
    except TypeError:
        return str(shape)


def _inspect_existing_phrase_assets(model_path=PHRASE_MODEL_PATH, labels_path=PHRASE_LABELS_PATH):
    model_path_exists = _is_valid_artifact(model_path)
    labels_path_exists = _is_valid_artifact(labels_path)

    debug_info = {
        "model_available": False,
        "model_path": model_path,
        "labels_path": labels_path,
        "model_path_exists": model_path_exists,
        "labels_path_exists": labels_path_exists,
        "model_input_shape": None,
        "model_output_shape": None,
        "labels_count": 0,
        "labels": [],
        "error": None,
    }

    if not model_path_exists or not labels_path_exists:
        debug_info["error"] = "model or labels file missing"
        return debug_info

    try:
        labels = _load_label_list(labels_path)
        if labels is None:
            raise RuntimeError("labels file could not be loaded")

        model = _try_load_model(model_path)

        dummy = np.zeros((1, FRAMES, FEATURES_PER_FRAME), dtype=np.float32)
        model(dummy, training=False)

        model_input_shape = getattr(model, "input_shape", None)
        model_output_shape = getattr(model, "output_shape", None)

        expected_input_shape = (None, FRAMES, FEATURES_PER_FRAME)
        if tuple(model_input_shape) != expected_input_shape:
            raise RuntimeError(
                f"model input shape {tuple(model_input_shape)} does not match expected {expected_input_shape}"
            )

        output_units = None
        if isinstance(model_output_shape, (list, tuple)) and model_output_shape:
            output_units = model_output_shape[-1]

        if output_units is not None and int(output_units) != len(labels):
            raise RuntimeError(
                f"model output classes ({output_units}) do not match labels count ({len(labels)})"
            )

        debug_info["model_available"] = True
        debug_info["model_input_shape"] = _shape_to_text(model_input_shape)
        debug_info["model_output_shape"] = _shape_to_text(model_output_shape)
        debug_info["labels_count"] = len(labels)
        debug_info["labels"] = labels
        debug_info["model"] = model
        global _LAST_PHRASE_ASSET_DEBUG_INFO
        _LAST_PHRASE_ASSET_DEBUG_INFO = dict(debug_info)
        return debug_info

    except Exception as error:
        debug_info["error"] = str(error)
        return debug_info


def _load_existing_phrase_assets(model_path=PHRASE_MODEL_PATH, labels_path=PHRASE_LABELS_PATH):
    debug_info = _inspect_existing_phrase_assets(model_path, labels_path)
    if not debug_info["model_available"]:
        raise RuntimeError(debug_info["error"] or "failed to load phrase assets")

    model = debug_info.get("model")
    labels = debug_info["labels"]
    return model, {index: label for index, label in enumerate(labels)}, debug_info


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


def get_phrase_assets_debug_info(
    model_path=PHRASE_MODEL_PATH,
    labels_path=PHRASE_LABELS_PATH,
    data_dir=PHRASE_DATA_DIR,
):
    global _LAST_PHRASE_ASSET_DEBUG_INFO

    if _LAST_PHRASE_ASSET_DEBUG_INFO:
        cached = _LAST_PHRASE_ASSET_DEBUG_INFO
        if cached.get("model_path") == model_path and cached.get("labels_path") == labels_path:
            debug_info = dict(cached)
            debug_info.pop("model", None)
            return debug_info

    debug_info = _inspect_existing_phrase_assets(model_path, labels_path)
    debug_info.pop("model", None)

    if debug_info.get("model_available"):
        _LAST_PHRASE_ASSET_DEBUG_INFO = dict(debug_info)

    if debug_info["model_available"]:
        return debug_info

    if not _is_valid_artifact(model_path) and not _is_valid_artifact(labels_path):
        debug_info["error"] = debug_info["error"] or "model and labels files are missing"

    return debug_info


@lru_cache(maxsize=1)
def load_phrase_assets(
    model_path=PHRASE_MODEL_PATH,
    labels_path=PHRASE_LABELS_PATH,
    data_dir=PHRASE_DATA_DIR,
):
    global _LAST_PHRASE_ASSET_DEBUG_INFO

    if _is_valid_artifact(model_path) and _is_valid_artifact(labels_path):
        model, label_index_map, debug_info = _load_existing_phrase_assets(model_path, labels_path)
        _LAST_PHRASE_ASSET_DEBUG_INFO = dict(debug_info)

        print(f"[INFO] phrase model path: {model_path}")
        print(f"[INFO] phrase labels path: {labels_path}")
        print(f"[INFO] model_path_exists={debug_info['model_path_exists']} labels_path_exists={debug_info['labels_path_exists']}")
        print(f"[INFO] model_input_shape={debug_info['model_input_shape']} model_output_shape={debug_info['model_output_shape']}")
        print(f"[INFO] labels_count={debug_info['labels_count']} labels={debug_info['labels']}")
        print("[INFO] Model warmed up")

        return model, label_index_map

    print("[INFO] Existing model or labels missing. Training a fresh model...")
    model, label_index_map = _train_phrase_model(model_path, labels_path, data_dir)

    dummy = np.zeros((1, FRAMES, FEATURES_PER_FRAME), dtype=np.float32)
    model(dummy, training=False)

    print("[INFO] Model warmed up")
    _LAST_PHRASE_ASSET_DEBUG_INFO = {
        "model_available": True,
        "model_path": model_path,
        "labels_path": labels_path,
        "model_path_exists": True,
        "labels_path_exists": True,
        "model_input_shape": _shape_to_text(getattr(model, "input_shape", None)),
        "model_output_shape": _shape_to_text(getattr(model, "output_shape", None)),
        "labels_count": len(label_index_map),
        "labels": [label_index_map[index] for index in sorted(label_index_map.keys())],
        "error": None,
    }

    return model, label_index_map
