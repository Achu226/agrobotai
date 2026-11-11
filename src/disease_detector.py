from __future__ import annotations

from pathlib import Path

import numpy as np

from src.config import (
    DISEASE_CLASSES,
    DISEASE_DISPLAY_NAMES,
    DISEASE_MODEL_PATH,
    DISEASE_SEVERITY,
    HEALTHY_DISEASE_CLASSES,
    OTHER_PLANT_CLASS,
    HIGH_CONFIDENCE_THRESHOLD,
    LOW_CONFIDENCE_THRESHOLD,
    MODELS_DIR,
)
from src.image_utils import prepare_model_input


class PyTorchDiseaseWrapper:
    def __init__(self, model, device=None, use_tta=True):
        import torch
        self.device = device or torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.model = model.to(self.device)
        self.model.eval()
        self.use_tta = use_tta
        self.mean = torch.tensor([0.485, 0.456, 0.406], device=self.device).view(1, 3, 1, 1)
        self.std = torch.tensor([0.229, 0.224, 0.225], device=self.device).view(1, 3, 1, 1)

    def predict(self, batch_numpy: np.ndarray, verbose=0, use_tta: bool | None = None) -> np.ndarray:
        import torch
        import torch.nn.functional as F

        tta_active = self.use_tta if use_tta is None else use_tta
        tensor = torch.from_numpy(batch_numpy).permute(0, 3, 1, 2).float().to(self.device)
        norm = (tensor - self.mean) / self.std

        with torch.no_grad():
            if tta_active:
                t1 = norm
                t2 = torch.flip(norm, dims=[3])  # horizontal flip
                t3 = torch.flip(norm, dims=[2])  # vertical flip
                t4 = F.interpolate(norm[:, :, 16:208, 16:208], size=(224, 224), mode="bilinear", align_corners=False)  # 85% crop
                t5 = F.interpolate(norm[:, :, 8:216, 8:216], size=(224, 224), mode="bilinear", align_corners=False)   # 92% crop
                t_batch = torch.cat([t1, t2, t3, t4, t5], dim=0)
                output = self.model(t_batch)
                probs = torch.softmax(output, dim=1).mean(dim=0, keepdim=True).cpu().numpy()
            else:
                output = self.model(norm)
                probs = torch.softmax(output, dim=1).cpu().numpy()

        return probs


def _build_disease_backbone(model_name: str, num_classes: int):
    import torch.nn as nn
    from torchvision import models

    if model_name == "convnext_tiny":
        model = models.convnext_tiny(weights=None)
        model.classifier[2] = nn.Sequential(
            nn.Dropout(0.3),
            nn.Linear(model.classifier[2].in_features, num_classes)
        )
    elif model_name == "convnext_small":
        model = models.convnext_small(weights=None)
        model.classifier[2] = nn.Sequential(
            nn.Dropout(0.4),
            nn.Linear(model.classifier[2].in_features, num_classes)
        )
    elif model_name == "efficientnet_v2_s":
        model = models.efficientnet_v2_s(weights=None)
        model.classifier[1] = nn.Sequential(
            nn.Dropout(0.3),
            nn.Linear(model.classifier[1].in_features, num_classes)
        )
    elif model_name == "swin_v2_t":
        model = models.swin_v2_t(weights=None)
        model.head = nn.Sequential(
            nn.Dropout(0.3),
            nn.Linear(model.head.in_features, num_classes)
        )
    else:
        model = models.efficientnet_b0(weights=None)
        model.classifier[1] = nn.Sequential(
            nn.Dropout(0.2),
            nn.Linear(model.classifier[1].in_features, num_classes)
        )
    return model


def load_disease_model(model_path: Path | None = None):
    pt_path = Path(model_path) if model_path else (MODELS_DIR / "disease_model.pt")
    h5_path = Path(model_path) if model_path else DISEASE_MODEL_PATH

    if pt_path.exists():
        try:
            import torch
            device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
            loaded = torch.load(str(pt_path), map_location=device)

            if isinstance(loaded, dict) and "model_state_dict" in loaded:
                model_name = loaded.get("model_name", "convnext_tiny")
                num_classes = len(loaded.get("classes", DISEASE_CLASSES))
                model = _build_disease_backbone(model_name, num_classes)
                model.load_state_dict(loaded["model_state_dict"])
            else:
                import torch.nn as nn
                from torchvision import models
                model = models.efficientnet_b0(weights=None)
                in_features = model.classifier[1].in_features
                model.classifier[1] = nn.Linear(in_features, len(DISEASE_CLASSES))
                model.load_state_dict(loaded)

            return PyTorchDiseaseWrapper(model, device=device)
        except Exception as exc:
            raise RuntimeError(f"Failed to load PyTorch disease model: {exc}") from exc

    if h5_path.exists():
        try:
            from tensorflow.keras.models import load_model
            return load_model(str(h5_path), compile=False)
        except Exception as exc:
            raise RuntimeError(f"TensorFlow is required to load Keras disease model: {exc}") from exc

    raise FileNotFoundError(
        f"Disease model not found at {pt_path} or {h5_path}. Run train_models.py or place disease_model.h5 in models/"
    )


