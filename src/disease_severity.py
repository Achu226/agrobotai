"""
Disease Severity & Affected Area Calculator
Calculates percentage of leaf surface damaged by lesion, blight, or pest attack
Provides stage classification and visual damage segmentation map
"""

from __future__ import annotations
import base64
import cv2
import numpy as np
from typing import Tuple, Dict, Any


def calculate_disease_severity(
    image_rgb: np.ndarray,
    sensitivity: float = 1.0
) -> Dict[str, Any]:
    """
    Segment diseased/necrotic leaf tissue vs healthy green leaf tissue
    and compute precise damage percentage.

    Args:
        image_rgb: RGB image as uint8 numpy array (H, W, 3)
        sensitivity: multiplier for thresholding sensitivity (default 1.0)

    Returns:
        Dictionary containing:
            - ok (bool)
            - affected_percentage (float, 0.0 - 100.0)
            - healthy_percentage (float, 0.0 - 100.0)
            - total_leaf_pixels (int)
            - diseased_pixels (int)
            - severity_stage (str: 'Healthy', 'Stage 1: Mild', 'Stage 2: Moderate', 'Stage 3: Severe', 'Stage 4: Critical')
            - severity_score (float, 0-100 where 100 is completely healthy)
            - mask_overlay_rgb (np.ndarray: color-coded visualization)
            - recommendation (str)
    """
    if image_rgb is None or not isinstance(image_rgb, np.ndarray) or image_rgb.size == 0:
        return {
            "ok": False,
            "error": "Invalid image array",
            "affected_percentage": 0.0,
            "severity_stage": "Unknown",
            "severity_score": 0.0
        }

    h, w = image_rgb.shape[:2]

    # Convert to HSV and LAB color spaces for robust plant segmentation
    hsv = cv2.cvtColor(image_rgb, cv2.COLOR_RGB2HSV)
    lab = cv2.cvtColor(image_rgb, cv2.COLOR_RGB2LAB)

    # 1. Segment Entire Leaf Mask (Exclude background)
    # Plant leaf HSV range: hue generally between 20 and 95
    # Also exclude very bright or very dark backgrounds
    lower_leaf_1 = np.array([20, 25, 20])
    upper_leaf_1 = np.array([100, 255, 255])
    mask_green = cv2.inRange(hsv, lower_leaf_1, upper_leaf_1)

    # Also capture yellow/brown leaf portions in leaf mask
    lower_leaf_yellow_brown = np.array([10, 30, 20])
    upper_leaf_yellow_brown = np.array([35, 255, 220])
    mask_yellow_brown = cv2.inRange(hsv, lower_leaf_yellow_brown, upper_leaf_yellow_brown)

    # Combined leaf mask
    leaf_mask = cv2.bitwise_or(mask_green, mask_yellow_brown)

    # Morphological clean up of leaf mask
    kernel_leaf = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    leaf_mask = cv2.morphologyEx(leaf_mask, cv2.MORPH_CLOSE, kernel_leaf)
    leaf_mask = cv2.morphologyEx(leaf_mask, cv2.MORPH_OPEN, kernel_leaf)

    total_leaf_pixels = int(np.count_nonzero(leaf_mask))
    total_image_pixels = h * w

    # If leaf coverage is too low, handle gracefully
    if total_leaf_pixels < (total_image_pixels * 0.02):
        _, buf = cv2.imencode('.png', cv2.cvtColor(image_rgb, cv2.COLOR_RGB2BGR))
        base64_img = f"data:image/png;base64,{base64.b64encode(buf).decode('utf-8')}"
        return {
            "ok": False,
            "error": "No sufficient leaf area detected for severity calculation",
            "affected_percentage": 0.0,
            "healthy_percentage": 100.0,
            "total_leaf_pixels": total_leaf_pixels,
            "diseased_pixels": 0,
            "severity_stage": "Indeterminate",
            "severity_score": 50.0,
            "visual_map_base64": base64_img,
            "recommendation": "Please capture the leaf filling most of the camera frame."
        }

    # 2. Segment Diseased/Necrotic Regions on the Leaf Mask
    # Lesions include:
    # A. Brown/Black necrosis (dark spots, early/late blight concentric rings)
    # B. Chlorotic yellow halos / leaf spots
    # C. Rust/Orange/Reddish fungal pustules

    # A: Brown / Necrotic spots (low value, specific hue)
    lower_necrotic = np.array([0, 40, 15])
    upper_necrotic = np.array([25, 255, 140])
    mask_necrotic = cv2.inRange(hsv, lower_necrotic, upper_necrotic)

    # B: Yellow chlorosis / halos
    lower_chlorosis = np.array([18, 60, 130])
    upper_chlorosis = np.array([36, 255, 255])
    mask_chlorosis = cv2.inRange(hsv, lower_chlorosis, upper_chlorosis)

    # C: LAB color space difference: a-channel (green-red) and b-channel (blue-yellow)
    # Lesions have higher 'a' channel (reddish/brown) than healthy green leaves
    a_channel = lab[:, :, 1]
    b_channel = lab[:, :, 2]
    # High 'a' relative to green indicates lesion
    mask_lab_lesion = (a_channel > 132).astype(np.uint8) * 255

    # Combine all lesion indicators
    diseased_raw = cv2.bitwise_or(mask_necrotic, mask_chlorosis)
    diseased_raw = cv2.bitwise_or(diseased_raw, mask_lab_lesion)

    # Restrict disease mask ONLY to the leaf area
    diseased_mask = cv2.bitwise_and(diseased_raw, diseased_raw, mask=leaf_mask)

    # Morphological noise removal for lesions
    kernel_lesion = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    diseased_mask = cv2.morphologyEx(diseased_mask, cv2.MORPH_OPEN, kernel_lesion)

    diseased_pixels = int(np.count_nonzero(diseased_mask))

    # Calculate percentage of affected leaf surface
    affected_pct = round((diseased_pixels / max(total_leaf_pixels, 1)) * 100.0, 2)
    healthy_pct = round(100.0 - affected_pct, 2)

    # Health Severity Score (100 is pristine healthy, 0 is total destruction)
    # Non-linear penalty: damage > 20% severely impairs photosynthesis
    if affected_pct <= 2.0:
        stage = "Healthy / Negligible"
        health_score = round(100.0 - (affected_pct * 3.0), 1)
        recommendation = "Crop is in excellent physiological health. Maintain regular preventive scouting."
    elif affected_pct <= 10.0:
        stage = "Stage 1: Mild (Early Infection)"
        health_score = round(90.0 - ((affected_pct - 2.0) * 2.5), 1)
        recommendation = "Early localized infection detected. Apply biological or preventive fungicide spray to arrest spread."
    elif affected_pct <= 25.0:
        stage = "Stage 2: Moderate"
        health_score = round(70.0 - ((affected_pct - 10.0) * 1.6), 1)
        recommendation = "Active disease spread. Targeted curative chemical or systemic treatment required within 24-48 hours."
    elif affected_pct <= 50.0:
        stage = "Stage 3: Severe"
        health_score = round(45.0 - ((affected_pct - 25.0) * 1.0), 1)
        recommendation = "Severe photosynthetic disruption. Immediate aggressive fungicide/bactericide application and prune heavily infected foliage."
    else:
        stage = "Stage 4: Critical / Defoliation"
        health_score = max(5.0, round(20.0 - ((affected_pct - 50.0) * 0.3), 1))
        recommendation = "Critical systemic damage. Isolate affected plot, remove dead biomass, and initiate intensive rescue protocol."

    # 3. Create Color-Coded Visual Overlay Map
    # Healthy leaf -> Green overlay, Diseased spots -> Red/Magenta highlight
    overlay = image_rgb.copy()

    # Create visual masks
    # Red for disease spots
    overlay[diseased_mask > 0] = [230, 25, 75]  # Bright Crimson

    # Blend overlay with original image for semi-transparent heatmap
    alpha = 0.55
    visual_map = cv2.addWeighted(overlay, alpha, image_rgb, 1 - alpha, 0)

    # Draw contours around lesions for crisp visual inspection
    contours, _ = cv2.findContours(diseased_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    cv2.drawContours(visual_map, contours, -1, (255, 255, 0), 1)  # Yellow border around spots

    # Encode visual map to Base64 data URL for frontend rendering
    _, buf = cv2.imencode('.png', cv2.cvtColor(visual_map, cv2.COLOR_RGB2BGR))
    visual_map_base64 = f"data:image/png;base64,{base64.b64encode(buf).decode('utf-8')}"

    return {
        "ok": True,
        "affected_percentage": affected_pct,
        "healthy_percentage": healthy_pct,
        "total_leaf_pixels": total_leaf_pixels,
        "diseased_pixels": diseased_pixels,
        "severity_stage": stage,
        "severity_score": health_score,
        "visual_map_base64": visual_map_base64,
        "recommendation": recommendation,
        "leaf_coverage_ratio": round(total_leaf_pixels / total_image_pixels, 3)
    }
