"""
Compares the deployed disease model with a candidate on the same held-out test photos.

    python scripts/compare_disease_models.py models/disease_model.pt models/disease_model_ext.pt

  A  lab test   data/disease/test        tomato, potato, pepper (PlantVillage)
  B  field test data/plantdoc_v2/test    tomato, potato, pepper field photos (PlantDoc)
  D  earlier added crops  data/disease_ext/test   (classes both models know: rice, banana, ...)
  C  new classes data/disease_ext, data/disease_garden, data/plantdoc_v2 test   (candidate only; per class)

The candidate passes only if it loses at most 0.5 points on A, 2 points on B and 1 point on D.
Prints a JSON summary on the last line.
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

import torch
import torch.nn as nn
from torch.utils.data import DataLoader
from torchvision import models

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from scripts.train_field_model import EVAL_TF, Images, files  # noqa: E402

MAX_LAB_LOSS, MAX_FIELD_LOSS, MAX_EARLIER_LOSS = 0.5, 2.0, 1.0


def load(path: Path):
    ckpt = torch.load(path, map_location="cpu")
    model = models.efficientnet_v2_s(weights=None)
    model.classifier[1] = nn.Sequential(nn.Dropout(0.3), nn.Linear(model.classifier[1].in_features, len(ckpt["classes"])))
    model.load_state_dict(ckpt["model_state_dict"])
    return model.eval(), list(ckpt["classes"])


def predict(model, items, device) -> list[int]:
    out = []
    with torch.no_grad():
        for x, _ in DataLoader(Images(items, EVAL_TF), batch_size=64, num_workers=4):
            out += model(x.to(device)).argmax(1).cpu().tolist()
    return out


def accuracy(model, classes, items, device) -> tuple[float, dict]:
    """items: (path, class name). Returns overall % and per-class (correct, total)."""
    idx = [(p, classes.index(c), False) for p, c in items if c in classes]
    preds = predict(model, idx, device)
    per = defaultdict(lambda: [0, 0])
    for (p, t, _), y in zip(idx, preds):
        per[classes[t]][0] += int(y == t)
        per[classes[t]][1] += 1
    total = sum(n for _, n in per.values())
    return (100.0 * sum(c for c, _ in per.values()) / total if total else 0.0), dict(per)


def main(old_path: str, new_path: str) -> int:
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    old, old_classes = load(Path(old_path))
    new, new_classes = load(Path(new_path))
    old, new = old.to(device), new.to(device)
    base = [c for c in old_classes if c != "Other_plant"]
    lab = [(f, c) for c in base for f in files(ROOT / "data/disease/test", c)]
    field = [(f, c) for c in base for f in files(ROOT / "data/plantdoc_v2/test", c)]
    added = [c for c in new_classes if c not in old_classes] + ["Other_plant"]
    newc = [(f, c) for c in added for root in ("data/disease_ext/test", "data/disease_garden/test", "data/plantdoc_v2/test")
            for f in files(ROOT / root, c)]
    earlier = [(f, c) for c in old_classes for f in files(ROOT / "data/disease_ext/test", c)]

    a_old, _ = accuracy(old, old_classes, lab, device)
    a_new, _ = accuracy(new, new_classes, lab, device)
    b_old, _ = accuracy(old, old_classes, field, device)
    b_new, _ = accuracy(new, new_classes, field, device)
    c_new, per = accuracy(new, new_classes, newc, device)
    d_old, _ = accuracy(old, old_classes, earlier, device) if earlier else (0.0, {})
    d_new, _ = accuracy(new, new_classes, earlier, device) if earlier else (0.0, {})
    print(f"A lab test ({len(lab)} photos):   current {a_old:.2f}%  candidate {a_new:.2f}%")
    print(f"B field test ({len(field)} photos): current {b_old:.2f}%  candidate {b_new:.2f}%")
    print(f"D earlier added crops ({len(earlier)} photos): current {d_old:.2f}%  candidate {d_new:.2f}%")
    print(f"C new classes ({len(newc)} photos):  candidate {c_new:.2f}%")
    for c, (ok, n) in sorted(per.items(), key=lambda kv: kv[1][0] / kv[1][1]):
        print(f"   {c:28s} {ok:4d}/{n:<4d} {100 * ok / n:5.1f}%")
    passed = a_new >= a_old - MAX_LAB_LOSS and b_new >= b_old - MAX_FIELD_LOSS and d_new >= d_old - MAX_EARLIER_LOSS
    print("PASS: candidate may replace the current model" if passed else "FAIL: keep the current model")
    print(json.dumps({"lab": [a_old, a_new], "field": [b_old, b_new], "earlier": [d_old, d_new], "new_crops": c_new,
                      "passed": passed}))
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:3]))
