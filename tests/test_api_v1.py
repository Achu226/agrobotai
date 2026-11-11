import json

import numpy as np
import pytest
from fastapi.testclient import TestClient

import server
from src import config, model_registry, store
from src.config import DISEASE_CLASSES, PEST_CLASSES, ROOT_DIR
from tests.conftest import (
    LAN_PHONE,
    LOOPBACK,
    ExplodingNet,
    FixedLogitNet,
    install_model,
    jpeg_bytes,
    leaf_image,
    logits_for,
)

EARLY_BLIGHT = list(DISEASE_CLASSES.values()).index("Tomato_Early_blight")
TOMATO_HEALTHY = list(DISEASE_CLASSES.values()).index("Tomato_healthy")


@pytest.fixture()
def phone():
    return TestClient(server.app, client=LAN_PHONE)


def _register(client, username="farmer1", password="secret-pass-1", **extra):
    res = client.post("/api/v1/auth/register", json={"username": username, "password": password, **extra})
    assert res.status_code == 201, res.text
    return {"Authorization": f"Bearer {res.json()['token']}"}, res.json()["user"]


def _admin_headers(client, username="admin1", password="admin-pass-1"):
    from src import auth

    store.create_user(username, auth.hash_password(password), "admin", "Test Admin")
    res = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    return {"Authorization": f"Bearer {res.json()['token']}"}


def _analyze(client, headers, img=None, **form):
    data = {"include_advice": "false", **form}
    return client.post("/api/v1/analyze", headers=headers,
                       files={"file": ("leaf.jpg", jpeg_bytes(img if img is not None else leaf_image()), "image/jpeg")},
                       data=data)


def _install_both(disease_idx=EARLY_BLIGHT, pest_logits=None):
    install_model("disease", FixedLogitNet(logits_for(len(DISEASE_CLASSES), disease_idx)))
    install_model("pest", FixedLogitNet(pest_logits or logits_for(len(PEST_CLASSES), None)))


# ---------------------------------------------------------------- health & status

def test_health_reports_real_model_state_without_paths(phone):
    res = phone.get("/health")
    assert res.status_code == 200
    body = res.json()
    assert body["models"]["disease"]["ready"] is False
    assert "missing" in body["models"]["disease"]["error"]
    assert str(ROOT_DIR) not in res.text

    install_model("disease", FixedLogitNet(logits_for(len(DISEASE_CLASSES), 0)))
    body = phone.get("/health").json()
    assert body["models"]["disease"] == {"ready": True, "state": "ready", "version": "test-disease-v1",
                                         "num_classes": len(DISEASE_CLASSES), "error": None}


def test_models_status_requires_auth(phone):
    assert phone.get("/models/status").status_code == 401
    headers, _ = _register(phone)
    body = phone.get("/models/status", headers=headers).json()
    assert body["models"]["pest"]["state"] == "unavailable"
    from src import config

    # The deployed model's crops (models/disease_classes.json), the original three first
    assert body["supported_disease_crops"] == list(config.SUPPORTED_DISEASE_CROPS)
    assert body["supported_disease_crops"][:3] == ["Tomato", "Potato", "Bell Pepper"]


def test_registry_reports_missing_file_without_absolute_path(tmp_path, monkeypatch):
    monkeypatch.setattr(model_registry, "MODELS_DIR", tmp_path)
    info = model_registry._load_one("disease")
    assert info["ready"] is False and info["wrapper"] is None
    assert "models/disease_model.pt is missing" in info["error"]
    assert str(tmp_path) not in info["error"]


def test_registry_refuses_corrupt_weights(tmp_path, monkeypatch):
    (tmp_path / "pest_model.pt").write_bytes(b"not a checkpoint")
    monkeypatch.setattr(model_registry, "MODELS_DIR", tmp_path)
    info = model_registry._load_one("pest")
    assert info["ready"] is False
    assert info["error"].startswith("Failed to load pest_model.pt")


# ---------------------------------------------------------------- LAN guard

