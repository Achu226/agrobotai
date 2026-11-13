"""
Real inference for the mobile API: uploaded bytes -> validated image -> trained models ->
an honest, structured result.

Every number in the response comes from an actual model output or measurement. When a model
is missing or fails, the corresponding section says so ("unavailable" / "failed"); nothing is
filled in with placeholder predictions.

Confidence: `model_score` is the raw softmax of the test-time-augmented prediction (what the
classic pipeline uses). `calibrated_confidence` is the single-view softmax after temperature
scaling fitted on the validation split (models/calibration.json); on the held-out test split it
tracks real accuracy closely (ECE < 0.5%), but only for images like the training data.
"""
from __future__ import annotations

import io
import time
import uuid
from datetime import datetime

import numpy as np
from PIL import Image, UnidentifiedImageError

from src import model_registry
from src import farm_advisor
from src.config import (
    CROPS,
    DISEASE_CLASSES,
    DISEASE_DISPLAY_NAMES,
    DISEASE_UNCERTAIN_THRESHOLD,
    HEALTH_WEIGHTS,
    HEALTHY_DISEASE_CLASSES,
    OTHER_PLANT_CLASS,
    PEST_CLASSES,
    PEST_DISPLAY_NAMES,
    RGB_SPECTRAL_LIMITATION,
    SCAN_IMAGES_DIR,
    SUPPORTED_DISEASE_CROPS,
)
from src.crop_classifier import crop_from_probs
from src.disease_detector import detect_disease
from src.image_quality import check_image_quality
from src.image_utils import prepare_model_input
from src.pipeline import analyze_image

# A confirmed pest + disease single-view confidence below this => treat the photo as an insect photo
INSECT_PHOTO_DISEASE_LIMIT = 0.97
UNCERTAIN_MESSAGE = "Unable to make a reliable diagnosis. Please capture a clearer image or consult an agricultural expert."
ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP", "BMP"}
Image.MAX_IMAGE_PIXELS = 60_000_000  # reject decompression bombs


class InferenceError(Exception):
    """Raised with an HTTP status, a machine-readable code and a user-facing message."""

    def __init__(self, status: int, code: str, message: str, extra: dict | None = None):
        super().__init__(message)
        self.status, self.code, self.message, self.extra = status, code, message, extra or {}

    def to_dict(self) -> dict:
        return {"code": self.code, "message": self.message, **self.extra}


# ---------------------------------------------------------------- image input

def decode_image(data: bytes) -> np.ndarray:
    try:
        with Image.open(io.BytesIO(data)) as img:
            fmt = img.format
            if fmt not in ALLOWED_FORMATS:
                raise InferenceError(415, "unsupported_format", f"Unsupported image format ({fmt or 'unknown'}). Use JPEG or PNG.")
            img.load()
            if img.mode == "RGBA":
                bg = Image.new("RGB", img.size, (255, 255, 255))
                bg.paste(img, mask=img.split()[3])
                img = bg
            return np.asarray(img.convert("RGB"), dtype=np.uint8)
    except InferenceError:
        raise
    except Image.DecompressionBombError:
        raise InferenceError(413, "image_too_large", "Image has too many pixels.")
    except (UnidentifiedImageError, OSError, ValueError):
        raise InferenceError(400, "invalid_image", "The file is not a readable image (corrupted or not an image).")


def validate_quality(image_rgb: np.ndarray) -> dict:
    quality = check_image_quality(image_rgb)
    if not quality["ok"]:
        raise InferenceError(422, "poor_image_quality", " ".join(i["message"] for i in quality["issues"]),
                             {"quality": {k: quality[k] for k in ("issues", "metrics")}})
    return quality


def save_scan_image(image_rgb: np.ndarray) -> str:
    """Stores a re-encoded JPEG under a server-generated name (no client-controlled paths)."""
    SCAN_IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    img = Image.fromarray(image_rgb)
    img.thumbnail((1600, 1600))
    path = SCAN_IMAGES_DIR / f"{uuid.uuid4().hex}.jpg"
    img.save(path, format="JPEG", quality=90)
    return str(path)


# ---------------------------------------------------------------- model helpers

def _model_meta(name: str) -> dict:
    info = model_registry.get(name)
    return {"name": name, "version": info.get("version"), "architecture": info.get("architecture"),
            "calibrated": info.get("calibrated", False)}


