from pathlib import Path
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATASET_DIR = PROJECT_ROOT / "dataset" / "phrases"

for phrase_dir in sorted(DATASET_DIR.iterdir()):
    if not phrase_dir.is_dir():
        continue

    files = sorted(phrase_dir.glob("*.npy"))
    print(f"{phrase_dir.name}: {len(files)} samples")

    if files:
        arr = np.load(files[0])
        print(f"  first shape: {arr.shape}")