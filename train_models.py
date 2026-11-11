"""
Training script for top-tier Agricultural CNN model: EfficientNetV2-S (Small).
Optimized for high accuracy on NVIDIA RTX 4050 GPU with Mixed Precision (AMP).
"""

from __future__ import annotations

import os
import random
import sys
import time
from pathlib import Path

import torch
import torch.nn as nn
import torch.optim as optim
from PIL import Image
from torch.utils.data import DataLoader, Dataset
from torchvision import models, transforms

ROOT_DIR = Path(__file__).resolve().parent
DATA_DIR = ROOT_DIR / "data"
MODELS_DIR = ROOT_DIR / "models"
MODELS_DIR.mkdir(parents=True, exist_ok=True)

PEST_CLASSES = [
    "aphids", "armyworm", "beetle", "bollworm", "grasshopper",
    "mites", "mosquito", "sawfly", "stem_borer",
    "no_pest",  # leaves without insects (scripts/build_no_pest_class.py), so the model can say "no pest"
]

DISEASE_CLASSES = [
    "Pepper__bell___Bacterial_spot", "Pepper__bell___healthy",
    "Potato___Early_blight", "Potato___Late_blight", "Potato___healthy",
    "Tomato_Bacterial_spot", "Tomato_Early_blight", "Tomato_Late_blight",
    "Tomato_Leaf_Mold", "Tomato_Septoria_leaf_spot",
    "Tomato_Spider_mites_Two_spotted_spider_mite", "Tomato__Target_Spot",
    "Tomato__Tomato_YellowLeaf__Curl_Virus", "Tomato__Tomato_mosaic_virus",
    "Tomato_healthy",
]

IMAGE_MEAN = [0.485, 0.456, 0.406]
IMAGE_STD = [0.229, 0.224, 0.225]


class StrictFolderDataset(Dataset):
    def __init__(self, root_dir: Path | list[Path], target_classes: list[str], transform=None, max_per_class: int | None = None):
        self.transform = transform
        self.samples = []
        self.class_to_idx = {name: i for i, name in enumerate(target_classes)}
        root_dirs = [root_dir] if isinstance(root_dir, Path) else list(root_dir)

        print("  Class counts:", flush=True)
        for cname in target_classes:
            idx = self.class_to_idx[cname]
            files = []
            for rdir in root_dirs:
                cdir = rdir / cname
                if cdir.is_dir():
                    files.extend([f for f in cdir.iterdir() if f.suffix.lower() in (".jpg", ".jpeg", ".png", ".bmp")])
            files.sort()
            if max_per_class is not None:
                rng = random.Random(42)
                rng.shuffle(files)
                files = files[:max_per_class]
            for f in files:
                self.samples.append((f, idx))
            print(f"    {cname}: {len(files)} images", flush=True)

    def __len__(self):
        return len(self.samples)

    def __getitem__(self, idx):
        path, target = self.samples[idx]
        image = Image.open(path).convert("RGB")
        if self.transform:
            image = self.transform(image)
        return image, target


class TransformSubset(Dataset):
    def __init__(self, base: StrictFolderDataset, indices: list[int], transform):
        self.base = base
        self.indices = indices
        self.transform = transform

    def __len__(self):
        return len(self.indices)

    def __getitem__(self, i):
        path, target = self.base.samples[self.indices[i]]
        image = Image.open(path).convert("RGB")
        if self.transform:
            image = self.transform(image)
        return image, target


def _val_transform():
    return transforms.Compose([
        transforms.Resize((224, 224)),
        transforms.ToTensor(),
        transforms.Normalize(IMAGE_MEAN, IMAGE_STD),
    ])


def _train_transform():
    return transforms.Compose([
        transforms.Resize((224, 224)),
        transforms.RandomHorizontalFlip(),
        transforms.RandomRotation(15),
        transforms.ColorJitter(brightness=0.2, contrast=0.2, saturation=0.2),
        transforms.ToTensor(),
        transforms.Normalize(IMAGE_MEAN, IMAGE_STD),
    ])


