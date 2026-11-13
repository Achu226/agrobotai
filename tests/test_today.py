from datetime import date

import pytest
from fastapi.testclient import TestClient

import server
from src import api_v1, weather_forecast
from tests.conftest import LAN_PHONE
from tests.test_api_v1 import _admin_headers, _analyze, _install_both, _register


@pytest.fixture()
def phone(monkeypatch):
    # No internet in tests: the weather service reports "unavailable", as it does on a farm without signal
    monkeypatch.setattr(weather_forecast.WeatherService, "get_weather_data",
                        lambda self, location: {"ok": False, "code": "weather_unavailable", "error": "offline"})
    return TestClient(server.app, client=LAN_PHONE)


def test_today_summarises_only_my_real_data(phone):
    _install_both()
    me, _ = _register(phone, username="me_salem", location="Salem")
    neighbour, _ = _register(phone, username="neighbour", location="Salem")
    today = date.today().isoformat()
    base = {"plot": "North", "kind": "spray", "cost": 250, "done_on": today}
    phone.post("/api/v1/diary", headers=me, json=base | {"remind_on": today})
    phone.post("/api/v1/diary", headers=me, json=base | {"kind": "sale", "cost": 9000})
    phone.post("/api/v1/diary", headers=me, json=base | {"done_on": "2020-01-01", "cost": 77})  # old: not this week
    phone.post("/api/v1/diary", headers=neighbour, json=base | {"cost": 5000})                  # someone else's money
    _analyze(phone, me)
    _analyze(phone, neighbour)
    body = phone.get("/api/v1/today", headers=me).json()
    assert body["week"] == {"scans": 1, "spent": 250, "earned": 9000}
    assert [r["plot"] for r in body["reminders"]] == ["North"]
    assert [a["count"] for a in body["nearby"]] == [1]            # the neighbour's scan, not mine
    assert body["spray"]["ok"] is False and body["spray"]["code"] == "weather_unavailable"  # never a guessed verdict
    assert phone.get("/api/v1/today").status_code == 401


def test_pi_health_warnings():
    assert api_v1.device_alerts({"hostname": "pi", "cpu_temp_c": 60.0, "power": {"under_voltage_now": False}}) == []
    hot = api_v1.device_alerts({"hostname": "pi", "cpu_temp_c": 81.5, "power": {"under_voltage_now": True}})
    assert [a["code"] for a in hot] == ["pi_hot", "pi_low_power"] and hot[0]["value"] == 81.5
    assert api_v1.device_alerts({"hostname": "laptop", "cpu_temp_c": None, "power": None}) == []  # a laptop reports neither


def test_admin_outbreak_export(phone):
    _install_both()
    farmer, _ = _register(phone, username="farmer_erode", location="Erode")
    _analyze(phone, farmer)
    res = phone.get("/api/v1/admin/outbreaks.csv", headers=_admin_headers(phone))
    lines = res.text.lstrip("﻿").splitlines()
    assert lines[0] == "Village / place,Condition,Type,Confirmed scans,Last seen"
    assert lines[1].startswith("Erode,Tomato Early Blight,disease,1,")
    assert phone.get("/api/v1/admin/outbreaks.csv", headers=farmer).status_code == 403


def test_ask_an_expert_round_trip(phone):
    _install_both()
    me, _ = _register(phone, username="asker_farmer")
    other, _ = _register(phone, username="other_farmer")
    scan_id = _analyze(phone, me).json()["scan"]["id"]
    assert phone.post(f"/api/v1/scans/{scan_id}/ask", headers=other, json={"question": "Is this blight?"}).status_code == 404
    assert phone.post(f"/api/v1/scans/{scan_id}/ask", headers=me, json={"question": "  "}).status_code == 422
    asked = phone.post(f"/api/v1/scans/{scan_id}/ask", headers=me, json={"question": "Is this blight? Leaves are yellow."})
    assert asked.status_code == 200 and asked.json()["scan"]["question"].startswith("Is this blight")
    admin = _admin_headers(phone)
    waiting = phone.get("/api/v1/scans?asked=true&review_status=pending", headers=admin).json()["scans"]
    assert [s["id"] for s in waiting] == [scan_id]
    assert phone.get("/api/v1/today", headers=me).json()["answers"] == []           # not answered yet
    phone.post(f"/api/v1/scans/{scan_id}/review", headers=admin, json={"decision": "approved", "comment": "Yes, early blight."})
    answers = phone.get("/api/v1/today", headers=me).json()["answers"]
    assert answers == [{"scan_id": scan_id, "question": "Is this blight? Leaves are yellow.", "answer": "Yes, early blight.",
                        "decision": "approved"}]
    assert phone.get("/api/v1/today", headers=other).json()["answers"] == []


def test_crop_calendar_saves_dated_reminders(phone):
    me, _ = _register(phone, username="calendar_farmer")
    crops = phone.get("/api/v1/calendar", headers=me).json()["crops"]
    assert "Rice (Paddy)" in crops and "Tomato" in crops
    preview = phone.get("/api/v1/calendar?crop=Rice (Paddy)&sown_on=2026-06-01", headers=me).json()
    assert preview["harvest_on"] == "2026-09-29"
    assert {"day": 21, "date": "2026-06-22", "kind": "fertilizer", "task": "First nitrogen top dressing (tillering)"} in preview["tasks"]
    assert phone.get("/api/v1/diary", headers=me).json()["entries"] == []               # a preview saves nothing
    saved = phone.post("/api/v1/calendar", headers=me,
                       json={"plot": "East field", "crop": "Rice (Paddy)", "sown_on": "2026-06-01", "language": "ta"})
    assert saved.status_code == 201
    entries = phone.get("/api/v1/diary", headers=me).json()["entries"]
    assert len(entries) == len(preview["tasks"])
    assert all(e["remind_on"] == e["done_on"] and e["plot"] == "East field" for e in entries)
    assert any("தூர் கட்டும்" in e["note"] for e in entries)                            # Tamil task text
    assert phone.post("/api/v1/calendar", headers=me, json={"plot": "x", "crop": "Wheat", "sown_on": "2026-06-01"}).status_code == 422
    assert phone.post("/api/v1/calendar", headers=me, json={"plot": "x", "crop": "Tomato", "sown_on": "2026-02-30"}).status_code == 422
