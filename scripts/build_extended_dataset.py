"""
Builds data/disease_ext/{train,val,test}/<class>/ for the new crops (rice, banana, 11 PlantVillage crops)
and the "Other_plant" examples, from the files fetched by scripts/download_leaf_datasets.py.

Near-duplicates (the same photo rotated/flipped, common in the rice set) are grouped with a
rotation-proof fingerprint and a whole group goes to one split, so test photos are never seen in training.

    .venv\\Scripts\\python.exe scripts\\build_extended_dataset.py
"""
from __future__ import annotations

import io
import json
import random
import shutil
import subprocess
import sys
import zipfile
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
import pyarrow.parquet as pq
from PIL import Image, ImageOps

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "new_raw"
OUT = ROOT / "data" / "disease_ext"
MAX_SIDE = 384
PV_CAP = 1100          # photos per PlantVillage class (keeps the huge classes from dominating)
OTHER_CAP = 300        # photos per "other plant" dataset
SPLIT = (0.70, 0.15)   # train, val; the rest is test

SETHY = {"Bacterialblight": "Rice_bacterial_blight", "Blast": "Rice_blast", "Brownspot": "Rice_brown_spot", "Tungro": "Rice_tungro"}
RICE_BD = {"Healthy": "Rice_healthy", "Rice Blast": "Rice_blast", "Rice Tungro": "Rice_tungro"}
BANANA = {"cordana": "Banana_cordana", "healthy": "Banana_healthy", "pestalotiopsis": "Banana_pestalotiopsis", "sigatoka": "Banana_sigatoka"}
PLANTVILLAGE = {
    "Apple___Apple_scab": "Apple_scab", "Apple___Black_rot": "Apple_black_rot", "Apple___Cedar_apple_rust": "Apple_cedar_rust",
    "Apple___healthy": "Apple_healthy", "Blueberry___healthy": "Blueberry_healthy",
    "Cherry_(including_sour)___Powdery_mildew": "Cherry_powdery_mildew", "Cherry_(including_sour)___healthy": "Cherry_healthy",
    "Corn_(maize)___Cercospora_leaf_spot Gray_leaf_spot": "Maize_gray_leaf_spot", "Corn_(maize)___Common_rust_": "Maize_common_rust",
    "Corn_(maize)___Northern_Leaf_Blight": "Maize_northern_leaf_blight", "Corn_(maize)___healthy": "Maize_healthy",
    "Grape___Black_rot": "Grape_black_rot", "Grape___Esca_(Black_Measles)": "Grape_esca",
    "Grape___Leaf_blight_(Isariopsis_Leaf_Spot)": "Grape_leaf_blight", "Grape___healthy": "Grape_healthy",
    "Orange___Haunglongbing_(Citrus_greening)": "Orange_citrus_greening", "Peach___Bacterial_spot": "Peach_bacterial_spot",
    "Peach___healthy": "Peach_healthy", "Raspberry___healthy": "Raspberry_healthy", "Soybean___healthy": "Soybean_healthy",
    "Squash___Powdery_mildew": "Squash_powdery_mildew", "Strawberry___Leaf_scorch": "Strawberry_leaf_scorch",
    "Strawberry___healthy": "Strawberry_healthy",
}
NEW_CLASSES = sorted(set(SETHY.values()) | set(RICE_BD.values()) | set(BANANA.values()) | set(PLANTVILLAGE.values()))
OTHER = "Other_plant"


def fingerprints(img: Image.Image, n: int = 16) -> np.ndarray:
    """256-bit difference hashes of the 8 rotations/flips, shape (8, 4) uint64 (row 0 = the photo as it is).
    A 64-bit hash was too coarse: different long, thin rice leaves looked identical."""
    g = img.convert("L")
    out = []
    for flip in (False, True):
        base = ImageOps.mirror(g) if flip else g
        for angle in (0, 90, 180, 270):
            a = np.asarray(base.rotate(angle, expand=True).resize((n + 1, n), Image.BILINEAR), dtype=np.int16)
            out.append(np.packbits((a[:, 1:] > a[:, :-1]).flatten()).view(np.uint64))
    return np.stack(out)


def groups(hashes: np.ndarray, max_bits: int = 6) -> list[int]:
    """Union of photos whose fingerprints match up to rotation/flip (at most `max_bits` of 256 bits differ)."""
    n = len(hashes)
    parent = list(range(n))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    plain = hashes[:, 0]
    for i in range(n):
        d = np.bitwise_count(hashes[i][:, None, :] ^ plain[None, i + 1:, :]).sum(-1).min(axis=0)
        for j in np.nonzero(d <= max_bits)[0]:
            a, b = find(i), find(i + 1 + int(j))
            if a != b:
                parent[b] = a
    return [find(i) for i in range(n)]


def assign_splits(sizes: list[int], rng: random.Random) -> list[str]:
    """Largest group first, each to the split furthest below its share, so no split ends up empty."""
    target = {"train": SPLIT[0], "val": SPLIT[1], "test": 1 - SPLIT[0] - SPLIT[1]}
    have = dict.fromkeys(target, 0)
    order = sorted(range(len(sizes)), key=lambda g: (-sizes[g], rng.random()))
    out = [""] * len(sizes)
    for g in order:
        total = sum(have.values()) + sizes[g]
        split = max(target, key=lambda s: target[s] * total - have[s])
        out[g] = split
        have[split] += sizes[g]
    return out


