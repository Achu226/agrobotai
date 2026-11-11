"""
Builds the pest model's 10th class, `no_pest`: photos of leaves without insects.

  data/pest/{train,val,test}/no_pest/
    lab leaves   from data/disease/{train,val,test}   (PlantVillage; same split, Spider_mites excluded: mites are a pest)
    field leaves from data/plantdoc/{train,test}       (PlantDoc; train split -> train/val, test split -> test)

Each source keeps its own train/test split, so no test photo is ever trained on.
"""
from __future__ import annotations

import random
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "pest"
EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
SIZES = {"train": (200, 500), "val": (50, 90), "test": (36, 100)}  # (lab, field) photos per split


def photos(root: Path) -> list[Path]:
    return sorted(f for f in root.rglob("*") if f.suffix.lower() in EXTS and "Spider_mites" not in f.parent.name)


def main() -> int:
    rng = random.Random(2026)
    lab = {s: photos(ROOT / "data/disease" / s) for s in ("train", "val", "test")}
    field_train = photos(ROOT / "data/plantdoc/train")
    rng.shuffle(field_train)
    field = {"train": field_train[: SIZES["train"][1]], "val": field_train[SIZES["train"][1]: SIZES["train"][1] + SIZES["val"][1]],
             "test": rng.sample(photos(ROOT / "data/plantdoc/test"), SIZES["test"][1])}
    for split, (n_lab, _) in SIZES.items():
        dest = OUT / split / "no_pest"
        if dest.exists():
            shutil.rmtree(dest)
        dest.mkdir(parents=True)
        chosen = [("pv", f) for f in rng.sample(lab[split], n_lab)] + [("pd", f) for f in field[split]]
        for i, (src, f) in enumerate(chosen):
            shutil.copy2(f, dest / f"{src}_{i:04d}{f.suffix.lower()}")
        print(f"{split}: {n_lab} lab + {len(field[split])} field leaves -> {dest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
