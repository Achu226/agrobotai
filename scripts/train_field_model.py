"""
Fine-tunes the disease model for real field photos and adds a 16th class, `Other_plant`.

Starts from models/disease_model.pt (15 PlantVillage classes) and trains on
  data/disease/train            (PlantVillage, lab photos)
  data/plantdoc/train           (PlantDoc, field photos; 15% held out per class for validation)
Field photos are over-sampled to ~40% of every epoch, with field-style augmentation.

Writes models/disease_model_field.pt (the deployed model is not touched). Evaluate it with
scripts/eval_field_photos.py and verify_models.py before swapping it in.

    python scripts/train_field_model.py [epochs] [--resume]   # --resume continues from the saved field model
"""
from __future__ import annotations

import random
import sys
import time
from pathlib import Path

import torch
import torch.nn as nn
from PIL import Image
from torch.utils.data import DataLoader, Dataset, WeightedRandomSampler
from torchvision import models, transforms

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from train_models import DISEASE_CLASSES, IMAGE_MEAN, IMAGE_STD  # noqa: E402

CLASSES = DISEASE_CLASSES + ["Other_plant"]
EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
FIELD_SHARE = 0.4
OUT = ROOT / "models" / "disease_model_field.pt"


def files(root: Path, cls: str) -> list[Path]:
    d = root / cls
    return sorted(f for f in d.iterdir() if f.suffix.lower() in EXTS) if d.is_dir() else []


def build_splits():
    rng = random.Random(1337)
    pv_train = [(f, i, False) for i, c in enumerate(CLASSES) for f in files(ROOT / "data/disease/train", c)]
    pv_val = [(f, i, False) for i, c in enumerate(CLASSES) for f in files(ROOT / "data/disease/val", c)]
    pd_train, pd_val = [], []
    for i, c in enumerate(CLASSES):
        fs = files(ROOT / "data/plantdoc/train", c)
        rng.shuffle(fs)
        n_val = max(1, round(0.15 * len(fs))) if len(fs) >= 5 else 0
        pd_val += [(f, i, True) for f in fs[:n_val]]
        pd_train += [(f, i, True) for f in fs[n_val:]]
    return pv_train, pd_train, pv_val, pd_val


class Images(Dataset):
    def __init__(self, items, transform):
        self.items, self.transform = items, transform

    def __len__(self):
        return len(self.items)

    def __getitem__(self, i):
        path, target, _ = self.items[i]
        return self.transform(Image.open(path).convert("RGB")), target


TRAIN_TF = transforms.Compose([
    transforms.RandomResizedCrop(224, scale=(0.45, 1.0), ratio=(0.75, 1.33)),
    transforms.RandomHorizontalFlip(),
    transforms.RandomVerticalFlip(),
    transforms.RandomRotation(25),
    transforms.ColorJitter(brightness=0.35, contrast=0.35, saturation=0.35, hue=0.04),
    transforms.RandomApply([transforms.GaussianBlur(5, sigma=(0.1, 2.0))], p=0.25),
    transforms.ToTensor(),
    transforms.Normalize(IMAGE_MEAN, IMAGE_STD),
])
EVAL_TF = transforms.Compose([transforms.Resize((224, 224)), transforms.ToTensor(), transforms.Normalize(IMAGE_MEAN, IMAGE_STD)])


def evaluate(model, loader, device):
    model.eval()
    correct = total = 0
    with torch.no_grad():
        for x, y in loader:
            pred = model(x.to(device, non_blocking=True)).argmax(1).cpu()
            correct += int((pred == y).sum())
            total += len(y)
    return 100.0 * correct / max(total, 1)


def _score(lab: float, field: float) -> float:
    # Field accuracy first; lab accuracy breaks ties; falling below 97% on lab photos is penalised hard
    return field + 0.1 * lab + min(lab - 97.0, 0) * 5