def calibrated_probs(name: str, image_rgb: np.ndarray) -> np.ndarray:
    info = model_registry.get(name)
    w = info["wrapper"]
    if getattr(w, "onnx", False):
        z = w.logits(prepare_model_input(image_rgb))[0].astype(np.float64) / info.get("temperature", 1.0)
        e = np.exp(z - z.max())
        return (e / e.sum()).astype(np.float32)
    import torch

    t = torch.from_numpy(prepare_model_input(image_rgb)).permute(0, 3, 1, 2).float().to(w.device)
    with torch.inference_mode():
        logits = w.model((t - w.mean) / w.std)[0].float()
        return torch.softmax(logits / info.get("temperature", 1.0), dim=0).cpu().numpy()


def _crop_of_disease_label(label: str) -> str | None:
    from src.config import crop_of_disease_label

    return crop_of_disease_label(label)


def _top_k(probs: np.ndarray, names: dict, display: dict, k: int = 3) -> list[dict]:
    return [{"label": names[int(i)], "display_name": display.get(names[int(i)], names[int(i)]),
             "calibrated_confidence": round(float(probs[i]) * 100, 2)} for i in np.argsort(probs)[::-1][:k]]


def assess_disease(det: dict, cal: np.ndarray | None, crop_selected: str | None, elapsed_ms: float) -> dict:
    meta = _model_meta("disease")
    if not det.get("ok"):
        unavailable = det.get("status") == "Model not loaded"
        return {"state": "unavailable" if unavailable else "failed", "message": det.get("error") or "Disease model failed.",
                "model": meta}
    label = det["label"]
    cal_idx = int(np.argmax(cal))
    cal_conf = float(cal[cal_idx])
    predicted_crop = _crop_of_disease_label(label)
    out = {
        "label": label,
        "display_name": DISEASE_DISPLAY_NAMES.get(label, label),
        "predicted_crop": predicted_crop,
        "model_score": round(float(det["confidence_raw"]) * 100, 2),
        "calibrated_confidence": round(cal_conf * 100, 2),
        "uncertainty_threshold": round(DISEASE_UNCERTAIN_THRESHOLD * 100, 1),
        "top_predictions": _top_k(cal, DISEASE_CLASSES, DISEASE_DISPLAY_NAMES),
        "supported_crops": list(SUPPORTED_DISEASE_CROPS),
        "model": meta,
        "inference_ms": round(elapsed_ms, 1),
    }
    reasons = []
    if label == OTHER_PLANT_CLASS:
        out.update(state="unsupported_crop",
                   message=f"This leaf does not look like {', '.join(SUPPORTED_DISEASE_CROPS)} - the only crops the disease "
                           f"model knows - so no diagnosis was made.")
        return out
    if crop_selected and crop_selected in CROPS and crop_selected not in SUPPORTED_DISEASE_CROPS:
        out.update(state="unsupported_crop",
                   message=f"The disease model was only trained on {', '.join(SUPPORTED_DISEASE_CROPS)}. "
                           f"It cannot diagnose {crop_selected}.")
        return out
    if DISEASE_CLASSES[cal_idx] != label:
        reasons.append("augmented and single-view predictions disagree")
    if cal_conf < DISEASE_UNCERTAIN_THRESHOLD:
        reasons.append(f"calibrated confidence {cal_conf * 100:.1f}% is below {DISEASE_UNCERTAIN_THRESHOLD * 100:.0f}%")
    if crop_selected in SUPPORTED_DISEASE_CROPS and crop_selected != predicted_crop:
        reasons.append(f"model thinks this is {predicted_crop}, but {crop_selected} was selected")
    if reasons:
        out.update(state="uncertain", message=UNCERTAIN_MESSAGE, uncertainty_reasons=reasons)
    elif label in HEALTHY_DISEASE_CLASSES:
        out.update(state="no_disease_detected",
                   message="No supported disease detected. This is not proof the plant is healthy — "
                           "the model only knows the listed diseases.")
    else:
        out.update(state="disease_detected", message=f"{out['display_name']} detected.")
    return out