def test_lan_clients_only_reach_mobile_api(phone):
    for path in ("/api/history", "/api/health", "/docs", "/openapi.json", "/"):
        assert phone.get(path).status_code == 403, path
    assert phone.get("/health").status_code == 200
    assert phone.get("/api/v1/auth/me").status_code == 401
    local = TestClient(server.app, client=LOOPBACK)
    assert local.get("/api/history").status_code == 200
    assert local.get("/docs").status_code == 200


# ---------------------------------------------------------------- auth & access control

def test_register_login_and_wrong_password(phone):
    headers, user = _register(phone, full_name="Ravi")
    assert user["role"] == "farmer"
    assert phone.get("/api/v1/auth/me", headers=headers).json()["user"]["username"] == "farmer1"
    assert phone.post("/api/v1/auth/login", json={"username": "farmer1", "password": "nope-nope"}).status_code == 401
    assert phone.post("/api/v1/auth/login", json={"username": "ghost", "password": "whatever1"}).status_code == 401
    assert phone.post("/api/v1/auth/register", json={"username": "farmer1", "password": "another-pass"}).status_code == 409
    assert phone.post("/api/v1/auth/register", json={"username": "x", "password": "short"}).status_code == 422


def test_self_registration_never_creates_admin(phone):
    res = phone.post("/api/v1/auth/register", json={"username": "sneaky", "password": "sneaky-pass", "role": "admin"})
    assert res.json()["user"]["role"] == "farmer"


def test_signup_can_be_disabled(phone, monkeypatch):
    monkeypatch.setattr(config, "ALLOW_FARMER_SIGNUP", False)
    assert phone.post("/api/v1/auth/register", json={"username": "abc", "password": "abcdefgh"}).status_code == 403


def test_logout_revokes_token(phone):
    headers, _ = _register(phone)
    assert phone.post("/api/v1/auth/logout", headers=headers).status_code == 200
    assert phone.get("/api/v1/auth/me", headers=headers).status_code == 401


def test_farmer_cannot_review_or_see_others(phone):
    _install_both()
    a, _ = _register(phone, "alice", "alice-pass-1")
    b, _ = _register(phone, "bobby", "bobby-pass-1")
    scan_id = _analyze(phone, a).json()["scan"]["id"]
    assert phone.get(f"/api/v1/scans/{scan_id}", headers=b).status_code == 404
    assert phone.get("/api/v1/scans", headers=b).json()["scans"] == []
    assert phone.post(f"/api/v1/scans/{scan_id}/review", headers=a, json={"decision": "approved"}).status_code == 403
    assert phone.get("/api/v1/admin/users", headers=a).status_code == 403


def test_admin_review_records_identity_and_time(phone):
    _install_both()
    farmer, _ = _register(phone)
    admin = _admin_headers(phone)
    scan_id = _analyze(phone, farmer).json()["scan"]["id"]
    assert phone.get("/api/v1/scans?review_status=pending", headers=admin).json()["scans"][0]["id"] == scan_id
    res = phone.post(f"/api/v1/scans/{scan_id}/review", headers=admin,
                     json={"decision": "rejected", "comment": "Leaf is out of focus"})
    scan = res.json()["scan"]
    assert scan["review_status"] == "rejected"
    assert scan["reviewer_username"] == "admin1"
    assert scan["reviewed_at"] and scan["review_comment"] == "Leaf is out of focus"
    stats = phone.get("/api/v1/admin/stats", headers=admin).json()
    assert stats["successful_scans"] == 1 and stats["rejected"] == 1 and stats["farmers"] == 1


# ---------------------------------------------------------------- uploads

@pytest.mark.parametrize("payload, status, code", [
    (b"", 400, None),
    (b"definitely not an image", 400, "invalid_image"),
])
def test_bad_uploads_are_rejected(phone, payload, status, code):
    _install_both()
    headers, _ = _register(phone)
    res = phone.post("/api/v1/analyze", headers=headers, files={"file": ("x.jpg", payload, "image/jpeg")})
    assert res.status_code == status
    if code:
        assert res.json()["error"]["code"] == code
    assert phone.get("/api/v1/scans", headers=headers).json()["scans"] == []


