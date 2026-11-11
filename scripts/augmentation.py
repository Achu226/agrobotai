#!/usr/bin/env python
"""
Advanced Augmentation Pipeline using Albumentations
Includes CLAHE, MixUp, CutMix for maximum model generalization
"""

import albumentations as A
from albumentations.pytorch import ToTensorV2
import cv2
import numpy as np
import torch
from typing import Tuple

def get_augmentation_pipeline(
    mode: str = "advanced",
    image_size: Tuple[int, int] = (224, 224)
) -> A.Compose:
    """
    Get augmentation pipeline

    Args:
        mode: 'basic', 'medium', or 'advanced'
        image_size: Target image size

    Returns:
        Albumentations compose pipeline
    """

    if mode == "basic":
        transform = A.Compose([
            A.Resize(image_size[0], image_size[1]),
            A.HorizontalFlip(p=0.5),
            A.VerticalFlip(p=0.5),
            A.Rotate(limit=90, p=0.5),
            A.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
            ToTensorV2(),
        ])

    elif mode == "medium":
        transform = A.Compose([
            A.Resize(image_size[0], image_size[1]),
            A.HorizontalFlip(p=0.5),
            A.VerticalFlip(p=0.5),
            A.Rotate(limit=90, p=0.5),
            A.ShiftScaleRotate(shift_limit=0.1, scale_limit=0.2, rotate_limit=45, p=0.5),
            A.ColorJitter(brightness=0.2, contrast=0.2, saturation=0.2, hue=0.1, p=0.5),
            A.GaussianBlur(blur_limit=(3, 7), p=0.3),
            A.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
            ToTensorV2(),
        ])

    elif mode == "advanced":
        transform = A.Compose([
            # Resize with aspect ratio preservation
            A.LongestMaxSize(max_size=image_size[0] + 32),
            A.PadIfNeeded(
                min_height=image_size[0],
                min_width=image_size[1],
                border_mode=cv2.BORDER_CONSTANT,
                value=0
            ),
            A.RandomCrop(height=image_size[0], width=image_size[1]),

            # Geometric transforms
            A.HorizontalFlip(p=0.5),
            A.VerticalFlip(p=0.5),
            A.Rotate(limit=180, p=0.6),
            A.ShiftScaleRotate(
                shift_limit=0.15,
                scale_limit=0.3,
                rotate_limit=45,
                border_mode=cv2.BORDER_CONSTANT,
                p=0.6
            ),

            # Advanced elastic deformations (simulates real leaf curling)
            A.OneOf([
                A.ElasticTransform(alpha=1, sigma=50, alpha_affine=50, p=1.0),
                A.GridDistortion(p=1.0),
                A.OpticalDistortion(distort_limit=1, shift_limit=0.5, p=1.0),
            ], p=0.3),

            # Color & lighting augmentations
            A.CLAHE(clip_limit=4.0, tile_grid_size=(8, 8), p=0.5),  # Adaptive histogram equalization
            A.RandomBrightnessContrast(brightness_limit=0.25, contrast_limit=0.25, p=0.6),
            A.ColorJitter(brightness=0.2, contrast=0.2, saturation=0.3, hue=0.1, p=0.5),
            A.HueSaturationValue(hue_shift_limit=15, sat_shift_limit=25, val_shift_limit=15, p=0.5),

            # Lighting conditions (simulate field conditions)
            A.OneOf([
                A.RandomShadow(shadow_roi=(0, 0.5, 1, 1), num_shadows_lower=1, num_shadows_upper=3, p=1.0),
                A.RandomSunFlare(flare_roi=(0, 0, 1, 0.5), angle_lower=0, angle_upper=1, p=1.0),
                A.RandomFog(fog_coef_lower=0.1, fog_coef_upper=0.3, alpha_coef=0.1, p=1.0),
            ], p=0.25),

            # Noise & blur (simulates camera shake, motion blur)
            A.OneOf([
                A.GaussianBlur(blur_limit=(3, 7), p=1.0),
                A.MotionBlur(blur_limit=7, p=1.0),
                A.MedianBlur(blur_limit=5, p=1.0),
            ], p=0.3),

            A.OneOf([
                A.GaussNoise(var_limit=(10.0, 50.0), p=1.0),
                A.ISONoise(color_shift=(0.01, 0.05), intensity=(0.1, 0.5), p=1.0),
            ], p=0.2),

            # Coarse dropout (simulates partial occlusions)
            A.CoarseDropout(
                max_holes=8,
                max_height=32,
                max_width=32,
                min_holes=1,
                fill_value=0,
                p=0.3
            ),

            # Normalize with ImageNet stats
            A.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
            ToTensorV2(),
        ])

    else:
        raise ValueError(f"Unknown augmentation mode: {mode}")

    return transform


def get_test_augmentation(image_size: Tuple[int, int] = (224, 224)) -> A.Compose:
    """Get test/validation augmentation (no random transforms)"""
    return A.Compose([
        A.Resize(image_size[0], image_size[1]),
        A.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
        ToTensorV2(),
    ])


