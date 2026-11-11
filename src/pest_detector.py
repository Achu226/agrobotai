from __future__ import annotations

from pathlib import Path
import numpy as np

from src.config import (
    HIGH_CONFIDENCE_THRESHOLD,
    LOW_CONFIDENCE_THRESHOLD,
    MODELS_DIR,
    PEST_CLASSES,
    PEST_DISPLAY_NAMES,
    PEST_MODEL_PATH,
    PEST_SEVERITY,
    PEST_CONFIDENCE_THRESHOLD,
    PEST_MARGIN_THRESHOLD,
    PEST_EVIDENCE_THRESHOLD,
    PEST_UNCERTAIN_LOWER_THRESHOLD,
    PEST_LEAF_SCENE_THRESHOLD,
    PEST_STRONG_CONFIDENCE_THRESHOLD,
)
from src.image_utils import prepare_model_input


class PyTorchPestWrapper:
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


def _build_pest_backbone(model_name: str, num_classes: int):
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


def load_pest_model(model_path: Path | None = None):
    pt_path = Path(model_path) if model_path else (MODELS_DIR / "pest_model.pt")
    h5_path = Path(model_path) if model_path else PEST_MODEL_PATH

    if pt_path.exists():
        try:
            import torch
            device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
            loaded = torch.load(str(pt_path), map_location=device)

            if isinstance(loaded, dict) and "model_state_dict" in loaded:
                model_name = loaded.get("model_name", "convnext_tiny")
                num_classes = len(loaded.get("classes", PEST_CLASSES))
                model = _build_pest_backbone(model_name, num_classes)
                model.load_state_dict(loaded["model_state_dict"])
            else:
                import torch.nn as nn
                from torchvision import models
                model = models.efficientnet_b0(weights=None)
                in_features = model.classifier[1].in_features
                model.classifier[1] = nn.Linear(in_features, len(PEST_CLASSES))
                model.load_state_dict(loaded)

            return PyTorchPestWrapper(model, device=device)
        except Exception as exc:
            raise RuntimeError(f"Failed to load PyTorch pest model: {exc}") from exc

    if h5_path.exists():
        try:
            from tensorflow.keras.models import load_model
            return load_model(str(h5_path), compile=False)
        except Exception as exc:
            raise RuntimeError(f"TensorFlow is required to load Keras pest model: {exc}") from exc

    raise FileNotFoundError(
        f"Pest model not found at {pt_path} or {h5_path}. Run train_models.py or place pest_model.h5 in models/"
    )