def assess_pest(det: dict, cal: np.ndarray | None, elapsed_ms: float) -> dict:
    meta = _model_meta("pest")
    base = {
        "model": meta,
        "model_type": "image_classifier",
        "bounding_boxes": None,
        "localization_note": "The pest model classifies the whole image; it cannot locate or count insects.",
    }
    if not det.get("ok"):
        unavailable = det.get("status") == "Model not loaded"
        return base | {"state": "unavailable" if unavailable else "failed",
                       "message": det.get("error") or "Pest model failed."}
    top = det.get("predicted_class")
    out = base | {"inference_ms": round(elapsed_ms, 1), "leaf_scene_confidence": det.get("leaf_scene_confidence")}
    guess = {
        "top_prediction": PEST_DISPLAY_NAMES.get(top, top),
        "model_score": det.get("top_confidence"),
        "calibrated_confidence": round(float(np.max(cal)) * 100, 2) if cal is not None else None,
        "top_predictions": _top_k(cal, PEST_CLASSES, PEST_DISPLAY_NAMES) if cal is not None else [],
    }
    if det.get("pest_detected") or det.get("display_name", "").startswith("Possible Pest"):
        out |= guess
    else:
        # The guess was rejected (e.g. pest model run on a plain leaf). Keep it for audit only;
        # its confidence is not meaningful outside the insect-photo training domain.
        out["rejected_guess"] = guess | {"reason": det.get("rejection_reason")}
    if det.get("pest_detected"):
        return out | {"state": "pest_detected", "label": top, "display_name": PEST_DISPLAY_NAMES.get(top, top),
                      "message": f"{PEST_DISPLAY_NAMES.get(top, top)} detected."}
    if det.get("display_name", "").startswith("Possible Pest"):
        return out | {"state": "possible_pest", "label": None, "display_name": "Possible pest — inspect the leaf",
                      "message": det.get("rejection_reason") or "Pest evidence is not strong enough to confirm."}
    return out | {"state": "no_pest_detected", "label": None, "display_name": "No supported pest detected",
                  "message": "None of the 9 supported insect pests was detected. Other pests may still be present — "
                             "check the underside of leaves."}


def summarize(disease: dict, pest: dict) -> tuple[str, str]:
    d, p = disease["state"], pest["state"]
    if d == "uncertain" and p == "pest_detected":
        return "pest_detected", (f"{pest['message']} The leaf-disease check could not make a reliable diagnosis "
                                 "on this photo — photograph a leaf close-up separately for that.")
    if d == "uncertain":
        return "uncertain", UNCERTAIN_MESSAGE
    if d == "disease_detected" and p == "pest_detected":
        return "disease_and_pest_detected", f"{disease['display_name']} and {pest['display_name']} detected."
    if d == "disease_detected":
        return "disease_detected", disease["message"]
    if p == "pest_detected":
        return "pest_detected", pest["message"]
    if d == "unsupported_crop":
        return "unsupported_crop", disease["message"]
    if p == "possible_pest":
        return "uncertain", "Possible pest — the model is not sure. Inspect the leaf closely."
    if d in ("unavailable", "failed"):
        return "partial", "Disease analysis is unavailable; only the pest check ran."
    return "no_supported_condition_detected", ("No supported disease or pest detected. This does not prove the plant "
                                               "is healthy — check for symptoms outside the supported classes.")


# ---------------------------------------------------------------- public entry points

def predict_disease(image_rgb: np.ndarray, crop: str | None = None) -> dict:
    w = model_registry.wrapper("disease")
    if w is None:
        raise InferenceError(503, "disease_model_unavailable", model_registry.get("disease")["error"] or "Disease model unavailable.")
    started = time.perf_counter()
    det = detect_disease(image_rgb, model=w)
    cal = calibrated_probs("disease", image_rgb) if det.get("ok") else None
    result = assess_disease(det, cal, crop, (time.perf_counter() - started) * 1000)
    if result["state"] == "failed":
        raise InferenceError(500, "inference_failed", result["message"])
    return result | {"inferred_at": datetime.now().astimezone().isoformat(timespec="seconds")}


