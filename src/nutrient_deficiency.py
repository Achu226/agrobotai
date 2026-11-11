"""
Nutrient Deficiency Detection Module
Detects N-P-K (Nitrogen, Phosphorus, Potassium) and micronutrient deficiencies
Uses color analysis, pattern detection, and optional deep learning model
"""

from __future__ import annotations
import cv2
import numpy as np
from typing import Dict, Any, Optional
from pathlib import Path


def analyze_nutrient_deficiency(
    image_rgb: np.ndarray,
    model=None
) -> Dict[str, Any]:
    """
    Detect nutrient deficiencies using color/pattern analysis

    Primary Nutrient Deficiency Symptoms:
    - Nitrogen (N): General yellowing (chlorosis) of older/lower leaves, uniform pale green
    - Phosphorus (P): Dark green/purple/reddish tints, especially leaf edges and stems
    - Potassium (K): Yellowing/browning at leaf margins (marginal chlorosis/necrosis)
    - Iron (Fe): Interveinal chlorosis - yellow between veins, veins stay green
    - Zinc (Zn): Similar to Fe, but on younger leaves; stunted growth
    - Magnesium (Mg): Yellowing starts from leaf edges inward (older leaves first)

    Args:
        image_rgb: RGB image as numpy array
        model: Optional trained deep learning classifier for nutrient deficiency

    Returns:
        Dict with deficiency classification and recommendations
    """
    if image_rgb is None or not isinstance(image_rgb, np.ndarray) or image_rgb.size == 0:
        return {
            "ok": False,
            "error": "Invalid image",
            "deficiency": "Unknown",
            "confidence": 0.0,
            "score": 100.0
        }

    # If deep learning model is provided, use it
    if model is not None:
        return _model_based_detection(image_rgb, model)

    # Otherwise use rule-based color/pattern analysis
    return _rule_based_detection(image_rgb)


def _model_based_detection(image_rgb: np.ndarray, model) -> Dict[str, Any]:
    """Use trained deep learning model for nutrient deficiency classification"""
    try:
        import torch
        from torchvision import transforms
        from PIL import Image

        # Preprocessing
        transform = transforms.Compose([
            transforms.Resize((224, 224)),
            transforms.ToTensor(),
            transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
        ])

        img_pil = Image.fromarray(image_rgb)
        img_tensor = transform(img_pil).unsqueeze(0)

        device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        model = model.to(device)
        img_tensor = img_tensor.to(device)

        model.eval()
        with torch.no_grad():
            outputs = model(img_tensor)
            probabilities = torch.softmax(outputs, dim=1)[0]
            confidence, predicted_idx = torch.max(probabilities, 0)

        # Map prediction to nutrient class
        nutrient_classes = [
            "Healthy",
            "Nitrogen Deficiency",
            "Phosphorus Deficiency",
            "Potassium Deficiency",
            "Iron Deficiency",
            "Zinc Deficiency",
            "Magnesium Deficiency"
        ]

        deficiency = nutrient_classes[predicted_idx.item()]
        confidence_val = round(confidence.item() * 100, 2)

        return {
            "ok": True,
            "deficiency": deficiency,
            "confidence": confidence_val,
            "score": 100.0 if deficiency == "Healthy" else round(100 - confidence_val, 1),
            "method": "deep_learning",
            **_get_nutrient_recommendations(deficiency)
        }

    except Exception as e:
        return {
            "ok": False,
            "error": f"Model inference failed: {str(e)}",
            "deficiency": "Unknown",
            "confidence": 0.0
        }


