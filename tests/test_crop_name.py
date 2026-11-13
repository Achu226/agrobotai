"""The plant name comes only from the disease model, and only when it is sure of the crop."""
import numpy as np

from src.config import DISEASE_CLASSES, DISEASE_DISPLAY_NAMES, OTHER_PLANT_CLASS, crop_of_disease_label
from src.crop_classifier import classify_crop_type, crop_from_probs


def _probs(**by_label):
    p = np.zeros(len(DISEASE_CLASSES))
    for i, label in DISEASE_CLASSES.items():
        p[i] = by_label.get(label, 0.0)
    return p


def _labels(crop):
    return [l for l in DISEASE_CLASSES.values() if crop_of_disease_label(l) == crop]


def test_crop_named_when_its_diseases_together_are_sure():
    a, b = _labels("Tomato")[:2]
    assert crop_from_probs(_probs(**{a: 0.50, b: 0.45, _labels("Potato")[0]: 0.05}))[0] == "Tomato"


def test_unsure_crop_is_not_named():
    crop, conf = crop_from_probs(_probs(**{_labels("Tomato")[0]: 0.6, _labels("Potato")[0]: 0.4}))
    assert crop is None and abs(conf - 0.6) < 1e-9


def test_other_plant_is_not_named():
    assert crop_from_probs(_probs(**{OTHER_PLANT_CLASS: 0.97, _labels("Tomato")[0]: 0.03}))[0] is None


def test_no_model_never_guesses():
    out = classify_crop_type(np.zeros((8, 8, 3), np.uint8), {"ok": False})
    assert out["ok"] is False and out["predicted_crop"] is None


def test_pipeline_shape_from_display_names():
    label = _labels("Potato")[0]
    shown = {DISEASE_DISPLAY_NAMES.get(l, l): (99.0 if l == label else 0.0) for l in DISEASE_CLASSES.values()}
    out = classify_crop_type(np.zeros((8, 8, 3), np.uint8), {"ok": True, "probabilities": shown})
    assert out["predicted_crop"] == "Potato" and out["confidence"] == 99.0
