from pathlib import Path
import json
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATASET_DIR = PROJECT_ROOT / "dataset" / "phrases"

summary = {}

for phrase_dir in sorted(DATASET_DIR.iterdir()):
    if not phrase_dir.is_dir():
        continue

    files = sorted(phrase_dir.glob("*.npy"))
    shapes = []

    for f in files:
        try:
            arr = np.load(f)
            shapes.append(list(arr.shape))
        except Exception:
            shapes.append(["error"])

    unique_shapes = []
    for s in shapes:
        if s not in unique_shapes:
            unique_shapes.append(s)

    summary[phrase_dir.name] = {
        "count": len(files),
        "shapes": unique_shapes,
    }

output_path = PROJECT_ROOT / "dataset" / "dataset_info.json"

with open(output_path, "w", encoding="utf-8") as f:
    json.dump(summary, f, indent=2)

print(f"Saved dataset info to: {output_path}")
print(json.dumps(summary, indent=2))