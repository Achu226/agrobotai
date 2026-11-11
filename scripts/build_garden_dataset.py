"""
Builds data/disease_garden/{train,val,test}/<class>/ for home-garden plants (rose, money plant, hibiscus, marigold)
from the zips fetched by `scripts/download_leaf_datasets.py --garden` (all CC BY 4.0, Mendeley Data).

Same duplicate-safe split as scripts/build_extended_dataset.py: rotated/flipped copies of one photo stay in one split.
Flower photos in the flowers set are skipped (the model reads leaves).

The flowers set (all hibiscus and marigold, part of rose) shows cut-out leaves on pure black. A model trained on that
learns "black background = hibiscus/marigold" and fails on real garden photos (measured: 16 of 119 right). So every
such leaf is pasted onto real outdoor photos (PlantDoc, blurred like a phone background) and the black original is
not used. Test leaves only get backgrounds from PlantDoc's test split, so no background is shared with training.

    .venv\\Scripts\\python.exe scripts\\build_garden_dataset.py
"""
from __future__ import annotations

import io
import json
import random
import shutil
import sys
import zipfile
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from scripts.build_extended_dataset import assign_splits, fingerprints, groups, save  # noqa: E402

RAW = ROOT / "data" / "new_raw" / "garden"
OUT = ROOT / "data" / "disease_garden"
# (zip, parent folder, class folder) -> class
MAP = {
    ("rose", "Rose Leaf", "Black Spot"): "Rose_leaf_spot",
    ("rose", "Rose Leaf", "Dry Leaf"): "Rose_dry_leaf",
    ("rose", "Rose Leaf", "Healthy Leaf"): "Rose_healthy",
    ("rose", "Rose Leaf", "Leaf Holes"): "Rose_insect_damage",
    ("flowers", "Rosa", "Fungal Leaf Spot Disease"): "Rose_leaf_spot",
    ("flowers", "Rosa", "Healthy Leaf"): "Rose_healthy",
    ("flowers", "Rosa", "Nutrient Deficiency"): "Rose_nutrient_deficiency",
    ("flowers", "Rosa", "insect damage"): "Rose_insect_damage",
    ("flowers", "Hibiscus rosa-sinensis", "Bacterial Leaf or Spot"): "Hibiscus_bacterial_leaf_spot",
    ("flowers", "Hibiscus rosa-sinensis", "Healthy Leaf"): "Hibiscus_healthy",
    ("flowers", "Hibiscus rosa-sinensis", "Nutrient Deficiency"): "Hibiscus_nutrient_deficiency",
    ("flowers", "Tagetes erecta", "Alternaria Leaf Blight"): "Marigold_alternaria_blight",
    ("flowers", "Tagetes erecta", "Heaalthy Leaf"): "Marigold_healthy",  # sic, folder name in the dataset
    ("flowers", "Tagetes erecta", "Pest Damage"): "Marigold_pest_damage",
    ("money_plant", "MoneyPlant", "Bacterial wilt disease"): "Money_plant_bacterial_wilt",
    ("money_plant", "MoneyPlant", "Healthy"): "Money_plant_healthy",
    ("money_plant", "MoneyPlant", "Manganese Toxicity"): "Money_plant_manganese_toxicity",
}
CLASSES = sorted(set(MAP.values()))
EXTS = (".jpg", ".jpeg", ".png")
BLACK_BG_SOURCE = "garden_flowers"
COPIES = {"train": 2, "val": 1, "test": 1}  # backgrounds per cut-out leaf


def backgrounds(split: str) -> list[Path]:
    root = ROOT / "data" / "plantdoc_v2" / ("test" if split == "test" else "train")
    return sorted(f for f in root.rglob("*") if f.suffix.lower() in EXTS)


def on_background(leaf: Image.Image, back_path: Path, rng: random.Random) -> Image.Image:
    """Cut-out leaf (pure black around it) pasted onto a blurred real photo."""
    a = np.asarray(leaf, dtype=np.float32)
    mask = Image.fromarray(((a.max(axis=2) > 18) * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(1.5))
    back = Image.open(back_path).convert("RGB")
    w, h = back.size
    side = int(min(w, h) * rng.uniform(0.6, 1.0))  # random crop, so one photo gives different backgrounds
    x, y = rng.randint(0, w - side), rng.randint(0, h - side)
    back = back.crop((x, y, x + side, y + side)).resize(leaf.size).filter(ImageFilter.GaussianBlur(rng.uniform(2, 6)))
    return Image.composite(leaf, back, mask)


def collect() -> dict[str, list[tuple[str, bytes]]]:
    items: dict[str, list[tuple[str, bytes]]] = defaultdict(list)
    for name in ("rose", "flowers", "money_plant"):
        with zipfile.ZipFile(RAW / name / f"{name}.zip") as z:
            for entry in sorted(z.namelist()):
                parts = entry.split("/")
                cls = MAP.get((name, *parts[-3:-1])) if len(parts) >= 3 else None
                if cls and entry.lower().endswith(EXTS):
                    items[cls].append((f"garden_{name}", z.read(entry)))
    return items


def main() -> int:
    if OUT.exists():
        shutil.rmtree(OUT)
    counts: Counter = Counter()
    rng = random.Random(1337)
    backs = {s: backgrounds(s) for s in COPIES}
    assert all(backs.values()), "PlantDoc photos missing: run scripts/prepare_plantdoc.py --extended first"
    for cls, photos in sorted(collect().items()):
        imgs, prints = [], []
        for source, data in photos:
            try:
                img = Image.open(io.BytesIO(data))
                img = img.convert("RGB")
            except Exception:  # noqa: BLE001 - unreadable file: skip it, never invent data
                continue
            img.thumbnail((768, 768))  # the rose originals are large; fingerprints and save() need far less
            imgs.append((source, img))
            prints.append(fingerprints(img))
        members = defaultdict(list)
        for i, g in enumerate(groups(np.stack(prints))):
            members[g].append(i)
        member_list = list(members.values())
        for group, split in zip(member_list, assign_splits([len(m) for m in member_list], rng)):
            for i in group:
                source, img = imgs[i]
                if source != BLACK_BG_SOURCE:
                    save(img, OUT / split / cls / f"{source}_{i:05d}.jpg")
                    counts[(cls, split)] += 1
                    continue
                for k in range(COPIES[split]):
                    save(on_background(img, rng.choice(backs[split]), rng), OUT / split / cls / f"{source}_{i:05d}_bg{k}.jpg")
                    counts[(cls, split)] += 1
        print(f"{cls:32s} {len(imgs):5d} photos, {len(members):5d} unique groups | train {counts[(cls, 'train')]} "
              f"val {counts[(cls, 'val')]} test {counts[(cls, 'test')]}", flush=True)
    assert set(c for c, _ in counts) == set(CLASSES), "a class got no photos: check the folder names in MAP"
    (OUT / "sources.json").write_text(json.dumps({
        "classes": CLASSES,
        "counts": {f"{c}/{s}": n for (c, s), n in sorted(counts.items())},
        "licences": {"garden_rose": "CC BY 4.0 (Mendeley 10.17632/hmjtdzkfh3.2)",
                     "garden_flowers": "CC BY 4.0 (Mendeley 10.17632/2vzp6ss7vg.1)",
                     "garden_money_plant": "CC BY 4.0 (Mendeley 10.17632/rzjww3vdxt.3)"},
    }, indent=1), encoding="utf-8")
    print("total", sum(counts.values()), "photos in", OUT)
    return 0


if __name__ == "__main__":
    sys.exit(main())