def test_oversized_upload_rejected(phone, monkeypatch):
    _install_both()
    monkeypatch.setattr(config, "MAX_UPLOAD_MB", 0.001)
    headers, _ = _register(phone)
    assert _analyze(phone, headers).status_code == 413


def test_unsupported_format_rejected(phone):
    import io

    from PIL import Image

    _install_both()
    headers, _ = _register(phone)
    buf = io.BytesIO()
    Image.fromarray(leaf_image()).save(buf, format="GIF")
    res = phone.post("/api/v1/analyze", headers=headers, files={"file": ("x.gif", buf.getvalue(), "image/gif")})
    assert res.status_code == 415


@pytest.mark.parametrize("img, code", [
    (np.full((256, 256, 3), (40, 140, 50), dtype=np.uint8), "blurry"),
    ((leaf_image() * 0.08).astype(np.uint8), "too_dark"),
])
def test_poor_quality_photos_are_rejected_before_inference(phone, img, code):
    _install_both()
    headers, _ = _register(phone)
    res = _analyze(phone, headers, img)
    assert res.status_code == 422
    assert code in [i["code"] for i in res.json()["error"]["quality"]["issues"]]


def test_non_leaf_photo_rejected(phone):
    _install_both()
    headers, _ = _register(phone)
    rng = np.random.default_rng(1)
    blue = np.clip(np.array((40, 60, 170)) + rng.normal(0, 25, (256, 256, 3)), 0, 255).astype(np.uint8)
    res = _analyze(phone, headers, blue)
    assert res.status_code == 422
    assert res.json()["error"]["code"] == "no_leaf_detected"


# ---------------------------------------------------------------- inference mapping

def test_disease_detected_maps_real_model_output(phone):
    _install_both(EARLY_BLIGHT)
    headers, _ = _register(phone)
    res = _analyze(phone, headers, crop="Tomato", captured_at="2026-10-21T09:15:00+05:30")
    assert res.status_code == 200, res.text
    scan = res.json()["scan"]
    result = scan["result"]
    assert result["disease"]["state"] == "disease_detected"
    assert result["disease"]["label"] == "Tomato_Early_blight"
    assert result["disease"]["calibrated_confidence"] > 99
    assert result["disease"]["model"]["version"] == "test-disease-v1"
    assert result["pest"]["bounding_boxes"] is None and result["pest"]["model_type"] == "image_classifier"
    assert scan["inference_status"] == "succeeded"
    assert scan["captured_at"] == "2026-10-21T09:15:00+05:30"
    assert scan["model_versions"] == {"disease": "test-disease-v1", "pest": "test-pest-v1"}
    assert scan["review_status"] == "pending"
    assert phone.get(f"/api/v1/scans/{scan['id']}/image", headers=headers).headers["content-type"] == "image/jpeg"


def test_healthy_class_is_not_reported_as_proof_of_health(phone):
    _install_both(TOMATO_HEALTHY)
    headers, _ = _register(phone)
    result = _analyze(phone, headers).json()["scan"]["result"]
    assert result["disease"]["state"] == "no_disease_detected"
    assert result["summary"]["state"] == "no_supported_condition_detected"
    assert "not prove" in result["summary"]["message"] or "not proof" in result["disease"]["message"]


def test_flat_output_is_uncertain_with_required_message(phone):
    _install_both(None)  # all logits equal -> 1/15 confidence
    headers, _ = _register(phone)
    result = _analyze(phone, headers).json()["scan"]["result"]
    assert result["disease"]["state"] == "uncertain"
    assert result["summary"]["message"] == ("Unable to make a reliable diagnosis. Please capture a clearer image "
                                            "or consult an agricultural expert.")
    assert result["dosage"] is None
    assert result["advice"]["state"] == "not_applicable"