def _rule_based_detection(image_rgb: np.ndarray) -> Dict[str, Any]:
    """Rule-based nutrient deficiency detection using color analysis"""

    h, w = image_rgb.shape[:2]
    hsv = cv2.cvtColor(image_rgb, cv2.COLOR_RGB2HSV)
    lab = cv2.cvtColor(image_rgb, cv2.COLOR_RGB2LAB)

    # Segment leaf mask (exclude background)
    lower_green = np.array([25, 20, 20])
    upper_green = np.array([95, 255, 255])
    mask_green = cv2.inRange(hsv, lower_green, upper_green)

    # Also capture yellowed/chlorotic regions
    lower_yellow = np.array([15, 30, 100])
    upper_yellow = np.array([35, 255, 255])
    mask_yellow = cv2.inRange(hsv, lower_yellow, upper_yellow)

    # Purplish/reddish tints (phosphorus deficiency symptom)
    lower_purple = np.array([130, 30, 30])
    upper_purple = np.array([170, 255, 200])
    mask_purple = cv2.inRange(hsv, lower_purple, upper_purple)

    leaf_mask = cv2.bitwise_or(mask_green, mask_yellow)
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    leaf_mask = cv2.morphologyEx(leaf_mask, cv2.MORPH_CLOSE, kernel)

    total_leaf_pixels = np.count_nonzero(leaf_mask)
    if total_leaf_pixels < 1000:
        return {
            "ok": False,
            "error": "Insufficient leaf area detected",
            "deficiency": "Indeterminate",
            "confidence": 0.0,
            "score": 50.0
        }

    yellow_pixels = np.count_nonzero(mask_yellow)
    purple_pixels = np.count_nonzero(mask_purple)

    yellow_ratio = yellow_pixels / total_leaf_pixels
    purple_ratio = purple_pixels / total_leaf_pixels

    # Extract color features
    leaf_region = cv2.bitwise_and(image_rgb, image_rgb, mask=leaf_mask)
    leaf_pixels = leaf_region[leaf_mask > 0]

    mean_r = np.mean(leaf_pixels[:, 0])
    mean_g = np.mean(leaf_pixels[:, 1])
    mean_b = np.mean(leaf_pixels[:, 2])

    # Calculate hue histogram on leaf region
    hsv_leaf = hsv[leaf_mask > 0]
    hue_values = hsv_leaf[:, 0]
    hue_hist, _ = np.histogram(hue_values, bins=180, range=(0, 180))

    # Green dominance: healthy leaves
    green_hue_peak = np.sum(hue_hist[30:80])
    yellow_hue_peak = np.sum(hue_hist[15:35])

    # Detection Logic
    scores = {
        "Healthy": 0.0,
        "Nitrogen Deficiency": 0.0,
        "Phosphorus Deficiency": 0.0,
        "Potassium Deficiency": 0.0,
        "Iron Deficiency": 0.0,
        "Magnesium Deficiency": 0.0
    }

    # 1. Nitrogen Deficiency: General pale yellow-green, high yellow ratio
    if yellow_ratio > 0.25:
        scores["Nitrogen Deficiency"] += yellow_ratio * 100
        # Low saturation + high yellowing = nitrogen
        if np.mean(hsv_leaf[:, 1]) < 90:
            scores["Nitrogen Deficiency"] += 20

    # 2. Phosphorus Deficiency: Purple/reddish tint, dark green base
    if purple_ratio > 0.08 or mean_r > mean_g * 1.1:
        scores["Phosphorus Deficiency"] += purple_ratio * 150 + 15

    # 3. Potassium Deficiency: Marginal chlorosis (edge detection + yellow)
    # Detect edges and check if yellow concentrated there
    gray = cv2.cvtColor(image_rgb, cv2.COLOR_RGB2GRAY)
    edges = cv2.Canny(gray, 50, 150)
    edge_yellow_overlap = cv2.bitwise_and(mask_yellow, edges)
    edge_yellow_ratio = np.count_nonzero(edge_yellow_overlap) / max(np.count_nonzero(edges), 1)

    if edge_yellow_ratio > 0.15 and yellow_ratio > 0.15:
        scores["Potassium Deficiency"] += edge_yellow_ratio * 80 + 10

    # 4. Iron Deficiency: Interveinal chlorosis (yellow with green veins)
    # Detect veins as darker green lines
    lab_b = lab[:, :, 2]  # Yellow-blue channel
    veins_mask = cv2.inRange(lab_b, 0, 115)  # Veins are more blue (less yellow)
    veins_on_leaf = cv2.bitwise_and(veins_mask, leaf_mask)

    yellow_intervein = cv2.bitwise_and(mask_yellow, cv2.bitwise_not(veins_on_leaf))
    intervein_ratio = np.count_nonzero(yellow_intervein) / max(total_leaf_pixels, 1)

    if intervein_ratio > 0.20:
        scores["Iron Deficiency"] += intervein_ratio * 120

    # 5. Magnesium Deficiency: Similar to potassium but affects older leaves, edge inward yellowing
    if yellow_ratio > 0.18 and edge_yellow_ratio > 0.10:
        scores["Magnesium Deficiency"] += (yellow_ratio + edge_yellow_ratio) * 40

    # 6. Healthy: Strong green, low yellowing
    if yellow_ratio < 0.15 and purple_ratio < 0.05 and green_hue_peak > yellow_hue_peak * 1.5:
        scores["Healthy"] = 80 - (yellow_ratio * 100)

    # Determine final classification
    max_score_key = max(scores, key=scores.get)
    max_score_val = scores[max_score_key]
    confidence = min(max_score_val, 95.0)

    # If all scores are low, mark as healthy or indeterminate
    if confidence < 30:
        max_score_key = "Healthy"
        confidence = 70.0

    health_score = 100.0 if max_score_key == "Healthy" else round(100 - confidence, 1)

    return {
        "ok": True,
        "deficiency": max_score_key,
        "primary_deficiency": max_score_key,  # Frontend compatibility
        "has_deficiency": max_score_key != "Healthy",  # Frontend compatibility
        "confidence": round(confidence, 2),
        "score": health_score,
        "method": "rule_based",
        "affected_leaf_zone": "Uniform" if max_score_key == "Healthy" else "Marginal / Interveinal",  # Frontend compatibility
        "yellow_ratio": round(yellow_ratio * 100, 2),
        "purple_ratio": round(purple_ratio * 100, 2),
        **_get_nutrient_recommendations(max_score_key)
    }


