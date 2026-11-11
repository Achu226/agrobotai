from src.pest_detector import score_pest


def test_leaf_closeup_does_not_confirm_moderate_pest_guess():
    # Real case: Early Blight leaf, pest CNN guessed aphids at 72% with lesions counted as "evidence"
    res = score_pest("aphids", 0.7206, "bollworm", 0.2071, 0.5135, evidence_score=1.0, leaf_confidence=0.99)
    assert res["pest_detected"] is False
    # On a plain leaf close-up the pest model is out of its domain: its guess is ignored, not flagged
    assert res["display_name"] == "No Visible Pest"
    assert "leaf close-up" in res["rejection_reason"]


def test_very_confident_pest_is_confirmed_even_on_leaf():
    res = score_pest("aphids", 0.985, "mites", 0.01, 0.975, evidence_score=0.2, leaf_confidence=0.985)
    assert res["pest_detected"] is True


def test_insect_photo_confirmed_when_disease_model_unsure():
    res = score_pest("armyworm", 0.80, "bollworm", 0.15, 0.65, evidence_score=0.1, leaf_confidence=0.70)
    assert res["pest_detected"] is True


def test_without_cross_check_falls_back_to_evidence_gate():
    weak = score_pest("beetle", 0.80, "sawfly", 0.10, 0.70, evidence_score=0.1)
    strong = score_pest("beetle", 0.80, "sawfly", 0.10, 0.70, evidence_score=0.6)
    assert weak["pest_detected"] is False
    assert strong["pest_detected"] is True


def test_low_confidence_on_leaf_is_clean():
    res = score_pest("sawfly", 0.35, "beetle", 0.30, 0.05, evidence_score=1.0, leaf_confidence=0.99)
    assert res["pest_detected"] is False
    assert res["display_name"] == "No Visible Pest"


def test_moderate_guess_off_leaf_is_possible_pest():
    res = score_pest("beetle", 0.80, "sawfly", 0.10, 0.70, evidence_score=0.1, leaf_confidence=0.60)
    assert res["pest_detected"] is True  # passes softmax gates and is not a leaf scene
    res = score_pest("beetle", 0.60, "sawfly", 0.30, 0.30, evidence_score=0.1, leaf_confidence=0.60)
    assert res["display_name"] == "Possible Pest — Verification Required"