def train_model(model_name: str, classes: list[str], data_subdirs: list[str], out_path: Path, epochs_head=3, epochs_fine=4):
    print(f"\n==========================================")
    print(f"🚀 Training {model_name} (EfficientNetV2-S)")
    print(f"==========================================")

    train_roots = [DATA_DIR / sub / "train" for sub in data_subdirs]
    val_roots = [DATA_DIR / sub / "val" for sub in data_subdirs]

    # Fallback to single data folder if val doesn't exist
    has_explicit_val = all(r.exists() for r in val_roots)
    if not has_explicit_val:
        train_roots = [DATA_DIR / sub for sub in data_subdirs]

    base_ds = StrictFolderDataset(train_roots, classes)
    total_len = len(base_ds)
    if total_len == 0:
        print(f"❌ Error: No images found for {model_name} in {train_roots}")
        return

    indices = list(range(total_len))
    random.Random(1337).shuffle(indices)

    if has_explicit_val:
        train_indices = indices
        val_base = StrictFolderDataset(val_roots, classes)
        val_ds = TransformSubset(val_base, list(range(len(val_base))), _val_transform())
    else:
        split = int(0.85 * total_len)
        train_indices = indices[:split]
        val_indices = indices[split:]
        val_ds = TransformSubset(base_ds, val_indices, _val_transform())

    train_ds = TransformSubset(base_ds, train_indices, _train_transform())

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Device: {device} | Train samples: {len(train_ds)} | Val samples: {len(val_ds)}")

    train_loader = DataLoader(train_ds, batch_size=24, shuffle=True, num_workers=2, pin_memory=True)
    val_loader = DataLoader(val_ds, batch_size=32, shuffle=False, num_workers=2, pin_memory=True)

    # Load state-of-the-art EfficientNetV2-S
    try:
        weights = models.EfficientNet_V2_S_Weights.DEFAULT
        model = models.efficientnet_v2_s(weights=weights)
    except Exception:
        model = models.efficientnet_v2_s(weights=None)

    # Replace classifier head
    in_features = model.classifier[1].in_features
    model.classifier[1] = nn.Sequential(
        nn.Dropout(p=0.3, inplace=True),
        nn.Linear(in_features, len(classes))
    )
    model = model.to(device)

    criterion = nn.CrossEntropyLoss()

    # Phase 1: Train classifier head only
    for param in model.parameters():
        param.requires_grad = False
    for param in model.classifier.parameters():
        param.requires_grad = True

    optimizer = optim.AdamW(model.classifier.parameters(), lr=1e-3, weight_decay=1e-4)
    scaler = torch.cuda.amp.GradScaler(enabled=(device.type == "cuda"))

    print(f"\n[Phase 1/2] Training classifier head ({epochs_head} epochs)...")
    best_val_acc = 0.0

    for epoch in range(epochs_head):
        model.train()
        running_loss = 0.0
        correct = 0
        total = 0
        start_t = time.time()

        for batch_idx, (images, targets) in enumerate(train_loader):
            images, targets = images.to(device), targets.to(device)
            optimizer.zero_grad()
            with torch.cuda.amp.autocast(enabled=(device.type == "cuda")):
                outputs = model(images)
                loss = criterion(outputs, targets)
            scaler.scale(loss).backward()
            scaler.step(optimizer)
            scaler.update()

            running_loss += loss.item() * images.size(0)
            _, predicted = outputs.max(1)
            total += targets.size(0)
            correct += predicted.eq(targets).sum().item()

        epoch_loss = running_loss / total
        epoch_acc = 100.0 * correct / total
        print(f"  Head Epoch {epoch+1}/{epochs_head} | Loss: {epoch_loss:.4f} | Train Acc: {epoch_acc:.2f}%")

    # Phase 2: Fine-tune full network
    print(f"\n[Phase 2/2] Fine-tuning full EfficientNetV2-S network ({epochs_fine} epochs)...")
    for param in model.parameters():
        param.requires_grad = True

    optimizer = optim.AdamW(model.parameters(), lr=1e-4, weight_decay=1e-4)
    scheduler = optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=epochs_fine)

    for epoch in range(epochs_fine):
        model.train()
        running_loss = 0.0
        correct = 0
        total = 0

        for images, targets in train_loader:
            images, targets = images.to(device), targets.to(device)
            optimizer.zero_grad()
            with torch.cuda.amp.autocast(enabled=(device.type == "cuda")):
                outputs = model(images)
                loss = criterion(outputs, targets)
            scaler.scale(loss).backward()
            scaler.step(optimizer)
            scaler.update()

            running_loss += loss.item() * images.size(0)
            _, predicted = outputs.max(1)
            total += targets.size(0)
            correct += predicted.eq(targets).sum().item()

        scheduler.step()
        epoch_loss = running_loss / total
        epoch_acc = 100.0 * correct / total

        # Validation
        model.eval()
        val_correct = 0
        val_total = 0
        with torch.no_grad():
            for images, targets in val_loader:
                images, targets = images.to(device), targets.to(device)
                outputs = model(images)
                _, predicted = outputs.max(1)
                val_total += targets.size(0)
                val_correct += predicted.eq(targets).sum().item()

        val_acc = 100.0 * val_correct / val_total if val_total > 0 else 0.0
        print(f"  Fine-tune Epoch {epoch+1}/{epochs_fine} | Loss: {epoch_loss:.4f} | Train Acc: {epoch_acc:.2f}% | Val Acc: {val_acc:.2f}%")

        if val_acc > best_val_acc:
            best_val_acc = val_acc
            torch.save({
                "model_state_dict": model.state_dict(),
                "classes": classes,
                "model_name": "efficientnet_v2_s",
                "val_accuracy": val_acc,
            }, out_path)
            print(f"  💾 Saved best {model_name} model (Val Acc: {val_acc:.2f}%) to {out_path}")

    print(f"✅ Finished training {model_name}! Best Validation Accuracy: {best_val_acc:.2f}%\n")


if __name__ == "__main__":
    if sys.stdout.encoding and sys.stdout.encoding.lower() not in ('utf-8', 'utf8'):
        sys.stdout.reconfigure(encoding='utf-8')
    print("============================================================")
    print("AGROBOTAI: Training State-of-the-Art EfficientNetV2-S Models")
    print("============================================================")

    # Train Pest Model
    train_model(
        model_name="Pest Classification Model",
        classes=PEST_CLASSES,
        data_subdirs=["pest"],
        out_path=MODELS_DIR / "pest_model.pt",
        epochs_head=2,
        epochs_fine=3,
    )

    # Train Disease Model
    train_model(
        model_name="Plant Disease Model",
        classes=DISEASE_CLASSES,
        data_subdirs=["disease"],
        out_path=MODELS_DIR / "disease_model.pt",
        epochs_head=2,
        epochs_fine=3,
    )

    print("============================================================")
    print("🎉 All EfficientNetV2-S models successfully trained & saved!")
    print("============================================================")
