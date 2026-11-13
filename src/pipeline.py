from __future__ import annotations

from datetime import datetime
from typing import Optional

from src.ai_advisor import generate_advice
from src.config import RGB_SPECTRAL_LIMITATION
from src.crop_classifier import classify_crop_type
from src.disease_detector import detect_disease
from src.health_engine import combine_health
from src.image_utils import validate_plant_image
from src.ndre_cri_analyzer import analyze_ndre_cri
from src.pest_detector import detect_pest

# NEW FEATURES
from src.disease_severity import calculate_disease_severity
from src.nutrient_deficiency import analyze_nutrient_deficiency
from src.dosage_calculator import DosageCalculator


def analyze_image(
    image_rgb,
    crop: str = "Auto-Detect",
    pest_model=None,
    disease_model=None,
    nutrient_model=None,
    include_advice: bool = True,
    include_severity: bool = True,
    include_nutrients: bool = True,
    include_dosage: bool = True,
    api_key: str | None = None,
    cri_variant: str = "CRI1",
    field_size_acres: float = 1.0,
    location: Optional[str] = None,
) -> dict:
    is_valid, validation_msg, leaf_frac = validate_plant_image(image_rgb)
    if not is_valid:
        err_res = {
            "ok": False,
            "status": "Invalid Image",
            "error": validation_msg,
            "display_name": "No Plant Detected",
            "score": None,
            "confidence": None,
            "value": None,
        }
        return {
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "crop": crop,
            "is_valid_plant": False,
            "validation_error": validation_msg,
            "crop_classification": {"ok": False, "predicted_crop": crop, "confidence": 0.0},
            "pest": err_res,
            "disease": err_res,
            "ndre": err_res,
            "cri": err_res,
            "spectral_limitation": RGB_SPECTRAL_LIMITATION,
            "leaf_fraction": leaf_frac,
            "overall": {
                "ok": False,
                "overall_score": None,
                "overall_status": "INVALID IMAGE",
                "assessment_confidence": "None",
                "failed_modules": [{"module": "validation", "error": validation_msg}],
            },
            "advice": {
                "ok": False,
                "source": "validation_failed",
                "error": validation_msg,
                "immediate_actions": ["Please upload a clear photo of a plant leaf."],
                "next_24_48_hours": ["Ensure proper lighting and that the leaf fills most of the frame."],
                "next_7_days": ["Re-scan the crop with a valid plant leaf image."],
                "prevention": ["Avoid uploading photos of non-plant objects, faces, or empty backgrounds."],
                "pest_management": [],
                "disease_management": [],
                "irrigation": [],
                "nutrients": [],
                "field_monitoring": [],
                "yield_notes": [],
                "warnings": [validation_msg],
            },
            "failed_modules": [{"module": "validation", "error": validation_msg}],
        }
    disease = detect_disease(image_rgb, model=disease_model)
    # The disease model's certainty that this is an ordinary leaf guards against pest false alarms
    pest = detect_pest(image_rgb, model=pest_model, leaf_confidence=disease.get("single_view_confidence") if disease.get("ok") else None)
    crop_info = classify_crop_type(image_rgb, disease_result=disease)

    effective_crop = crop
    if not crop or crop.lower() in ("auto", "auto-detect", "detect", "auto-detect plant species"):
        effective_crop = crop_info.get("predicted_crop") or "Plant"  # never guess a crop the model is unsure of

    spectral = analyze_ndre_cri(image_rgb, cri_variant=cri_variant)
    ndre = spectral.get("ndre") or {"ok": False, "error": "NDRE unavailable", "score": None, "status": "Failed"}
    cri = spectral.get("cri") or {"ok": False, "error": "CRI unavailable", "score": None, "status": "Failed"}

    # NEW: Disease Severity Calculation
    severity = {"ok": False}
    if include_severity:
        severity = calculate_disease_severity(image_rgb)

    # NEW: Nutrient Deficiency Detection
    nutrients = {"ok": False}
    if include_nutrients:
        nutrients = analyze_nutrient_deficiency(image_rgb, model=nutrient_model)

    overall = combine_health(pest, disease, ndre, cri)

    # NEW: Dosage Calculator
    dosage_recommendation = {"ok": False}
    if include_dosage:
        # Calculate dosage for confirmed pest or disease
        detected_target = None
        # Prioritize confirmed active disease or confirmed active pest
        if disease.get("ok") and disease.get("display_name") and not disease.get("is_healthy_class", False):
            detected_target = disease.get("display_name")
        elif pest.get("ok") and pest.get("pest_detected") and pest.get("display_name") and not pest.get("is_healthy_class", False):
            detected_target = pest.get("display_name")
        elif disease.get("ok") and not disease.get("is_healthy_class", False) and disease.get("display_name"):
            detected_target = disease.get("display_name")

        if detected_target:
            dosage_recommendation = DosageCalculator.calculate_dosage(
                target_name=detected_target,
                field_size_acres=field_size_acres,
                preferred_mode="both"
            )

    advice = None
    if include_advice:
        # Enhanced advice with new features
        advice = generate_advice(
            effective_crop, pest, disease, ndre, cri, overall,
            api_key=api_key,
            severity_data=severity if include_severity else None,
            nutrient_data=nutrients if include_nutrients else None,
            location=location
        )

    failed = []
    for name, result in (("pest", pest), ("disease", disease), ("ndre", ndre), ("cri", cri)):
        if not result.get("ok"):
            failed.append({"module": name, "error": result.get("error") or "failed"})

    # Ensure backward-compatible aliases for pest & disease frontend keys
    if isinstance(pest, dict):
        pest["identified"] = pest.get("display_name") or pest.get("value") or ("No Pest" if pest.get("is_healthy_class") else "Pest Detected")
    if isinstance(disease, dict):
        disease["identified"] = disease.get("display_name") or disease.get("value") or ("Healthy" if disease.get("is_healthy_class") else "Disease Detected")

    return {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "crop": effective_crop,
        "selected_crop": crop,
        "crop_classification": crop_info,
        "is_valid_plant": True,
        "pest": pest,
        "disease": disease,
        "ndre": ndre,
        "cri": cri,
        "severity": severity,  # NEW
        "nutrients": nutrients,  # NEW
        "dosage_recommendation": dosage_recommendation,  # NEW
        "spectral_limitation": spectral.get("limitation", RGB_SPECTRAL_LIMITATION),
        "leaf_fraction": spectral.get("leaf_fraction"),
        "overall": overall,
        "advice": advice,
        "failed_modules": failed,
    }
