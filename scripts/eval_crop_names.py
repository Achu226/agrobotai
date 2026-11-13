"""
How often the deployed disease model names the right plant, on held-out photos it never trained on.

    python scripts/eval_crop_names.py [models/disease_model.pt]

For each set it counts: right plant / no name ("not sure" or "not supported") / wrong plant, for
  old  = the crop of the top class, always named (what the app showed before 2026-11-13)
  new  = src.crop_classifier.crop_from_probs on temperature-scaled probabilities (named only when sure)
Garden plants (rose, hibiscus, money plant, marigold) and Other_plant are not supported crops, so any name is wrong.
Prints a JSON summary on the last line.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import torch
from torch.utils.data import DataLoader

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from scripts.compare_disease_models import load  # noqa: E402
from scripts.train_field_model import EVAL_TF, Images, files  # noqa: E402
from src.config import OTHER_PLANT_CLASS, crop_of_disease_label  # noqa: E402
from src.crop_classifier import crop_from_probs  # noqa: E402

SETS = {
    "lab (tomato, potato, pepper)": ROOT / "data/disease/test",
    "field photos (PlantDoc)": ROOT / "data/plantdoc_v2/test",
    "added crops + other plants": ROOT / "data/disease_ext/test",
    "garden plants (not supported)": ROOT / "data/disease_garden/test",
}


def true_crop(set_name: str, cls: str) -> str | None:
    if "garden" in set_name or cls == OTHER_PLANT_CLASS:
        return None
    return crop_of_disease_label(cls)


def main():
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "models/disease_model.pt"
    model, classes = load(path)
    temp = json.loads((ROOT / "models/calibration.json").read_text())["disease"]["temperature"]
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model.to(device)
    summary = {}
    for name, root in SETS.items():
        items = [(p, 0, False) for c in sorted(d.name for d in root.iterdir() if d.is_dir()) for p in files(root, c)]
        truth = [true_crop(name, p.parent.name) for p, _, _ in items]
        probs = []
        with torch.no_grad():
            for x, _ in DataLoader(Images(items, EVAL_TF), batch_size=64, num_workers=4):
                probs += torch.softmax(model(x.to(device)).float() / temp, 1).cpu().numpy().tolist()
        counts = {k: {"right": 0, "no_name": 0, "wrong": 0} for k in ("old", "new")}
        for t, p in zip(truth, probs):
            top = classes[max(range(len(p)), key=p.__getitem__)]
            # crop_from_probs indexes probabilities by the deployed class order (config.DISEASE_CLASSES)
            for k, said in (("old", crop_of_disease_label(top)), ("new", crop_from_probs(p)[0])):
                counts[k]["no_name" if said is None else "right" if said == t else "wrong"] += 1
        n = len(items)
        summary[name] = {"n": n, **{k: {m: round(100 * v / n, 1) for m, v in c.items()} for k, c in counts.items()}}
        print(f"{name:32s} n={n:5d}  old {summary[name]['old']}  new {summary[name]['new']}")
    print(json.dumps(summary))


if __name__ == "__main__":
    main()
