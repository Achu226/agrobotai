from src.health_engine import combine_health
from src.pest_detector import score_pest
from src.disease_detector import score_disease
from src.ndre_cri_analyzer import score_chlorophyll_proxy, score_carotenoid_proxy
import numpy as np


def test_health_engine_weighted_average():
    pest = {"ok": True, "score": 80.0, "confidence_raw": 0.9}
    disease = {"ok": True, "score": 60.0, "confidence_raw": 0.8}
    ndre = {"ok": True, "score": 70.0}
    cri = {"ok": True, "score": 50.0}
    result = combine_health(pest, disease, ndre, cri)
    assert result["ok"] is True
    expected = (80 * 0.30 + 60 * 0.35 + 70 * 0.20 + 50 * 0.15)
    assert abs(result["overall_score"] - round(expected, 1)) < 0.11
    assert result["overall_status"] in {"HEALTHY", "MILD STRESS", "MODERATE STRESS", "SEVERE STRESS"}


def test_health_engine_ignores_failed_module():
    pest = {"ok": False, "score": None, "error": "missing"}
    disease = {"ok": True, "score": 100.0, "confidence_raw": 0.95}
    ndre = {"ok": True, "score": 100.0}
    cri = {"ok": True, "score": 100.0}
    result = combine_health(pest, disease, ndre, cri)
    assert result["ok"] is True
    assert result["overall_score"] == 100.0
    assert "pest" in result["failed_modules"]


def test_pest_and_disease_scores_are_deterministic():
    a = score_pest("aphids", 0.92)
    b = score_pest("aphids", 0.92)
    assert a["score"] == b["score"]
    healthy = score_disease("Tomato_healthy", 0.97)
    assert healthy["score"] >= 95.0
    blight = score_disease("Tomato_Late_blight", 0.90)
    assert blight["score"] < 50


def test_ndre_cri_score_helpers():
    veg_vals = np.array([0.25, 0.28, 0.30])
    chloro_idx, score, status = score_chlorophyll_proxy(veg_vals)
    assert score > 90.0
    assert status == "Healthy Plant"

    cri_vals = np.array([0.1, 0.15])
    caro_idx, caro_score, caro_status = score_carotenoid_proxy(cri_vals, mean_raw_exg=0.20)
    assert caro_score == 95.0
    assert caro_status == "Low Carotenoid"