def test_unsupported_crop_is_not_diagnosed(phone):
    _install_both(EARLY_BLIGHT)
    headers, _ = _register(phone)
    result = _analyze(phone, headers, crop="Cotton").json()["scan"]["result"]  # rice is supported by the 48-class model
    assert result["disease"]["state"] == "unsupported_crop"
    assert result["summary"]["state"] == "unsupported_crop"


def test_pest_model_unavailable_is_explicit(phone):
    install_model("disease", FixedLogitNet(logits_for(len(DISEASE_CLASSES), EARLY_BLIGHT)))
    headers, _ = _register(phone)
    scan = _analyze(phone, headers).json()["scan"]
    assert scan["result"]["pest"]["state"] == "unavailable"
    assert scan["inference_status"] == "partial"
    res = phone.post("/api/v1/predict/pest", headers=headers,
                     files={"file": ("leaf.jpg", jpeg_bytes(leaf_image()), "image/jpeg")})
    assert res.status_code == 503 and res.json()["error"]["code"] == "pest_model_unavailable"


def test_predict_disease_endpoint(phone):
    _install_both(EARLY_BLIGHT)
    headers, _ = _register(phone)
    res = phone.post("/api/v1/predict/disease", headers=headers,
                     files={"file": ("leaf.jpg", jpeg_bytes(leaf_image()), "image/jpeg")})
    assert res.status_code == 200
    assert res.json()["display_name"] == "Tomato Early Blight"
    assert res.json()["inferred_at"]


def test_no_models_returns_503_and_saves_nothing_successful(phone):
    headers, _ = _register(phone)
    res = _analyze(phone, headers)
    assert res.status_code == 503 and res.json()["error"]["code"] == "models_unavailable"
    assert phone.get("/api/v1/scans", headers=headers).json()["scans"] == []


def test_inference_crash_is_reported_and_logged_as_failed(phone):
    install_model("disease", ExplodingNet(logits_for(len(DISEASE_CLASSES), 0)))
    headers, _ = _register(phone)
    admin = _admin_headers(phone)
    res = _analyze(phone, headers)
    assert res.status_code == 500 and res.json()["error"]["code"] == "inference_failed"
    assert "device-side assert" in res.json()["detail"]
    assert phone.get("/api/v1/scans", headers=headers).json()["scans"] == []
    failed = phone.get("/api/v1/scans?include_failed=true", headers=admin).json()["scans"]
    assert [s["inference_status"] for s in failed] == ["failed"]
    assert phone.get("/api/v1/admin/stats", headers=admin).json()["successful_scans"] == 0


def test_duplicate_submission_returns_existing_scan(phone):
    _install_both()
    headers, _ = _register(phone)
    first = _analyze(phone, headers, client_request_id="req-123").json()
    second = _analyze(phone, headers, client_request_id="req-123").json()
    assert first["duplicate"] is False and second["duplicate"] is True
    assert first["scan"]["id"] == second["scan"]["id"]
    assert len(phone.get("/api/v1/scans", headers=headers).json()["scans"]) == 1


def test_scans_persist_in_database_file(phone):
    _install_both()
    headers, _ = _register(phone)
    scan_id = _analyze(phone, headers).json()["scan"]["id"]
    # A fresh client (as after a server restart) still sees the stored scan and session
    again = TestClient(server.app, client=LAN_PHONE)
    assert again.get(f"/api/v1/scans/{scan_id}", headers=headers).json()["scan"]["result"]["disease"]["label"] == "Tomato_Early_blight"


# ---------------------------------------------------------------- reports

def test_pdf_report_contains_stored_result_and_honest_gaps(phone):
    _install_both(EARLY_BLIGHT)
    headers, _ = _register(phone, full_name="Ravi Kumar")
    scan = _analyze(phone, headers).json()["scan"]
    res = phone.get(f"/api/v1/scans/{scan['id']}/report.pdf", headers=headers)
    assert res.status_code == 200 and res.headers["content-type"] == "application/pdf"
    pdf = res.content
    assert b"Tomato Early Blight" in pdf
    assert b"Ravi Kumar" in pdf
    assert b"test-disease-v1" in pdf
    assert b"pending" in pdf
    assert b"Not available" in pdf  # e.g. reviewer, which does not exist yet


