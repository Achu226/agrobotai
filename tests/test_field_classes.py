import pytest
from fastapi.testclient import TestClient

import server
from src.config import DISEASE_CLASSES, PEST_CLASSES
from src.pest_detector import score_pest
from tests.conftest import LAN_PHONE, FixedLogitNet, install_model, logits_for
from tests.test_api_v1 import _analyze, _register

OTHER_PLANT = list(DISEASE_CLASSES.values()).index("Other_plant")
NO_PEST = list(PEST_CLASSES.values()).index("no_pest")
EARLY_BLIGHT = list(DISEASE_CLASSES.values()).index("Tomato_Early_blight")


@pytest.fixture()
def phone():
    return TestClient(server.app, client=LAN_PHONE)


def test_other_plant_is_never_diagnosed(phone):
    install_model("disease", FixedLogitNet(logits_for(len(DISEASE_CLASSES), OTHER_PLANT)))
    install_model("pest", FixedLogitNet(logits_for(len(PEST_CLASSES), NO_PEST)))
    headers, _ = _register(phone)
    result = _analyze(phone, headers, crop="Tomato").json()["scan"]["result"]
    assert result["disease"]["state"] == "unsupported_crop"
    assert "no diagnosis" in result["disease"]["message"]
    assert result["summary"]["state"] == "unsupported_crop"
    assert result["crop"]["reported"] is None


def test_no_pest_class_means_no_pest(phone):
    install_model("disease", FixedLogitNet(logits_for(len(DISEASE_CLASSES), EARLY_BLIGHT)))
    install_model("pest", FixedLogitNet(logits_for(len(PEST_CLASSES), NO_PEST)))
    headers, _ = _register(phone)
    pest = _analyze(phone, headers).json()["scan"]["result"]["pest"]
    assert pest["state"] == "no_pest_detected"


def test_no_pest_is_never_confirmed_even_when_certain():
    for leaf_conf in (None, 0.2, 0.99):
        res = score_pest("no_pest", 0.999, "aphids", 0.001, 0.998, evidence_score=1.0, leaf_confidence=leaf_conf)
        assert res["pest_detected"] is False and res["display_name"] == "No Visible Pest"
