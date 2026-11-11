from __future__ import annotations

from src.config import (
    HEALTH_STATUS_THRESHOLDS,
    HEALTH_WEIGHTS,
    HIGH_CONFIDENCE_THRESHOLD,
    LOW_CONFIDENCE_THRESHOLD,
)


def _status_from_score(score: float) -> str:
    if score >= HEALTH_STATUS_THRESHOLDS["healthy"]:
        return "HEALTHY"
    if score >= HEALTH_STATUS_THRESHOLDS["mild"]:
        return "MILD STRESS"
    if score >= HEALTH_STATUS_THRESHOLDS["moderate"]:
        return "MODERATE STRESS"
    return "SEVERE STRESS"


def _assessment_confidence(confidences: list[float], modules_ok: int, modules_total: int) -> str:
    if modules_ok == 0:
        return "None"
    coverage = modules_ok / modules_total
    if not confidences:
        mean_conf = 0.5
    else:
        mean_conf = sum(confidences) / len(confidences)
    if coverage < 0.75:
        return "Low"
    if mean_conf >= HIGH_CONFIDENCE_THRESHOLD and coverage == 1.0:
        return "High"
    if mean_conf >= LOW_CONFIDENCE_THRESHOLD:
        return "Medium"
    return "Low"


def combine_health(pest: dict, disease: dict, ndre: dict, cri: dict) -> dict:
    weights = dict(HEALTH_WEIGHTS)
    scores = {}
    used_weights = {}
    confidences = []
    failed_modules = []

    mapping = {
        "pest": pest,
        "disease": disease,
        "ndre": ndre,
        "cri": cri,
    }

    for name, result in mapping.items():
        if result and result.get("ok") and result.get("score") is not None:
            scores[name] = float(result["score"])
            used_weights[name] = float(weights[name])
            raw = result.get("confidence_raw")
            if raw is not None:
                confidences.append(float(raw))
        else:
            failed_modules.append(name)

    if not scores:
        return {
            "ok": False,
            "overall_score": None,
            "overall_status": "UNAVAILABLE",
            "assessment_confidence": "None",
            "weights_used": {},
            "module_scores": {},
            "failed_modules": failed_modules,
            "error": "No module scores available",
        }

    total_weight = sum(used_weights.values())
    overall = sum(scores[name] * used_weights[name] for name in scores) / total_weight
    overall = round(float(overall), 1)

    return {
        "ok": True,
        "overall_score": overall,
        "overall_status": _status_from_score(overall),
        "assessment_confidence": _assessment_confidence(confidences, len(scores), 4),
        "weights_used": {k: round(v / total_weight, 4) for k, v in used_weights.items()},
        "configured_weights": weights,
        "module_scores": {k: round(v, 1) for k, v in scores.items()},
        "failed_modules": failed_modules,
        "error": None,
    }
