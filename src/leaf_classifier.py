"""
Leaf Species Classification Module
Identifies plant species from leaf images using deep learning
"""

from __future__ import annotations
import numpy as np
from typing import Dict, Any, Optional
from pathlib import Path


# Plant species that can be identified
LEAF_SPECIES = {
    0: "Tomato",
    1: "Potato",
    2: "Bell Pepper",
    3: "Green Chilli",
    4: "Brinjal (Eggplant)",
    5: "Corn (Maize)",
    6: "Rice (Paddy)",
    7: "Wheat",
    8: "Cotton",
    9: "Sugarcane",
    10: "Soybean",
    11: "Mango",
    12: "Banana",
    13: "Coconut",
    14: "Tea",
    15: "Coffee"
}


def classify_leaf_species(
    image_rgb: np.ndarray,
    model=None
) -> Dict[str, Any]:
    """
    Classify plant species from leaf image

    Args:
        image_rgb: RGB image as numpy array
        model: Optional trained classification model

    Returns:
        Dictionary with species classification results
    """
    if image_rgb is None or not isinstance(image_rgb, np.ndarray) or image_rgb.size == 0:
        return {
            "ok": False,
            "error": "Invalid image",
            "species": "Unknown",
            "confidence": 0.0
        }

    # If model is provided, use it
    if model is not None:
        return _model_based_classification(image_rgb, model)

    # Otherwise use rule-based color/shape analysis
    return _rule_based_classification(image_rgb)


def _model_based_classification(image_rgb: np.ndarray, model) -> Dict[str, Any]:
    """Use trained deep learning model for species classification"""
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

        species = LEAF_SPECIES.get(predicted_idx.item(), "Unknown")
        confidence_val = round(confidence.item() * 100, 2)

        return {
            "ok": True,
            "species": species,
            "confidence": confidence_val,
            "confidence_level": "High" if confidence_val > 75 else "Medium" if confidence_val > 50 else "Low",
            "method": "deep_learning",
            "all_probabilities": {LEAF_SPECIES[i]: round(probabilities[i].item() * 100, 2)
                                 for i in range(len(LEAF_SPECIES))}
        }

    except Exception as e:
        return {
            "ok": False,
            "error": f"Model inference failed: {str(e)}",
            "species": "Unknown",
            "confidence": 0.0
        }


def _rule_based_classification(image_rgb: np.ndarray) -> Dict[str, Any]:
    """
    Rule-based leaf classification using color, texture, and shape features
    This is a basic approach - deep learning models are much more accurate
    """
    import cv2

    h, w = image_rgb.shape[:2]
    hsv = cv2.cvtColor(image_rgb, cv2.COLOR_RGB2HSV)

    # Calculate dominant color
    hue_hist, _ = np.histogram(hsv[:, :, 0], bins=180, range=(0, 180))
    dominant_hue = np.argmax(hue_hist)

    # Calculate mean saturation and value
    mean_saturation = np.mean(hsv[:, :, 1])
    mean_value = np.mean(hsv[:, :, 2])

    # Simple heuristics (this is very basic - real classification needs ML)
    if 30 <= dominant_hue <= 80 and mean_saturation > 50:
        # Green leafy vegetables
        if mean_value > 120:
            species = "Tomato"
            confidence = 65.0
        else:
            species = "Brinjal (Eggplant)"
            confidence = 60.0
    elif dominant_hue < 30 or dominant_hue > 150:
        # Reddish or purplish tint
        species = "Bell Pepper"
        confidence = 55.0
    else:
        # Default to common crop
        species = "Tomato"
        confidence = 50.0

    return {
        "ok": True,
        "species": species,
        "confidence": confidence,
        "confidence_level": "Low",
        "method": "rule_based",
        "note": "For accurate species classification, train a deep learning model on leaf images."
    }