def _top_prediction(probs: np.ndarray) -> tuple[int, str, float]:
    index = int(np.argmax(probs))
    label = DISEASE_CLASSES.get(index, f"unknown_{index}")
    confidence = float(probs[index])
    return index, label, confidence


def score_disease(label: str, confidence: float) -> dict:
    display = DISEASE_DISPLAY_NAMES.get(label, label.replace("_", " ").title())
    severity = float(DISEASE_SEVERITY.get(label, 0.70))
    confidence = float(np.clip(confidence, 0.0, 1.0))
    is_healthy = label in HEALTHY_DISEASE_CLASSES
    low_conf = (not is_healthy) and confidence < LOW_CONFIDENCE_THRESHOLD

    if label == OTHER_PLANT_CLASS:
        # Not a crop the model knows: no diagnosis, so it neither lowers nor raises the health score
        return {"ok": True, "module": "disease", "label": label, "display_name": display, "raw_class": display,
                "is_healthy_class": True, "low_confidence": True, "confidence": round(confidence * 100.0, 2),
                "confidence_raw": confidence, "score": 85.0, "severity": 0.0, "error": None,
                "status": "This leaf does not look like tomato, potato or bell pepper - no diagnosis was made."}

    if is_healthy:
        if confidence >= 0.70:
            score = round(95.0 + 5.0 * min(1.0, (confidence - 0.70) / 0.30), 1)
        elif confidence >= 0.40:
            score = round(85.0 + 10.0 * ((confidence - 0.40) / 0.30), 1)
        else:
            score = round(75.0 + 10.0 * (confidence / 0.40), 1)
        status = "No disease detected — healthy leaf"
        result_label = display
        raw_display = display
    else:
        if low_conf:
            result_label = f"{display} (uncertain)"
            status = f"Low-confidence disease prediction ({round(confidence * 100.0, 1)}%). Confirm symptoms in the field before treating."
            score = round(85.0 + 10.0 * (1.0 - (confidence / LOW_CONFIDENCE_THRESHOLD)), 1)
        else:
            result_label = display
            if confidence >= HIGH_CONFIDENCE_THRESHOLD:
                status = f"{display} detected — high confidence"
            else:
                status = f"{display} detected — moderate confidence"
            score = round(100.0 * (1.0 - confidence * severity), 1)
        raw_display = display

    score = float(np.clip(score, 0.0, 100.0))
    return {
        "ok": True,
        "module": "disease",
        "label": label,
        "display_name": result_label,
        "raw_class": raw_display,
        "is_healthy_class": is_healthy or low_conf,
        "low_confidence": low_conf,
        "confidence": round(confidence * 100.0, 2),
        "confidence_raw": confidence,
        "score": score,
        "status": status,
        "severity": severity if (not is_healthy and not low_conf) else 0.0,
        "error": None,
    }


def detect_disease(image_rgb: np.ndarray, model=None) -> dict:
    if model is None:
        return {
            "ok": False,
            "module": "disease",
            "label": None,
            "display_name": "Unavailable",
            "confidence": None,
            "score": None,
            "status": "Model not loaded",
            "error": "Disease model is not loaded",
        }
    try:
        batch = prepare_model_input(image_rgb)
        preds = model.predict(batch, verbose=0)
        probs = np.asarray(preds)[0]
        if probs.size != len(DISEASE_CLASSES):
            raise RuntimeError(
                f"Disease model output size is {probs.size}, expected {len(DISEASE_CLASSES)} classes"
            )
        _, label, confidence = _top_prediction(probs)
        result = score_disease(label, confidence)
        # Single-view (no TTA) certainty that this is a PlantVillage-style leaf; used by the
        # pest detector to reject false alarms. TTA averaging blurs this signal.
        # Only the 15 crop-leaf classes count: "Other_plant" is high for insect photos too, so it must not
        # make an insect photo look like an ordinary leaf to the pest cross-check.
        leaf_idx = [i for i, name in DISEASE_CLASSES.items() if name != OTHER_PLANT_CLASS]
        try:
            # Without TTA the prediction above already is the single view: skip a second pass
            single = probs if getattr(model, "use_tta", True) is False else np.asarray(model.predict(batch, verbose=0, use_tta=False))[0]
        except TypeError:
            single = probs
        result["single_view_confidence"] = float(np.max(single[leaf_idx]))
        result["probabilities"] = {
            DISEASE_DISPLAY_NAMES[DISEASE_CLASSES[i]]: round(float(probs[i]) * 100.0, 2)
            for i in range(len(DISEASE_CLASSES))
        }
        return result
    except Exception as exc:
        return {
            "ok": False,
            "module": "disease",
            "label": None,
            "display_name": "Failed",
            "confidence": None,
            "score": None,
            "status": "Disease detection failed",
            "error": str(exc),
        }
