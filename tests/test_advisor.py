from src.ai_advisor import generate_advice


def _ok_module(name="ok", score=80, confidence=90):
    return {
        "ok": True,
        "display_name": name,
        "raw_class": name,
        "status": "ok",
        "score": score,
        "confidence": confidence,
        "confidence_raw": confidence / 100.0,
        "is_healthy_class": False,
        "error": None,
    }


def test_advisor_falls_back_without_api_key(monkeypatch):
    monkeypatch.setattr("src.ai_advisor.OPENAI_API_KEY", "")
    monkeypatch.setattr("src.config.OPENAI_BASE_URL", "https://api.openai.com/v1")
    pest = _ok_module("Aphids", 40, 88)
    disease = _ok_module("Tomato Healthy", 95, 91)
    disease["is_healthy_class"] = True
    ndre = {"ok": True, "value": 0.7, "status": "Healthy", "score": 70, "error": None}
    cri = {"ok": True, "value": 0.4, "status": "Moderate", "score": 60, "error": None}
    overall = {
        "ok": True,
        "overall_score": 68.5,
        "overall_status": "MILD STRESS",
        "assessment_confidence": "High",
        "failed_modules": [],
    }
    advice = generate_advice("Tomato", pest, disease, ndre, cri, overall)
    assert advice["ok"] is True
    assert advice["emergency_actions"]
    assert advice["schedule"]
    assert advice["pest_disease_control"]
    assert advice["safety"]
    assert advice["source"].startswith("fallback")