def get_tta_augmentations(image_size: Tuple[int, int] = (224, 224)) -> list:
    """
    Get Test-Time Augmentation transforms
    Returns list of transforms for TTA inference
    """
    base_transforms = [
        A.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
        ToTensorV2(),
    ]

    tta_transforms = [
        # Original
        A.Compose([A.Resize(image_size[0], image_size[1])] + base_transforms),

        # Horizontal flip
        A.Compose([
            A.Resize(image_size[0], image_size[1]),
            A.HorizontalFlip(p=1.0)
        ] + base_transforms),

        # Vertical flip
        A.Compose([
            A.Resize(image_size[0], image_size[1]),
            A.VerticalFlip(p=1.0)
        ] + base_transforms),

        # Slight brightness adjustment
        A.Compose([
            A.Resize(image_size[0], image_size[1]),
            A.RandomBrightnessContrast(brightness_limit=0.1, contrast_limit=0.1, p=1.0)
        ] + base_transforms),

        # 90 degree rotation
        A.Compose([
            A.Resize(image_size[0], image_size[1]),
            A.Rotate(limit=(90, 90), p=1.0)
        ] + base_transforms),
    ]

    return tta_transforms


class MixUpCutMixAugmentation:
    """
    MixUp and CutMix augmentation for batches
    Apply after standard augmentations, during training
    """

    def __init__(self, mixup_alpha: float = 0.2, cutmix_alpha: float = 0.2, prob: float = 0.5):
        self.mixup_alpha = mixup_alpha
        self.cutmix_alpha = cutmix_alpha
        self.prob = prob

    def mixup(self, images, labels):
        """MixUp augmentation"""
        if np.random.rand() > self.prob:
            return images, (labels, labels, 1.0)

        batch_size = images.size(0)
        lam = float(np.random.beta(self.mixup_alpha, self.mixup_alpha))

        index = torch.randperm(batch_size)
        mixed_images = lam * images + (1 - lam) * images[index]
        labels_a, labels_b = labels, labels[index]

        return mixed_images, (labels_a, labels_b, lam)

    def cutmix(self, images, labels):
        """CutMix augmentation"""
        if np.random.rand() > self.prob:
            return images, (labels, labels, 1.0)

        batch_size = images.size(0)
        lam = float(np.random.beta(self.cutmix_alpha, self.cutmix_alpha))

        index = torch.randperm(batch_size)

        # Get random box
        _, _, H, W = images.shape
        cut_rat = np.sqrt(1. - lam)
        cut_w = int(W * cut_rat)
        cut_h = int(H * cut_rat)

        cx = np.random.randint(W)
        cy = np.random.randint(H)

        bbx1 = np.clip(cx - cut_w // 2, 0, W)
        bby1 = np.clip(cy - cut_h // 2, 0, H)
        bbx2 = np.clip(cx + cut_w // 2, 0, W)
        bby2 = np.clip(cy + cut_h // 2, 0, H)

        mixed_images = images.clone()
        mixed_images[:, :, bby1:bby2, bbx1:bbx2] = images[index, :, bby1:bby2, bbx1:bbx2]

        # Adjust lambda based on actual box size
        lam = 1.0 - ((bbx2 - bbx1) * (bby2 - bby1) / (W * H))
        labels_a, labels_b = labels, labels[index]

        return mixed_images, (labels_a, labels_b, lam)

    def __call__(self, images, labels, use_cutmix: bool = True):
        """Apply MixUp or CutMix randomly"""
        if use_cutmix and np.random.rand() > 0.5:
            return self.cutmix(images, labels)
        else:
            return self.mixup(images, labels)


if __name__ == "__main__":
    # Test augmentation pipeline
    import matplotlib.pyplot as plt
    from PIL import Image

    print("Testing augmentation pipelines...")

    # Load a sample image
    img = np.array(Image.open("data/pest/test/aphids/jpg_0.jpg"))

    # Test each pipeline
    for mode in ["basic", "medium", "advanced"]:
        transform = get_augmentation_pipeline(mode=mode)

        fig, axes = plt.subplots(2, 4, figsize=(16, 8))
        fig.suptitle(f"Augmentation Mode: {mode.upper()}")

        for i in range(8):
            augmented = transform(image=img)['image']
            # Convert tensor to numpy for visualization
            aug_img = augmented.permute(1, 2, 0).numpy()
            aug_img = aug_img * np.array([0.229, 0.224, 0.225]) + np.array([0.485, 0.456, 0.406])
            aug_img = np.clip(aug_img, 0, 1)

            axes[i // 4, i % 4].imshow(aug_img)
            axes[i // 4, i % 4].axis('off')

        plt.tight_layout()
        plt.savefig(f"outputs/augmentation_{mode}.png", dpi=150)
        print(f"  Saved: outputs/augmentation_{mode}.png")

    print("✅ Augmentation test complete!")