def _get_nutrient_recommendations(deficiency: str) -> Dict[str, Any]:
    """Get fertilization recommendations based on detected deficiency"""

    recommendations = {
        "Healthy": {
            "display_name": "No Nutrient Deficiency Detected",
            "fertilizer": "Maintain balanced NPK fertilization schedule",
            "organic_options": ["Compost tea", "Balanced organic NPK blend"],
            "application_rate": "Follow standard crop recommendations",
            "immediate_action": "Continue preventive nutrient management",
            "chemical_formula": "N-P-K balanced (e.g., 10-10-10)",
            "severity": 0.0
        },
        "Nitrogen Deficiency": {
            "display_name": "Nitrogen (N) Deficiency",
            "fertilizer": "High nitrogen fertilizer (Urea, Ammonium Nitrate)",
            "organic_options": ["Blood meal", "Fish emulsion", "Composted manure"],
            "application_rate": "46 kg Urea (46-0-0) per acre OR 20-30 kg N/ha",
            "immediate_action": "Foliar spray with 2% Urea solution for rapid correction",
            "chemical_formula": "CO(NH₂)₂ (Urea), NH₄NO₃ (Ammonium Nitrate)",
            "severity": 0.7
        },
        "Phosphorus Deficiency": {
            "display_name": "Phosphorus (P) Deficiency",
            "fertilizer": "Triple Super Phosphate (TSP), Diammonium Phosphate (DAP)",
            "organic_options": ["Rock phosphate", "Bone meal"],
            "application_rate": "50-75 kg DAP (18-46-0) per acre",
            "immediate_action": "Apply water-soluble phosphorus fertilizer to soil around root zone",
            "chemical_formula": "Ca(H₂PO₄)₂ (TSP), (NH₄)₂HPO₄ (DAP)",
            "severity": 0.75
        },
        "Potassium Deficiency": {
            "display_name": "Potassium (K) Deficiency",
            "fertilizer": "Muriate of Potash (MOP / KCl), Sulphate of Potash (SOP)",
            "organic_options": ["Wood ash", "Kelp meal", "Greensand"],
            "application_rate": "40-60 kg MOP (0-0-60) per acre",
            "immediate_action": "Foliar spray with 1-2% KCl solution",
            "chemical_formula": "KCl (Muriate of Potash), K₂SO₄ (Sulphate of Potash)",
            "severity": 0.75
        },
        "Iron Deficiency": {
            "display_name": "Iron (Fe) Deficiency - Interveinal Chlorosis",
            "fertilizer": "Iron chelate (Fe-EDTA, Fe-DTPA)",
            "organic_options": ["Iron sulfate (Ferrous Sulfate)"],
            "application_rate": "2-5 kg Ferrous Sulfate per acre OR foliar Fe-EDTA 0.5%",
            "immediate_action": "Immediate foliar spray with chelated iron for rapid greening",
            "chemical_formula": "FeSO₄ (Ferrous Sulfate), Fe-EDTA (Chelated Iron)",
            "severity": 0.6
        },
        "Zinc Deficiency": {
            "display_name": "Zinc (Zn) Deficiency",
            "fertilizer": "Zinc Sulfate (ZnSO₄)",
            "organic_options": ["Zinc oxide dust"],
            "application_rate": "10-25 kg Zinc Sulfate per acre OR 0.5% foliar spray",
            "immediate_action": "Foliar application of 0.5% Zinc Sulfate solution",
            "chemical_formula": "ZnSO₄·7H₂O (Zinc Sulfate Heptahydrate)",
            "severity": 0.65
        },
        "Magnesium Deficiency": {
            "display_name": "Magnesium (Mg) Deficiency",
            "fertilizer": "Epsom Salt (Magnesium Sulfate)",
            "organic_options": ["Dolomitic lime (if soil pH is low)"],
            "application_rate": "10-20 kg Epsom Salt per acre OR 2% foliar spray",
            "immediate_action": "Dissolve 20g Epsom Salt per liter water, spray on leaves",
            "chemical_formula": "MgSO₄·7H₂O (Magnesium Sulfate Heptahydrate)",
            "severity": 0.65
        }
    }

    return recommendations.get(deficiency, recommendations["Healthy"])