def save(img: Image.Image, path: Path) -> None:
    img = img.convert("RGB")
    img.thumbnail((MAX_SIDE, MAX_SIDE))
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path, "JPEG", quality=90)


def parquet_images(path: Path):
    pf = pq.ParquetFile(path)
    feats = json.loads(pf.schema_arrow.metadata[b"huggingface"])["info"]["features"]
    # Column names differ between datasets ("label"/"labels", "image"/"img"): find them by type
    image_col = next(k for k, v in feats.items() if isinstance(v, dict) and v.get("_type") == "Image")
    label_col = next((k for k, v in feats.items() if isinstance(v, dict) and "names" in v), None)
    names = feats[label_col]["names"] if label_col else None
    for batch in pf.iter_batches(batch_size=64, columns=[image_col] + ([label_col] if label_col else [])):
        labels = batch.column(label_col).to_pylist() if label_col else [None] * batch.num_rows
        for img, label in zip(batch.column(image_col).to_pylist(), labels):
            yield (names[label] if names is not None and label is not None else None), img["bytes"]


def collect() -> dict[str, list[tuple[str, bytes]]]:
    """class -> [(source, jpeg bytes)]"""
    items: dict[str, list[tuple[str, bytes]]] = defaultdict(list)
    rng = random.Random(42)
    # Rice (Sethy, 7z) via the Windows/bsdtar extractor into a temp folder
    sethy_dir = RAW / "rice_sethy" / "x"
    if not any(sethy_dir.rglob("*.jpg")):
        sethy_dir.mkdir(parents=True, exist_ok=True)
        tar = Path(r"C:\Windows\System32\tar.exe")
        subprocess.run([str(tar if tar.exists() else "tar"), "-xf", str(RAW / "rice_sethy" / "rice_sethy.7z"), "-C", str(sethy_dir)], check=True)
    for folder, cls in SETHY.items():
        for f in sorted(sethy_dir.rglob(f"{folder}/*")):
            if f.suffix.lower() in (".jpg", ".jpeg", ".png"):
                items[cls].append(("rice_sethy", f.read_bytes()))
    for f in sorted((RAW / "rice_bd").rglob("*.parquet")):
        for label, data in parquet_images(f):
            if label in RICE_BD:
                items[RICE_BD[label]].append(("rice_bd", data))
    for f in sorted((RAW / "banana_lsd").rglob("*.parquet")):
        for label, data in parquet_images(f):
            items[BANANA[label]].append(("banana_lsd", data))
    for ds in sorted((RAW / "other").iterdir()):
        photos = [data for f in sorted(ds.rglob("*.parquet")) for _, data in parquet_images(f)]
        rng.shuffle(photos)
        items[OTHER] += [(f"other_{ds.name}", d) for d in photos[:OTHER_CAP]]
    pv_zip = RAW / "plantvillage" / "data.zip"
    with zipfile.ZipFile(pv_zip) as z:
        by_class = defaultdict(list)
        for name in z.namelist():
            parts = name.split("/")
            # .../color/<class>/<file>.JPG  (the grayscale and segmented copies are not used)
            if len(parts) >= 3 and parts[-3] == "color" and parts[-2] in PLANTVILLAGE and parts[-1]:
                by_class[PLANTVILLAGE[parts[-2]]].append(name)
        for cls, names in sorted(by_class.items()):
            names.sort()
            rng.shuffle(names)
            items[cls] += [("plantvillage", z.read(n)) for n in names[:PV_CAP]]
    return items


def main() -> int:
    if OUT.exists():
        shutil.rmtree(OUT)
    items = collect()
    counts: Counter = Counter()
    rng = random.Random(1337)
    for cls, photos in sorted(items.items()):
        imgs, prints = [], []
        for source, data in photos:
            try:
                img = Image.open(io.BytesIO(data))
                img.load()
            except Exception:  # noqa: BLE001 - unreadable file: skip it, never invent data
                continue
            imgs.append((source, img))
            prints.append(fingerprints(img))
        grp = groups(np.stack(prints))
        members = defaultdict(list)
        for i, g in enumerate(grp):
            members[g].append(i)
        member_list = list(members.values())
        n = len(imgs)
        for group, split in zip(member_list, assign_splits([len(m) for m in member_list], rng)):
            for i in group:
                source, img = imgs[i]
                save(img, OUT / split / cls / f"{source}_{i:05d}.jpg")
                counts[(cls, split)] += 1
        dupes = n - len(members)
        print(f"{cls:28s} {n:5d} photos, {len(members):5d} unique groups ({dupes} rotated/flipped copies kept together) | "
              f"train {counts[(cls, 'train')]} val {counts[(cls, 'val')]} test {counts[(cls, 'test')]}", flush=True)
    (OUT / "sources.json").write_text(json.dumps({
        "classes": NEW_CLASSES + [OTHER],
        "counts": {f"{c}/{s}": n for (c, s), n in sorted(counts.items())},
        "licences": {"rice_sethy": "CC BY 4.0 (Mendeley 10.17632/fwcj7stb8r.2)", "rice_bd": "CC BY 4.0 (Project-AgML)",
                     "banana_lsd": "CC BY 4.0 (Project-AgML / Mendeley 10.17632/9tb7k297ff.1)",
                     "plantvillage": "CC BY-SA 3.0 (mohanty/PlantVillage)", "other_*": "CC BY 4.0 (Project-AgML); beans: MIT"},
    }, indent=1), encoding="utf-8")
    print("total", sum(counts.values()), "photos in", OUT)
    return 0


if __name__ == "__main__":
    sys.exit(main())