def test_report_not_generated_for_failed_attempt(phone):
    install_model("disease", ExplodingNet(logits_for(len(DISEASE_CLASSES), 0)))
    headers, _ = _register(phone)
    admin = _admin_headers(phone)
    _analyze(phone, headers)
    failed_id = phone.get("/api/v1/scans?include_failed=true", headers=admin).json()["scans"][0]["id"]
    assert phone.get(f"/api/v1/scans/{failed_id}/report.pdf", headers=admin).status_code == 409


# ---------------------------------------------------------------- weather & sensors

def test_weather_unreachable_is_unavailable_not_invented(phone, monkeypatch):
    import requests

    def offline(*a, **k):
        raise requests.exceptions.ConnectionError("no internet")

    monkeypatch.delenv("WEATHER_API_KEY", raising=False)
    monkeypatch.setattr(requests, "get", offline)
    headers, _ = _register(phone)
    body = phone.get("/api/v1/weather?location=Salem", headers=headers).json()
    assert body["ok"] is False and body["code"] == "weather_unavailable"
    assert "weather" not in body


def test_weather_without_key_uses_open_meteo(phone, monkeypatch):
    import requests

    class Res:
        def __init__(self, data):
            self.data = data

        def json(self):
            return self.data

        def raise_for_status(self):
            pass

    forecast = {"current": {"time": "2026-10-27T19:00", "temperature_2m": 26.4, "relative_humidity_2m": 60,
                            "precipitation": 0.0, "wind_speed_10m": 3.0, "weather_code": 61, "uv_index": 0, "is_day": 0},
                "hourly": {"time": ["2026-10-27T18:00", "2026-10-27T19:00", "2026-10-27T20:00"],
                           "temperature_2m": [27.0, 26.4, 25.9], "precipitation_probability": [10, 40, 80],
                           "precipitation": [0.0, 0.2, 1.5], "weather_code": [3, 61, 63], "is_day": [1, 0, 0]},
                "daily": {"time": ["2026-10-27"], "temperature_2m_max": [31.0], "temperature_2m_min": [22.0],
                          "temperature_2m_mean": [26.0], "relative_humidity_2m_max": [95],
                          "relative_humidity_2m_mean": [80], "precipitation_sum": [4.2],
                          "precipitation_probability_max": [70], "weather_code": [63]}}

    def fake_get(url, params=None, timeout=None):
        if "geocoding" in url:
            return Res({"results": [{"name": "Salem", "admin1": "Tamil Nadu", "country": "India",
                                     "latitude": 11.65, "longitude": 78.16}]})
        return Res(forecast)

    monkeypatch.delenv("WEATHER_API_KEY", raising=False)
    monkeypatch.setattr(requests, "get", fake_get)
    headers, _ = _register(phone)
    body = phone.get("/api/v1/weather?location=Salem", headers=headers).json()
    assert body["ok"] is True and body["provider"] == "Open-Meteo"
    assert body["weather"]["current"]["temp_c"] == 26.4
    assert body["weather"]["current"]["condition"] == "Light rain"
    assert body["weather"]["forecast"][0]["chance_of_rain"] == 70
    assert body["weather"]["current"]["weather_code"] == 61 and body["weather"]["current"]["is_day"] is False
    # hourly starts at the current hour (19:00), earlier hours are dropped
    assert [h["time"] for h in body["weather"]["hourly"]] == ["2026-10-27T19:00", "2026-10-27T20:00"]
    assert body["weather"]["hourly"][1]["chance_of_rain"] == 80
    assert "risk_analysis" in body


