"""
Grows the deployed disease model with new classes, keeping everything it learned:
  data/disease_ext     rice, banana, 11 PlantVillage crops, Other_plant (scripts/build_extended_dataset.py)
  data/disease_garden  rose, money plant, hibiscus, marigold (scripts/build_garden_dataset.py)

Starts from models/disease_model.pt and trains on
  data/disease/train      PlantVillage tomato/potato/pepper (lab)
  data/disease_ext/train  PlantVillage 23 new classes (lab); rice, banana, Other_plant (field)
  data/disease_garden/train  home-garden plants (field)
  data/plantdoc_v2/train  PlantDoc field photos of all supported crops (15% held out for validation)
Field photos are over-sampled to ~40% of every epoch.

Writes models/disease_model_ext.pt (the deployed model is not touched). Compare it with
scripts/compare_disease_models.py before swapping it in.

    python scripts/train_extended_model.py [epochs] [--garden-as-other]

--garden-as-other: no garden classes; instead a capped sample of the garden photos joins Other_plant, so plants the
model does not support answer "not a supported plant" instead of a wrong crop name. Writes disease_model_ext_other.pt.
"""
from __future__ import annotations

import json
import random
import sys
import time
from pathlib import Path

import torch
import torch.nn as nn
from torch.utils.data import DataLoader, WeightedRandomSampler
from torchvision import models

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from scripts.train_field_model import EVAL_TF, TRAIN_TF, Images, _score, evaluate, files  # noqa: E402

BASE = ROOT / "models" / "disease_model.pt"
OLD_CLASSES = list(torch.load(BASE, map_location="cpu")["classes"])
GARDEN = ROOT / "data/disease_garden"
GARDEN_AS_OTHER = "--garden-as-other" in sys.argv
if GARDEN_AS_OTHER:
    sys.argv.remove("--garden-as-other")
# Garden photos per split added to Other_plant (it has ~600 train photos; all 9k garden photos would swamp it)
GARDEN_CAP = {"train": 1500, "val": 300}
EXTRA_ROOTS = [ROOT / "data/disease_ext"] + ([] if GARDEN_AS_OTHER else [GARDEN])
NEW = [c for r in EXTRA_ROOTS if (r / "sources.json").exists()
       for c in json.loads((r / "sources.json").read_text(encoding="utf-8"))["classes"] if c not in OLD_CLASSES]
NEW = list(dict.fromkeys(NEW))
CLASSES = OLD_CLASSES + NEW
# Files from real field photos (name prefix). The garden sets are NOT listed: they are studio-style photos, and
# counting them as field halved how often PlantDoc photos were drawn (field test fell 69.9 -> 64.4%).
FIELD_SOURCES = ("rice_", "banana_", "other_")
FIELD_SHARE = 0.4
OUT = ROOT / "models" / ("disease_model_ext_other.pt" if GARDEN_AS_OTHER else "disease_model_ext.pt")


def build_splits():
    rng = random.Random(1337)
    lab_train, lab_val, field_train, field_val = [], [], [], []
    for i, c in enumerate(CLASSES):
        for split, lab, field in (("train", lab_train, field_train), ("val", lab_val, field_val)):
            lab += [(f, i, False) for f in files(ROOT / "data/disease" / split, c)]
            for f in (f for r in EXTRA_ROOTS for f in files(r / split, c)):
                (field if f.name.startswith(FIELD_SOURCES) else lab).append((f, i, f.name.startswith(FIELD_SOURCES)))
            if GARDEN_AS_OTHER and c == "Other_plant":
                garden = sorted(f for d in sorted((GARDEN / split).iterdir()) for f in files(GARDEN / split, d.name))
                lab += [(f, i, False) for f in random.Random(split).sample(garden, min(GARDEN_CAP[split], len(garden)))]
        fs = files(ROOT / "data/plantdoc_v2/train", c)
        rng.shuffle(fs)
        n_val = max(1, round(0.15 * len(fs))) if len(fs) >= 5 else 0
        field_val += [(f, i, True) for f in fs[:n_val]]
        field_train += [(f, i, True) for f in fs[n_val:]]
    return lab_train, field_train, lab_val, field_val


