#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Dataset Preparation Script
Reorganizes train/test folders into train/val/test with stratified splits
"""

import argparse
import shutil
import sys
from pathlib import Path
from typing import List, Tuple
import random
from collections import defaultdict

# Fix Windows console encoding
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except:
        pass

def get_images_by_class(data_dir: Path) -> dict:
    """Get all image paths organized by class"""
    images_by_class = defaultdict(list)

    for class_dir in sorted(data_dir.iterdir()):
        if not class_dir.is_dir():
            continue

        class_name = class_dir.name
        for img_path in class_dir.glob("*"):
            if img_path.suffix.lower() in ['.jpg', '.jpeg', '.png', '.bmp']:
                images_by_class[class_name].append(img_path)

    return images_by_class

def stratified_split(
    images_by_class: dict,
    train_ratio: float,
    val_ratio: float,
    test_ratio: float,
    seed: int = 42
) -> Tuple[dict, dict, dict]:
    """Split images maintaining class distribution"""
    random.seed(seed)

    train_split = defaultdict(list)
    val_split = defaultdict(list)
    test_split = defaultdict(list)

    for class_name, images in images_by_class.items():
        # Shuffle images
        random.shuffle(images)

        total = len(images)
        train_count = int(total * train_ratio)
        val_count = int(total * val_ratio)

        train_split[class_name] = images[:train_count]
        val_split[class_name] = images[train_count:train_count + val_count]
        test_split[class_name] = images[train_count + val_count:]

        print(f"  {class_name}: {len(train_split[class_name])} train, "
              f"{len(val_split[class_name])} val, {len(test_split[class_name])} test")

    return train_split, val_split, test_split

def copy_split_to_folders(split_data: dict, output_dir: Path, split_name: str):
    """Copy images to new folder structure"""
    split_dir = output_dir / split_name
    split_dir.mkdir(parents=True, exist_ok=True)

    for class_name, images in split_data.items():
        class_dir = split_dir / class_name
        class_dir.mkdir(exist_ok=True)

        for img_path in images:
            dest = class_dir / img_path.name
            shutil.copy2(img_path, dest)

def main():
    parser = argparse.ArgumentParser(description="Prepare dataset with stratified splits")
    parser.add_argument("--data-dir", type=str, required=True, help="Path to data directory")
    parser.add_argument("--split", nargs=3, type=float, default=[0.75, 0.15, 0.10],
                       help="Train/Val/Test split ratios (default: 0.75 0.15 0.10)")
    parser.add_argument("--output-dir", type=str, help="Output directory (default: same as data-dir)")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")

    args = parser.parse_args()

    data_dir = Path(args.data_dir)
    output_dir = Path(args.output_dir) if args.output_dir else data_dir

    train_ratio, val_ratio, test_ratio = args.split
    assert abs(sum(args.split) - 1.0) < 0.01, "Split ratios must sum to 1.0"

    print(f"📊 Preparing dataset from: {data_dir}")
    print(f"   Split: {train_ratio:.1%} train / {val_ratio:.1%} val / {test_ratio:.1%} test")

    # Check if data is already split into train/test
    if (data_dir / "train").exists() and (data_dir / "test").exists():
        print("\n🔍 Detected existing train/test split. Merging first...")
        train_images = get_images_by_class(data_dir / "train")
        test_images = get_images_by_class(data_dir / "test")

        # Merge
        all_images = defaultdict(list)
        for class_name in set(list(train_images.keys()) + list(test_images.keys())):
            all_images[class_name].extend(train_images.get(class_name, []))
            all_images[class_name].extend(test_images.get(class_name, []))
    else:
        print("\n🔍 Loading images from flat structure...")
        all_images = get_images_by_class(data_dir)

    total_images = sum(len(imgs) for imgs in all_images.values())
    print(f"   Found {len(all_images)} classes, {total_images} total images")

    # Perform stratified split
    print("\n✂️  Splitting dataset...")
    train_split, val_split, test_split = stratified_split(
        all_images, train_ratio, val_ratio, test_ratio, seed=args.seed
    )

    # Create backup of old structure
    if (output_dir / "train").exists():
        backup_dir = output_dir.parent / f"{output_dir.name}_backup"
        if not backup_dir.exists():
            print(f"\n💾 Backing up old structure to: {backup_dir}")
            shutil.copytree(output_dir, backup_dir)
        # Update file pointers to point to backup
        for split in (train_split, val_split, test_split):
            for cls, imgs in split.items():
                split[cls] = [backup_dir / img.relative_to(output_dir) if output_dir in img.parents else img for img in imgs]
        if (output_dir / "train").exists():
            shutil.rmtree(output_dir / "train")
        if (output_dir / "test").exists():
            shutil.rmtree(output_dir / "test")
        if (output_dir / "val").exists():
            shutil.rmtree(output_dir / "val")

    # Copy to new structure
    print("\n📁 Creating new folder structure...")
    copy_split_to_folders(train_split, output_dir, "train")
    copy_split_to_folders(val_split, output_dir, "val")
    copy_split_to_folders(test_split, output_dir, "test")

    print("\n✅ Dataset preparation complete!")
    print(f"   Output: {output_dir}")
    print(f"   Structure:")
    print(f"     train/  ({sum(len(imgs) for imgs in train_split.values())} images)")
    print(f"     val/    ({sum(len(imgs) for imgs in val_split.values())} images)")
    print(f"     test/   ({sum(len(imgs) for imgs in test_split.values())} images)")

if __name__ == "__main__":
    main()