def _compute_pest_visual_evidence(image_rgb: np.ndarray) -> tuple[float, dict]:
    """
    Analyzes leaf tissue for morphological evidence of discrete insect pests
    using color segmentation, boundary gradient analysis, and contour morphology.
    Returns (evidence_score, details_dict) where evidence_score in [0.0, 1.0].
    """
    try:
        import cv2

        img_u8 = np.clip(image_rgb, 0, 255).astype(np.uint8)
        h, w = img_u8.shape[:2]
        total_pixels = h * w

        hsv = cv2.cvtColor(img_u8, cv2.COLOR_RGB2HSV)
        lab = cv2.cvtColor(img_u8, cv2.COLOR_RGB2LAB)

        # 1. Segment leaf tissue (green + yellow-green + brown foliage)
        mask_green = cv2.inRange(hsv, np.array([18, 15, 15]), np.array([105, 255, 255]))
        mask_brown = cv2.inRange(hsv, np.array([8, 15, 15]), np.array([28, 255, 220]))
        leaf_mask = cv2.bitwise_or(mask_green, mask_brown)
        leaf_pixels = int(np.count_nonzero(leaf_mask))

        if leaf_pixels < max(300, int(total_pixels * 0.05)):
            return 0.20, {"candidate_objects": 0, "anomaly_area_pct": 0.0, "reason": "Insufficient leaf area"}

        # 2. Extract chromatic & high-frequency edge anomalies on leaf surface
        L, A, B = cv2.split(lab)
        leaf_bool = leaf_mask > 0
        med_L = float(np.median(L[leaf_bool]))
        med_A = float(np.median(A[leaf_bool]))
        med_B = float(np.median(B[leaf_bool]))

        delta_e = np.sqrt((L.astype(float) - med_L) ** 2 + (A.astype(float) - med_A) ** 2 + (B.astype(float) - med_B) ** 2)

        gray = cv2.cvtColor(img_u8, cv2.COLOR_RGB2GRAY)
        grad_x = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
        grad_y = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
        grad_mag = cv2.magnitude(grad_x, grad_y)

        # Discrete candidate pest mask: high color deviation + distinct boundary gradient
        anomaly_mask = (leaf_bool) & (delta_e > 26.0) & (grad_mag > 32.0)
        anomaly_u8 = anomaly_mask.astype(np.uint8) * 255

        # Morphological opening to eliminate noise/vein specks
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
        anomaly_clean = cv2.morphologyEx(anomaly_u8, cv2.MORPH_OPEN, kernel)

        contours, _ = cv2.findContours(anomaly_clean, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        candidate_count = 0
        total_anomaly_area = 0.0

        min_area = max(20.0, 0.0002 * leaf_pixels)
        max_area = 0.15 * leaf_pixels

        for cnt in contours:
            area = float(cv2.contourArea(cnt))
            if min_area <= area <= max_area:
                peri = float(cv2.arcLength(cnt, True))
                if peri > 0:
                    circularity = 4 * np.pi * (area / (peri * peri))
                    # Discrete insect bodies / caterpillars have bounded circularity and distinct aspect ratios
                    if 0.08 <= circularity <= 0.95:
                        candidate_count += 1
                        total_anomaly_area += area

        anomaly_pct = (total_anomaly_area / (leaf_pixels + 1e-5)) * 100.0
        # Calculate normalized visual evidence score
        evidence_score = float(np.clip((candidate_count * 0.12) + (total_anomaly_area / (0.04 * leaf_pixels + 1e-5)) * 0.35, 0.0, 1.0))

        details = {
            "candidate_objects": candidate_count,
            "anomaly_area_pct": round(anomaly_pct, 2),
            "evidence_score": round(evidence_score, 3),
            "leaf_pixels": leaf_pixels,
        }
        return round(evidence_score, 3), details
    except Exception as exc:
        return 0.40, {"candidate_objects": 0, "error": str(exc), "evidence_score": 0.40}


def _top_two_predictions(probs: np.ndarray) -> tuple[int, str, float, int, str, float, float]:
    sorted_indices = np.argsort(probs)[::-1]
    top_idx = int(sorted_indices[0])
    top_label = PEST_CLASSES.get(top_idx, f"unknown_{top_idx}")
    top_conf = float(probs[top_idx])

    if len(sorted_indices) > 1:
        second_idx = int(sorted_indices[1])
        second_label = PEST_CLASSES.get(second_idx, f"unknown_{second_idx}")
        second_conf = float(probs[second_idx])
    else:
        second_idx = top_idx
        second_label = top_label
        second_conf = 0.0

    margin = float(top_conf - second_conf)
    return top_idx, top_label, top_conf, second_idx, second_label, second_conf, margin


def score_pest(
    label: str,
    confidence: float,
    second_label: str = "",
    second_confidence: float = 0.0,
    probability_margin: float = 1.0,
    evidence_score: float = 0.5,
    evidence_details: dict | None = None,
    leaf_confidence: float | None = None,
) -> dict:
    """
    leaf_confidence: top probability from the disease model for the same image. A high value
    means the photo is an ordinary leaf close-up, where the closed-set pest CNN is unreliable.
    """
    display = PEST_DISPLAY_NAMES.get(label, label.replace("_", " ").title())
    second_display = PEST_DISPLAY_NAMES.get(second_label, second_label.replace("_", " ").title()) if second_label else ""
    severity = float(PEST_SEVERITY.get(label, 0.70))
    confidence = float(np.clip(confidence, 0.0, 1.0))
    probability_margin = float(np.clip(probability_margin, 0.0, 1.0))
    evidence_score = float(np.clip(evidence_score, 0.0, 1.0))

    # --- Multi-Factor Open-Set Decision Framework ---
    # 1. Tier 1: Confirmed Pest Infestation
    # Top-1 confidence + Top-1/Top-2 margin, cross-checked against the disease model when available
    # (the morphological evidence score also fires on disease lesions, so it is only the fallback).
    passes_softmax_gates = confidence >= PEST_CONFIDENCE_THRESHOLD and probability_margin >= PEST_MARGIN_THRESHOLD
    is_leaf_scene = leaf_confidence is not None and leaf_confidence >= PEST_LEAF_SCENE_THRESHOLD
    if label == "no_pest":
        # The model itself says the photo shows no insect (trained on lab + field leaves)
        is_confirmed_pest = False
    elif leaf_confidence is None:
        is_confirmed_pest = passes_softmax_gates and evidence_score >= PEST_EVIDENCE_THRESHOLD
    else:
        # Secondary guard: on an ordinary crop-leaf close-up a pest needs very high confidence
        is_confirmed_pest = (passes_softmax_gates and not is_leaf_scene) or confidence >= PEST_STRONG_CONFIDENCE_THRESHOLD

    if is_confirmed_pest:
        pest_detected = True
        display_name = display
        reported_label = label
        is_healthy_class = False
        status = f"{display} detected — high confidence (verified visual evidence)"
        score = round(100.0 * (1.0 - confidence * severity), 1)
        reported_severity = severity
        rejection_reason = None
    elif label != "no_pest" and not is_leaf_scene and (confidence >= PEST_UNCERTAIN_LOWER_THRESHOLD or (leaf_confidence is None and evidence_score >= 0.30)):
        # 2. Tier 2: Possible Pest — Verification Required (e.g. 66.9% sawfly guess on clean foliage)
        pest_detected = False
        display_name = "Possible Pest — Verification Required"
        reported_label = "clean_foliage"
        is_healthy_class = True
        status = "Model confidence/evidence is insufficient for reliable pest identification."
        score = 94.0
        reported_severity = 0.0
        rejection_reason = (
            f"Confidence ({round(confidence * 100.0, 1)}%), margin ({round(probability_margin * 100.0, 1)}%), "
            f"or morphological visual evidence ({evidence_score:.2f}) did not meet confirmation thresholds."
        )
    else:
        # 3. Tier 3: No Visible Pest (Clean foliage / Low confidence)
        pest_detected = False
        display_name = "No Visible Pest"
        reported_label = "clean_foliage"
        is_healthy_class = True
        status = "No visible insect/pest detected in the uploaded image."
        score = 100.0
        reported_severity = 0.0
        rejection_reason = (
            f"The photo looks like an ordinary leaf close-up (disease model {round(leaf_confidence * 100.0, 1)}% sure). "
            f"The pest model was trained on insect photos and is unreliable here, so its guess ({display}, "
            f"{round(confidence * 100.0, 1)}%) is ignored below {round(PEST_STRONG_CONFIDENCE_THRESHOLD * 100)}%."
            if is_leaf_scene else "No visual or statistical evidence of insect pest infestation."
        )

    score = float(np.clip(score, 0.0, 100.0))

    return {
        "ok": True,
        "module": "pest",
        "pest_detected": pest_detected,
        "predicted_class": label,
        "top_prediction": display,
        "top_confidence": round(confidence * 100.0, 2),
        "second_prediction": second_display,
        "second_confidence": round(second_confidence * 100.0, 2),
        "probability_margin": round(probability_margin * 100.0, 2),
        "evidence_score": round(evidence_score, 3),
        "evidence_details": evidence_details or {},
        "leaf_scene_confidence": round(leaf_confidence * 100.0, 2) if leaf_confidence is not None else None,
        "rejection_reason": rejection_reason,
        "label": reported_label,
        "display_name": display_name,
        "raw_class": display,
        "is_healthy_class": is_healthy_class,
        "low_confidence": not pest_detected or confidence < HIGH_CONFIDENCE_THRESHOLD,
        "confidence": round(confidence * 100.0, 2),
        "confidence_raw": confidence,
        "score": score,
        "status": status,
        "severity": reported_severity,
        "error": None,
    }


def detect_pest(image_rgb: np.ndarray, model=None, leaf_confidence: float | None = None) -> dict:
    if model is None:
        return {
            "ok": False,
            "module": "pest",
            "pest_detected": False,
            "label": None,
            "display_name": "Unavailable",
            "confidence": None,
            "score": None,
            "status": "Model not loaded",
            "error": "Pest model is not loaded",
        }
    try:
        # 1. Morphological Visual Evidence Verification on Leaf Tissue
        evidence_score, evidence_details = _compute_pest_visual_evidence(image_rgb)

        # 2. Run DL Model Prediction
        batch = prepare_model_input(image_rgb)
        preds = model.predict(batch, verbose=0)
        probs = np.asarray(preds)[0]
        if probs.size != len(PEST_CLASSES):
            raise RuntimeError(
                f"Pest model output size is {probs.size}, expected {len(PEST_CLASSES)} classes"
            )

        # 3. Top-2 Predictions and Margin
        top_idx, top_label, top_conf, second_idx, second_label, second_conf, margin = _top_two_predictions(probs)

        # 4. Multi-Factor Open-Set Scoring
        result = score_pest(
            label=top_label,
            confidence=top_conf,
            second_label=second_label,
            second_confidence=second_conf,
            probability_margin=margin,
            evidence_score=evidence_score,
            evidence_details=evidence_details,
            leaf_confidence=leaf_confidence,
        )

        result["probabilities"] = {
            PEST_DISPLAY_NAMES[PEST_CLASSES[i]]: round(float(probs[i]) * 100.0, 2)
            for i in range(len(PEST_CLASSES))
        }
        return result
    except Exception as exc:
        return {
            "ok": False,
            "module": "pest",
            "pest_detected": False,
            "label": None,
            "display_name": "Failed",
            "confidence": None,
            "score": None,
            "status": "Pest detection failed",
            "error": str(exc),
        }
