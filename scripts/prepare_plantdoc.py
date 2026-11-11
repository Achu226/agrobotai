"""
Builds field-photo datasets from the PlantDoc repository (data/plantdoc_raw, a git clone whose checkout fails on
Windows because some file names are invalid there).

    data/plantdoc/{train,test}/<our class>/*.jpg

Classes that match the disease model keep its label (e.g. "Tomato leaf late blight" -> Tomato_Late_blight).
Every other plant in PlantDoc goes to `Other_plant`, so the model can learn to say "this plant is not supported".
PlantDoc's own train/test split is kept, so no test photo is ever trained on.
"""
from __future__ import annotations

import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "plantdoc_raw"
OUT = ROOT / "data" / "plantdoc"

MAPPING = {
    "Bell_pepper leaf": "Pepper__bell___healthy",
    "Bell_pepper leaf spot": "Pepper__bell___Bacterial_spot",
    "Potato leaf early blight": "Potato___Early_blight",
    "Potato leaf late blight": "Potato___Late_blight",
    "Tomato Early blight leaf": "Tomato_Early_blight",
    "Tomato Septoria leaf spot": "Tomato_Septoria_leaf_spot",
    "Tomato leaf": "Tomato_healthy",
    "Tomato leaf bacterial spot": "Tomato_Bacterial_spot",
    "Tomato leaf late blight": "Tomato_Late_blight",
    "Tomato leaf mosaic virus": "Tomato__Tomato_mosaic_virus",
    "Tomato leaf yellow virus": "Tomato__Tomato_YellowLeaf__Curl_Virus",
    "Tomato mold leaf": "Tomato_Leaf_Mold",
    "Tomato two spotted spider mites leaf": "Tomato_Spider_mites_Two_spotted_spider_mite",
}
# --extended: field photos of the crops added with rice/banana/PlantVillage (scripts/build_extended_dataset.py)
EXTENDED = {
    "Apple Scab Leaf": "Apple_scab", "Apple leaf": "Apple_healthy", "Apple rust leaf": "Apple_cedar_rust",
    "Blueberry leaf": "Blueberry_healthy", "Cherry leaf": "Cherry_healthy", "Corn Gray leaf spot": "Maize_gray_leaf_spot",
    "Corn leaf blight": "Maize_northern_leaf_blight", "Corn rust leaf": "Maize_common_rust", "Peach leaf": "Peach_healthy",
    "Raspberry leaf": "Raspberry_healthy", "Soyabean leaf": "Soybean_healthy", "Squash Powdery mildew leaf": "Squash_powdery_mildew",
    "Strawberry leaf": "Strawberry_healthy", "grape leaf": "Grape_healthy", "grape leaf black rot": "Grape_black_rot",
}
OTHER = "Other_plant"
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


def main(extended: bool = False) -> int:
    mapping = MAPPING | EXTENDED if extended else MAPPING
    out = OUT.with_name("plantdoc_v2") if extended else OUT
    names = subprocess.run(["git", "-C", str(RAW), "ls-tree", "-r", "HEAD", "--name-only"],
                           capture_output=True, text=True, encoding="utf-8", check=True).stdout.splitlines()
    counts: Counter = Counter()
    for i, name in enumerate(names):
        parts = name.split("/")
        if len(parts) != 3 or parts[0] not in ("train", "test") or Path(parts[2]).suffix.lower() not in IMAGE_EXTS:
            continue
        split, cls, fname = parts
        label = mapping.get(cls, OTHER)
        safe = re.sub(r"[^A-Za-z0-9._-]", "_", Path(fname).stem)[:80] + Path(fname).suffix.lower()
        dest = out / split / label / f"{i:05d}_{safe}"
        if not dest.exists():
            blob = subprocess.run(["git", "-C", str(RAW), "cat-file", "blob", f"HEAD:{name}"], capture_output=True, check=True).stdout
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(blob)
        counts[(split, label)] += 1
    for (split, label), n in sorted(counts.items()):
        print(f"{split:5s} {n:4d} {label}")
    print("total", sum(counts.values()))
    return 0


if __name__ == "__main__":
    sys.exit(main(extended="--extended" in sys.argv))
