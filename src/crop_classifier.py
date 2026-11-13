"""Which crop is in the photo, read from the disease model's own output (no colour or shape guessing).

The model's probabilities are added up per crop: it can be unsure between two tomato diseases yet sure the leaf
is tomato. A crop is named only when that sum reaches the same gate the diagnosis uses; otherwise the answer is
"not sure" (None), never a guess.
"""
from __future__ import annotations

import numpy as np

from src.config import (DISEASE_CLASSES, DISEASE_DISPLAY_NAMES, DISEASE_UNCERTAIN_THRESHOLD, OTHER_PLANT_CLASS,
                        crop_of_disease_label)


def crop_probabilities(probs) -> dict[str, float]:
    """probs[i] belongs to DISEASE_CLASSES[i] -> {crop: summed probability}; Other_plant is kept under its own key."""
    out: dict[str, float] = {}
    for i, label in DISEASE_CLASSES.items():
        key = OTHER_PLANT_CLASS if label == OTHER_PLANT_CLASS else crop_of_disease_label(label)
        if key:
            out[key] = out.get(key, 0.0) + float(probs[i])
    return out


def crop_from_probs(probs) -> tuple[str | None, float]:
    """(crop, its summed probability); crop is None when unsure or when the leaf is not a supported plant."""
    sums = crop_probabilities(probs)
    if not sums:
        return None, 0.0
    top = max(sums, key=sums.get)
    if top == OTHER_PLANT_CLASS or sums[top] < DISEASE_UNCERTAIN_THRESHOLD:
        return None, sums[top]
    return top, sums[top]


def classify_crop_type(image_rgb: np.ndarray, disease_result: dict | None = None) -> dict:
    """Crop from the disease model's probabilities (percent, keyed by display name). No model -> ok False."""
    shown = (disease_result or {}).get("probabilities") if (disease_result or {}).get("ok") else None
    if not shown:
        return {"ok": False, "predicted_crop": None, "confidence": 0.0, "probabilities": {},
                "error": "Disease model unavailable, so the crop cannot be identified."}
    probs = np.array([shown.get(DISEASE_DISPLAY_NAMES.get(DISEASE_CLASSES[i], DISEASE_CLASSES[i]), 0.0) / 100.0
                      for i in range(len(DISEASE_CLASSES))])
    crop, conf = crop_from_probs(probs)
    return {"ok": True, "predicted_crop": crop, "confidence": round(conf * 100, 2),
            "probabilities": {k: round(v * 100, 2) for k, v in crop_probabilities(probs).items()}, "error": None}
