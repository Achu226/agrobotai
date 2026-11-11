"""
Downloads the open leaf datasets used to extend the disease model (rice, banana, 11 PlantVillage crops)
and the "not a supported crop" examples. Everything lands in data/new_raw/<source>/; nothing else is touched.

    .venv\\Scripts\\python.exe scripts\\download_leaf_datasets.py

Sources and licences (keep this list with the trained model):
  rice_sethy      Mendeley 10.17632/fwcj7stb8r.2 (Sethy et al. 2020)                 CC BY 4.0
  rice_bd         huggingface.co/datasets/Project-AgML/rice_disease_classification_bangladesh (raw)   CC BY 4.0
  banana_lsd      huggingface.co/datasets/Project-AgML/BananaLSD_leaf_disease_classification (raw)    CC BY 4.0
  plantvillage    huggingface.co/datasets/mohanty/PlantVillage (Hughes & Salathe 2015)               CC BY-SA 3.0
  other plants    Project-AgML datasets listed in OTHER_PLANTS (CC BY 4.0) and AI-Lab-Makerere/beans (MIT)
"""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path

import requests
from huggingface_hub import HfApi, hf_hub_download

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "new_raw"

SETHY = ("https://data.mendeley.com/public-files/datasets/fwcj7stb8r/files/fd8717c4-0d65-4c80-a76c-3b61cb68e80d/file_downloaded",
         "b2d5fbef5a8ef6adefa04a83be7ee5150091f412d40162ecdf9fd2b1b5e24aaf")
# Home-garden plants (Mendeley, all CC BY 4.0): (url, sha256)
GARDEN = {
    "rose": ("https://data.mendeley.com/public-files/datasets/hmjtdzkfh3/files/3b59517a-2736-42cc-997f-69d2f709afc5/file_downloaded",  # 10.17632/hmjtdzkfh3.2
             "bfb635220326986078b113d754aa26d18aa2109ee05365694d71d6e97a26e643"),
    "money_plant": ("https://data.mendeley.com/public-files/datasets/rzjww3vdxt/files/5039834d-d131-4706-b59b-56220d7f4d89/file_downloaded",  # 10.17632/rzjww3vdxt.3
                    "2f32ec8fb54b37737ac785d09858e296bfc906c8229618f6d5b670fbb2bfcd68"),
    "flowers": ("https://data.mendeley.com/public-files/datasets/2vzp6ss7vg/files/97c395f1-e81e-4c52-bb0f-76d00998f8e8/file_downloaded",  # rose/hibiscus/marigold, 10.17632/2vzp6ss7vg.1
                "00e63acd9334e9331b44b769f4732e311fd633755da5b5b30f2d4b1b5993bbd3"),
}
HF_RAW = {
    "rice_bd": "Project-AgML/rice_disease_classification_bangladesh",
    "banana_lsd": "Project-AgML/BananaLSD_leaf_disease_classification",
}
# Leaves of crops the model does NOT support (all CC BY 4.0 unless noted): taught as "Other_plant"
OTHER_PLANTS = [
    "Project-AgML/turmeric_leaf_disease_classification",
    "Project-AgML/COLD_chili_leaf_disease_classification",
    "Project-AgML/betel_leaf_disease_classification_2",
    "Project-AgML/black_gram_disease_classification",
    "Project-AgML/bean_cowpea_leaf_disease_classification",
    "Project-AgML/lemon_leaf_disease_classification",
    "Project-AgML/tea_leaf_disease_classification_bangladesh",
    "Project-AgML/radish_leaf_disease_classification",
    "Project-AgML/IDDMSLD_spinach_leaf_disease_classification",
    "Project-AgML/hog_plum_leaf_disease_classification",
    "AI-Lab-Makerere/beans",  # MIT
]


def fetch(url: str, dest: Path, sha256: str | None = None) -> None:
    if dest.exists() and (sha256 is None or hashlib.file_digest(dest.open("rb"), "sha256").hexdigest() == sha256):  # streamed: 4 GB zips
        print(f"  have {dest.name}")
        return
    dest.parent.mkdir(parents=True, exist_ok=True)
    h = hashlib.sha256()
    with requests.get(url, stream=True, timeout=60) as r:
        r.raise_for_status()
        with open(dest, "wb") as f:
            for chunk in r.iter_content(1 << 20):
                f.write(chunk)
                h.update(chunk)
    if sha256 and h.hexdigest() != sha256:
        dest.unlink()
        raise SystemExit(f"checksum mismatch for {dest.name}")
    print(f"  downloaded {dest.name} ({dest.stat().st_size / 1e6:.0f} MB){' sha256 OK' if sha256 else ''}")


def hf_files(repo: str, prefer: str = "raw/", max_mb: float | None = None) -> list[str]:
    files = [f.path for f in HfApi().list_repo_tree(repo, repo_type="dataset", recursive=True)
             if f.path.endswith(".parquet") and (max_mb is None or (getattr(f, "size", 0) or 0) <= max_mb * 1e6)]
    raw = [f for f in files if f.startswith(prefer)]
    # Original photos only: augmented copies would leak near-duplicates between train and test
    return raw or [f for f in files if "augment" not in f.lower()]


def main() -> int:
    if sys.argv[1:] == ["--garden"]:
        for name, (url, sha) in GARDEN.items():
            print(name)
            fetch(url, OUT / "garden" / name / f"{name}.zip", sha)
        return 0
    print("rice_sethy")
    fetch(SETHY[0], OUT / "rice_sethy" / "rice_sethy.7z", SETHY[1])
    for name, repo in HF_RAW.items():
        print(name)
        for f in hf_files(repo):
            hf_hub_download(repo, f, repo_type="dataset", local_dir=OUT / name)
            print(f"  {f}")
    for repo in OTHER_PLANTS:
        print("other:", repo)
        if any((OUT / "other" / repo.split("/")[1]).glob("**/*.parquet")):
            print("  have it")
            continue
        files = hf_files(repo, max_mb=150)[:1]  # one small shard is plenty for "other plant" examples
        if not files:
            print("  skipped: no shard under 150 MB")
        for f in files:
            hf_hub_download(repo, f, repo_type="dataset", local_dir=OUT / "other" / repo.split("/")[1])
            print(f"  {f}")
    print("plantvillage (2.2 GB)")
    hf_hub_download("mohanty/PlantVillage", "data.zip", repo_type="dataset", local_dir=OUT / "plantvillage")
    print("done")
    return 0


if __name__ == "__main__":
    sys.exit(main())