def main(epochs: int) -> int:
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    lab_train, field_train, lab_val, field_val = build_splits()
    train = lab_train + field_train
    w_field = FIELD_SHARE / (1 - FIELD_SHARE) * len(lab_train) / len(field_train)
    sampler = WeightedRandomSampler([w_field if field else 1.0 for *_, field in train], num_samples=len(train), replacement=True,
                                    generator=torch.Generator().manual_seed(7))
    train_loader = DataLoader(Images(train, TRAIN_TF), batch_size=24, sampler=sampler, num_workers=6, pin_memory=True,
                              persistent_workers=True)
    lab_loader = DataLoader(Images(lab_val, EVAL_TF), batch_size=48, num_workers=3)
    field_loader = DataLoader(Images(field_val, EVAL_TF), batch_size=48, num_workers=3)
    print(f"{len(CLASSES)} classes ({len(NEW)} new) | train: {len(lab_train)} lab + {len(field_train)} field (weight {w_field:.2f}) | "
          f"val: {len(lab_val)} lab + {len(field_val)} field", flush=True)

    model = models.efficientnet_v2_s(weights=None)
    in_features = model.classifier[1].in_features
    model.classifier[1] = nn.Sequential(nn.Dropout(0.3), nn.Linear(in_features, len(OLD_CLASSES)))
    model.load_state_dict(torch.load(BASE, map_location="cpu")["model_state_dict"])
    old, new = model.classifier[1][1], nn.Linear(in_features, len(CLASSES))
    with torch.no_grad():  # keep the trained output rows; the new rows start fresh
        new.weight[: len(OLD_CLASSES)] = old.weight
        new.bias[: len(OLD_CLASSES)] = old.bias
    model.classifier[1][1] = new
    model = model.to(device)

    head = list(model.classifier.parameters())
    body = [p for n, p in model.named_parameters() if not n.startswith("classifier")]
    opt = torch.optim.AdamW([{"params": body, "lr": 2e-4}, {"params": head, "lr": 2e-3}], weight_decay=1e-4)
    sched = torch.optim.lr_scheduler.OneCycleLR(opt, max_lr=[2e-4, 2e-3], total_steps=epochs * len(train_loader), pct_start=0.15)
    loss_fn = nn.CrossEntropyLoss(label_smoothing=0.05)
    scaler = torch.amp.GradScaler(enabled=device.type == "cuda")
    best = -1e9
    for epoch in range(1, epochs + 1):
        model.train()
        started, seen, correct = time.time(), 0, 0
        for step, (x, y) in enumerate(train_loader, 1):
            x, y = x.to(device, non_blocking=True), y.to(device, non_blocking=True)
            opt.zero_grad(set_to_none=True)
            with torch.autocast(device_type=device.type, enabled=device.type == "cuda"):
                out = model(x)
                loss = loss_fn(out, y)
            scaler.scale(loss).backward()
            scaler.step(opt)
            scaler.update()
            sched.step()
            seen += len(y)
            correct += int((out.argmax(1) == y).sum())
            if step % 300 == 0:
                print(f"  epoch {epoch} step {step}/{len(train_loader)} train acc {100 * correct / seen:.1f}%", flush=True)
        lab, field = evaluate(model, lab_loader, device), evaluate(model, field_loader, device)
        print(f"epoch {epoch}/{epochs}: train acc {100 * correct / seen:.1f}% | val lab {lab:.2f}% | val field {field:.2f}% "
              f"| {time.time() - started:.0f}s", flush=True)
        if (score := _score(lab, field)) > best:
            best = score
            torch.save({"model_state_dict": model.state_dict(), "classes": CLASSES, "model_name": "efficientnet_v2_s",
                        "val_accuracy": lab, "val_field_accuracy": field, "epoch": epoch}, OUT)
            print(f"  saved {OUT.name} (val lab {lab:.2f}%, field {field:.2f}%)", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main(int(sys.argv[1]) if len(sys.argv) > 1 else 6))
