from fastapi.testclient import TestClient

import server
from tests.conftest import LAN_PHONE
from tests.test_api_v1 import _admin_headers, _analyze, _install_both, _register


def test_outbreaks_count_only_confirmed_detections_by_place():
    phone = TestClient(server.app, client=LAN_PHONE)
    _install_both()  # every scan: confirmed Tomato Early Blight, no pest
    salem, _ = _register(phone, username="farmer_salem", location="Salem")
    erode, _ = _register(phone, username="farmer_erode", location="Erode")
    _analyze(phone, salem)
    _analyze(phone, salem)
    _analyze(phone, erode)
    _install_both(disease_idx=None)  # no clear winner: uncertain, must not count
    _analyze(phone, erode)

    admin = _admin_headers(phone)
    body = phone.get("/api/v1/admin/outbreaks", headers=admin).json()
    assert body["confirmed_scans"] == 3
    [blight] = body["by_condition"]
    assert blight["label"] == "Tomato Early Blight" and blight["count"] == 3 and blight["places"] == ["Erode", "Salem"]
    assert {(p["location"], p["count"]) for p in body["by_location"]} == {("Erode", 1), ("Salem", 2)}
    farmer, _ = _register(phone, username="nosy")
    assert phone.get("/api/v1/admin/outbreaks", headers=farmer).status_code == 403


def test_nearby_alerts_show_other_farmers_in_my_village_only():
    phone = TestClient(server.app, client=LAN_PHONE)
    _install_both()
    me, _ = _register(phone, username="me_salem", location="Salem")
    neighbour, _ = _register(phone, username="neighbour", location="salem ")
    far, _ = _register(phone, username="far", location="Erode")
    _analyze(phone, me)          # my own scan is not an alert to me
    _analyze(phone, neighbour)
    _analyze(phone, neighbour)
    _analyze(phone, far)
    body = phone.get("/api/v1/outbreaks/nearby", headers=me).json()
    [alert] = body["alerts"]
    assert body["ok"] and alert["display_name"] == "Tomato Early Blight" and alert["count"] == 2 and alert["kind"] == "disease"
    assert "neighbour" not in str(body)  # counts only, never who
    nowhere, _ = _register(phone, username="nowhere")
    assert phone.get("/api/v1/outbreaks/nearby", headers=nowhere).json()["code"] == "no_location"
    assert phone.get("/api/v1/outbreaks/nearby").status_code == 401