def test_sensors_show_status_not_fabricated_values(phone, monkeypatch):
    headers, _ = _register(phone)
    status = phone.get("/api/v1/sensors/status", headers=headers).json()
    assert status["devices"] == [] and "No sensor gateway" in status["message"]

    reading = {"device_id": "esp32-field-1", "readings": {"soil_moisture_pct": 41.5, "air_temp_c": 29.1}}
    assert phone.post("/api/v1/sensors/readings", json=reading).status_code == 503  # not configured
    monkeypatch.setattr(config, "SENSOR_INGEST_TOKEN", "sensor-secret")
    assert phone.post("/api/v1/sensors/readings", json=reading, headers={"X-Sensor-Token": "wrong"}).status_code == 401
    assert phone.post("/api/v1/sensors/readings", json=reading, headers={"X-Sensor-Token": "sensor-secret"}).status_code == 201

    device = phone.get("/api/v1/sensors/status", headers=headers).json()["devices"][0]
    assert device["connected"] is True and device["readings"]["soil_moisture_pct"] == 41.5
    monkeypatch.setattr(config, "SENSOR_STALE_SECONDS", -1)
    assert phone.get("/api/v1/sensors/status", headers=headers).json()["devices"][0]["connected"] is False


def test_insect_photo_reports_pest_without_inventing_a_leaf_disease(phone):
    # Pest model sure it is an aphid; disease model only moderately sure about a leaf class
    install_model("disease", FixedLogitNet(logits_for(len(DISEASE_CLASSES), EARLY_BLIGHT, strength=5.5)))  # ~95%: above 0.90, below 0.97
    install_model("pest", FixedLogitNet(logits_for(len(PEST_CLASSES), 0)))  # aphids
    headers, _ = _register(phone)
    result = _analyze(phone, headers).json()["scan"]["result"]
    assert result["pest"]["state"] == "pest_detected"
    assert result["disease"]["state"] == "uncertain"
    assert any("insect" in r for r in result["disease"]["uncertainty_reasons"])
    assert result["summary"]["state"] == "pest_detected"


def test_rejected_pest_guess_on_leaf_has_no_headline_confidence(phone):
    install_model("disease", FixedLogitNet(logits_for(len(DISEASE_CLASSES), TOMATO_HEALTHY)))
    install_model("pest", FixedLogitNet(logits_for(len(PEST_CLASSES), 0, strength=2.0)))  # weak aphid guess
    headers, _ = _register(phone)
    pest = _analyze(phone, headers).json()["scan"]["result"]["pest"]
    assert pest["state"] == "no_pest_detected"
    assert "calibrated_confidence" not in pest and "top_prediction" not in pest
    assert "leaf close-up" in pest["rejected_guess"]["reason"]


def test_dosage_only_for_confirmed_findings_with_a_verified_table(phone):
    _install_both(EARLY_BLIGHT)
    headers, _ = _register(phone)
    scan_id = _analyze(phone, headers).json()["scan"]["id"]
    res = phone.get(f"/api/v1/dosage?scan_id={scan_id}&acres=2&tank_liters=16", headers=headers)
    assert res.status_code == 200, res.text
    plan = res.json()
    assert plan["table"] == "Early Blight" and plan["field_size_acres"] == 2
    assert plan["chemical_treatment"]["dose_per_knapsack_tank"].startswith("40.0")  # 2.5 g/L x 16 L

    _install_both(TOMATO_HEALTHY)
    healthy = _analyze(phone, headers).json()["scan"]["id"]
    assert phone.get(f"/api/v1/dosage?scan_id={healthy}", headers=headers).status_code == 409

    mosaic = list(DISEASE_CLASSES.values()).index("Tomato__Tomato_mosaic_virus")
    _install_both(mosaic)
    no_table = _analyze(phone, headers, crop="Tomato").json()["scan"]["id"]
    res = phone.get(f"/api/v1/dosage?scan_id={no_table}", headers=headers)
    assert res.status_code == 404 and "no verified spray table" in res.json()["detail"]
