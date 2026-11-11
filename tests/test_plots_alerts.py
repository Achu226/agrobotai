from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

import server
from src import api_v1, config, store
from tests.conftest import LAN_PHONE
from tests.test_api_v1 import _analyze, _install_both, _register


@pytest.fixture()
def phone():
    return TestClient(server.app, client=LAN_PHONE)


# ---------------------------------------------------------------- recovery tracker

def test_plots_group_own_scans_in_time_order(phone):
    _install_both()
    me, _ = _register(phone, "farmer1")
    other, _ = _register(phone, "farmer2")
    first = _analyze(phone, me, plot="North field", captured_at="2026-10-20T08:00:00+05:30").json()["scan"]
    second = _analyze(phone, me, plot="North field", captured_at="2026-10-25T08:00:00+05:30").json()["scan"]
    _analyze(phone, me)  # no plot: not tracked
    _analyze(phone, other, plot="North field")  # someone else's plot of the same name
    assert first["plot"] == "North field"

    plots = phone.get("/api/v1/plots", headers=me).json()["plots"]
    assert [p["plot"] for p in plots] == ["North field"]
    assert [s["id"] for s in plots[0]["scans"]] == [first["id"], second["id"]]
    assert plots[0]["scans"][0]["severity_pct"] == first["severity_pct"]


def test_plots_require_login(phone):
    assert phone.get("/api/v1/plots").status_code == 401


# ---------------------------------------------------------------- alerts

def _device(readings, age_s=10):
    received = (datetime.now(timezone.utc) - timedelta(seconds=age_s)).astimezone().isoformat(timespec="seconds")
    return {"device_id": "pi-1", "received_at": received, "readings": readings}


@pytest.mark.parametrize("readings, codes", [
    ({"soil_moisture_pct": 18.0}, ["soil_dry"]),
    ({"soil_moisture_pct": 92.0}, ["waterlogged"]),
    ({"soil_moisture_pct": 45.0, "air_temp_c": 30.0, "humidity_pct": 60}, []),
    ({"air_temp_c": 41.5}, ["heat"]),
    ({"air_temp_c": 18.0, "humidity_pct": 95}, ["blight_weather"]),
    ({"air_temp_c": 30.0, "humidity_pct": 95}, []),  # humid but too warm for blight weather
    ({"soil_moisture_pct": None, "air_temp_c": None}, []),  # missing values never alert
])
def test_alert_thresholds(readings, codes):
    assert [a["code"] for a in api_v1.field_alerts([_device(readings)])] == codes


def test_stale_readings_only_say_offline(monkeypatch):
    monkeypatch.setattr(config, "SENSOR_STALE_SECONDS", 300)
    alerts = api_v1.field_alerts([_device({"soil_moisture_pct": 5.0}, age_s=1800)])
    assert alerts == [{"code": "sensor_offline", "device": "pi-1", "value": 30, "threshold": None}]


def test_device_silent_for_a_day_stops_alerting():
    assert api_v1.field_alerts([_device({"soil_moisture_pct": 5.0}, age_s=2 * 86400)]) == []


def test_alerts_endpoint_uses_real_readings_only(phone, monkeypatch):
    monkeypatch.setattr(config, "SENSOR_INGEST_TOKEN", "tok")
    headers, _ = _register(phone)
    assert phone.get("/api/v1/alerts", headers=headers).json() == {"alerts": []}
    phone.post("/api/v1/sensors/readings", headers={"X-Sensor-Token": "tok"},
               json={"device_id": "pi-1", "readings": {"soil_moisture_pct": 12.5}})
    alerts = phone.get("/api/v1/alerts", headers=headers).json()["alerts"]
    assert alerts == [{"code": "soil_dry", "device": "pi-1", "value": 12.5, "threshold": config.ALERT_SOIL_DRY_PCT}]
    assert store.latest_sensor_readings()[0]["readings"] == {"soil_moisture_pct": 12.5}