def predict_pest(image_rgb: np.ndarray) -> dict:
    from src.pest_detector import detect_pest

    w = model_registry.wrapper("pest")
    if w is None:
        raise InferenceError(503, "pest_model_unavailable", model_registry.get("pest")["error"] or "Pest model unavailable.")
    started = time.perf_counter()
    disease_w = model_registry.wrapper("disease")
    leaf_conf = None
    if disease_w is not None:
        d = detect_disease(image_rgb, model=disease_w)
        leaf_conf = d.get("single_view_confidence") if d.get("ok") else None
    det = detect_pest(image_rgb, model=w, leaf_confidence=leaf_conf)
    cal = calibrated_probs("pest", image_rgb) if det.get("ok") else None
    result = assess_pest(det, cal, (time.perf_counter() - started) * 1000)
    if result["state"] == "failed":
        raise InferenceError(500, "inference_failed", result["message"])
    return result | {"inferred_at": datetime.now().astimezone().isoformat(timespec="seconds")}


def _health_index(overall: dict) -> dict | None:
    if not overall or not overall.get("ok"):
        return None
    return {
        "value": overall["overall_score"],
        "status": overall["overall_status"],
        "kind": "heuristic",
        "formula": "weighted mean of available module scores: "
                   + " + ".join(f"{w:.2f}*{k}" for k, w in HEALTH_WEIGHTS.items())
                   + "; weights of missing modules are dropped and the rest renormalised",
        "inputs": overall.get("module_scores"),
        "limitations": "Not validated against field measurements. Spectral inputs are RGB proxies, not true NDRE/CRI.",
    }


ADVISABLE_STATES = ("disease_detected", "pest_detected", "disease_and_pest_detected")


def _extra_view(image_rgb: np.ndarray, n: int) -> np.ndarray:
    """Calibrated disease probabilities of extra photo n, after the same quality and leaf checks as the first."""
    from src.image_utils import validate_plant_image

    quality = check_image_quality(image_rgb)
    if not quality["ok"]:
        raise InferenceError(422, "poor_image_quality", f"Photo {n}: " + " ".join(i["message"] for i in quality["issues"]))
    ok, message, _ = validate_plant_image(image_rgb)
    if not ok:
        raise InferenceError(422, "no_leaf_detected", f"Photo {n}: {message}")
    return calibrated_probs("disease", image_rgb)