def main(epochs: int, resume: bool = False) -> int:
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    pv_train, pd_train, pv_val, pd_val = build_splits()
    train = pv_train + pd_train
    # Each field photo is drawn often enough that field photos make up ~FIELD_SHARE of every epoch
    w_field = FIELD_SHARE / (1 - FIELD_SHARE) * len(pv_train) / len(pd_train)
    weights = [w_field if field else 1.0 for _, _, field in train]
    sampler = WeightedRandomSampler(weights, num_samples=len(train), replacement=True, generator=torch.Generator().manual_seed(7))
    train_loader = DataLoader(Images(train, TRAIN_TF), batch_size=24, sampler=sampler, num_workers=4, pin_memory=True,
                              persistent_workers=True)
    pv_loader = DataLoader(Images(pv_val, EVAL_TF), batch_size=48, num_workers=2)
    pd_loader = DataLoader(Images(pd_val, EVAL_TF), batch_size=48, num_workers=2)
    print(f"train: {len(pv_train)} lab + {len(pd_train)} field (weight {w_field:.2f}); val: {len(pv_val)} lab + {len(pd_val)} field",
          flush=True)

    model = models.efficientnet_v2_s(weights=None)
    in_features = model.classifier[1].in_features
    model.classifier[1] = nn.Sequential(nn.Dropout(0.3), nn.Linear(in_features, len(DISEASE_CLASSES)))
    best = -1.0
    if resume and OUT.exists():
        model.classifier[1][1] = nn.Linear(in_features, len(CLASSES))
        ckpt = torch.load(OUT, map_location="cpu")
        model.load_state_dict(ckpt["model_state_dict"])
        best = _score(ckpt["val_accuracy"], ckpt["val_field_accuracy"])  # only save if better
        print(f"resuming from {OUT.name} (epoch {ckpt['epoch']}, field {ckpt['val_field_accuracy']:.2f}%)", flush=True)
    else:
        ckpt = torch.load(ROOT / "models" / "disease_model.pt", map_location="cpu")
        model.load_state_dict(ckpt["model_state_dict"])
        # Grow the head to 16 classes, keeping the 15 trained rows
        old = model.classifier[1][1]
        new = nn.Linear(in_features, len(CLASSES))
        with torch.no_grad():
            new.weight[: len(DISEASE_CLASSES)] = old.weight
            new.bias[: len(DISEASE_CLASSES)] = old.bias
        model.classifier[1][1] = new
    model = model.to(device)

    head = list(model.classifier.parameters())
    body = [p for n, p in model.named_parameters() if not n.startswith("classifier")]
    opt = torch.optim.AdamW([{"params": body, "lr": 1e-4}, {"params": head, "lr": 1e-3}], weight_decay=1e-4)
    sched = torch.optim.lr_scheduler.OneCycleLR(opt, max_lr=[1e-4, 1e-3], total_steps=epochs * len(train_loader), pct_start=0.15)
    loss_fn = nn.CrossEntropyLoss(label_smoothing=0.05)
    scaler = torch.amp.GradScaler(enabled=device.type == "cuda")

    for epoch in range(1, epochs + 1):
        model.train()
        started, seen, correct = time.time(), 0, 0
        for x, y in train_loader:
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
        lab, field = evaluate(model, pv_loader, device), evaluate(model, pd_loader, device)
        score = _score(lab, field)
        print(f"epoch {epoch}/{epochs}: train acc {100 * correct / seen:.1f}% | val lab {lab:.2f}% | val field {field:.2f}% "
              f"| {time.time() - started:.0f}s", flush=True)
        if score > best:
            best = score
            torch.save({"model_state_dict": model.state_dict(), "classes": CLASSES, "model_name": "efficientnet_v2_s",
                        "val_accuracy": lab, "val_field_accuracy": field, "epoch": epoch}, OUT)
            print(f"  saved {OUT.name} (val lab {lab:.2f}%, field {field:.2f}%)", flush=True)
    return 0


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    sys.exit(main(int(args[0]) if args else 8, resume="--resume" in sys.argv))