def analyze(image_rgb: np.ndarray, crop: str | None = None, include_advice: bool = True, location: str | None = None,
            language: str = "ta", sensors: list[dict] | None = None, extra_images: list[np.ndarray] | None = None) -> dict:
    """Full analysis. Raises InferenceError when nothing could be inferred.
    extra_images: more leaves of the same plant; the disease decision then uses their averaged calibrated probabilities."""
    disease_w, pest_w = model_registry.wrapper("disease"), model_registry.wrapper("pest")
    if disease_w is None and pest_w is None:
        raise InferenceError(503, "models_unavailable", "Neither the disease nor the pest model is loaded.",
                             {"disease_error": model_registry.get("disease")["error"],
                              "pest_error": model_registry.get("pest")["error"]})
    quality = validate_quality(image_rgb)

    started = time.perf_counter()
    crop_arg = crop if crop and crop in CROPS else "Auto-Detect"
    res = analyze_image(image_rgb, crop=crop_arg, pest_model=pest_w, disease_model=disease_w, include_advice=False)
    if not res.get("is_valid_plant"):
        raise InferenceError(422, "no_leaf_detected", res.get("validation_error") or "No plant leaf detected in the photo.",
                             {"leaf_fraction": res.get("leaf_fraction")})
    pipeline_ms = (time.perf_counter() - started) * 1000

    d_cal = calibrated_probs("disease", image_rgb) if res["disease"].get("ok") else None
    p_cal = calibrated_probs("pest", image_rgb) if res["pest"].get("ok") else None
    det, views = res["disease"], [d_cal]
    if extra_images and d_cal is not None:
        views += [_extra_view(img, n) for n, img in enumerate(extra_images, start=2)]
        d_cal = np.mean(views, axis=0)
        det = det | {"label": DISEASE_CLASSES[int(np.argmax(d_cal))], "confidence_raw": float(d_cal.max())}
    disease = assess_disease(det, d_cal, crop if crop in CROPS else None, pipeline_ms)
    if len(views) > 1:
        disease["photos"] = len(views)
        named = {c for c in (crop_from_probs(v)[0] for v in views) if c}
        if len(named) > 1 and disease["state"] in ("disease_detected", "no_disease_detected"):
            disease.update(state="uncertain", message=UNCERTAIN_MESSAGE, uncertainty_reasons=disease.get("uncertainty_reasons", []) + [
                f"the photos seem to show different plants ({', '.join(sorted(named))}); use leaves of one plant"])
    pest = assess_pest(res["pest"], p_cal, pipeline_ms)
    insect_photo = pest["state"] == "pest_detected" and (res["disease"].get("single_view_confidence") or 0) < INSECT_PHOTO_DISEASE_LIMIT
    if insect_photo and disease["state"] in ("disease_detected", "no_disease_detected", "uncertain"):
        disease.update(state="uncertain", message=UNCERTAIN_MESSAGE, uncertainty_reasons=disease.get("uncertainty_reasons", []) + [
            "the photo appears to show an insect rather than a leaf close-up; the disease model was trained on leaf close-ups"])
    if disease["state"] == "failed" and pest["state"] in ("failed", "unavailable"):
        raise InferenceError(500, "inference_failed", f"Inference failed: {disease['message']}")
    summary_state, summary_message = summarize(disease, pest)

    severity = res.get("severity") or {}
    if disease["state"] == "disease_detected" and severity.get("ok"):
        severity_out = {"state": "measured", "affected_pct": severity.get("affected_percentage"),
                        "stage": severity.get("severity_stage"),
                        "method": "HSV/LAB colour segmentation of lesion pixels; not validated against expert annotation"}
    else:
        severity_out = {"state": "not_applicable" if severity.get("ok") else "unavailable", "affected_pct": None}

    gradcam = None
    target = "pest" if pest["state"] == "pest_detected" and disease["state"] != "disease_detected" else "disease"
    # Grad-CAM needs PyTorch gradients, so the ONNX backend (Raspberry Pi) returns no heatmap
    if model_registry.wrapper(target) is not None and not getattr(model_registry.wrapper(target), "onnx", False):
        try:
            from src.gradcam_viz import gradcam_for_wrapper

            cam = gradcam_for_wrapper(model_registry.wrapper(target), image_rgb)
            gradcam = {"target": target, "heatmap_base64": cam["heatmap_base64"], "focus_area_pct": cam["focus_area_pct"]}
        except Exception as exc:  # noqa: BLE001
            gradcam = {"target": target, "error": str(exc)}

    # Plant name only when the model is sure of the crop (summed over its classes); unsure -> None, never a guess
    crop_name, crop_conf = crop_from_probs(d_cal) if d_cal is not None else (None, None)
    crop_conf = round(crop_conf * 100, 2) if crop_conf is not None else None
    dosage = res.get("dosage_recommendation") or {}
    result = {
        "summary": {"state": summary_state, "message": summary_message},
        "crop": {"selected": crop, "reported": crop_name, "confidence": crop_conf},
        "disease": disease,
        "pest": pest,
        "severity": severity_out,
        "health_index": _health_index(res.get("overall")),
        "spectral_proxies": {
            "exg_chlorophyll_proxy": {k: res["ndre"].get(k) for k in ("ok", "score", "status", "value")},
            "cri_carotenoid_proxy": {k: res["cri"].get(k) for k in ("ok", "score", "status", "value")},
            "limitation": RGB_SPECTRAL_LIMITATION,
        },
        "image_quality": quality["metrics"],
        "gradcam": gradcam,
        "advice": {"state": "not_requested"},
        "dosage": dosage if dosage.get("ok") and summary_state != "uncertain" else None,
        "timing_ms": {"pipeline": round(pipeline_ms, 1), "total": round((time.perf_counter() - started) * 1000, 1)},
        "inferred_at": datetime.now().astimezone().isoformat(timespec="seconds"),
    }
    if summary_state == "uncertain":
        result["advice"] = {"state": "not_applicable", "items": ["Retake the photo in daylight with one leaf filling the frame.",
                                                                 "If symptoms persist, consult an agricultural extension officer."]}
    elif include_advice and summary_state in ADVISABLE_STATES:
        result["advice"] = farm_advisor.advise_scan(result, language, sensors)
        result["advice_by_language"] = {result["advice"]["language"]: result["advice"]}
    return result
