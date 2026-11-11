from fastapi.testclient import TestClient

import server
from src import device_status
from tests.conftest import LAN_PHONE
from tests.test_api_v1 import _register


def test_throttled_flags_are_decoded():
    flags = device_status.parse_throttled("throttled=0x50005")
    assert flags["raw"] == "0x50005"
    assert flags["under_voltage_now"] and flags["throttled_now"] and flags["under_voltage_since_boot"]
    assert not flags["temp_limit_now"]
    assert not any(v for k, v in device_status.parse_throttled("throttled=0x0").items() if k != "raw")


def test_device_status_needs_sign_in_and_reports_real_values():
    phone = TestClient(server.app, client=LAN_PHONE)
    assert phone.get("/api/v1/device/status").status_code == 401
    headers, _ = _register(phone)
    body = phone.get("/api/v1/device/status", headers=headers).json()
    assert body["disk_total_gb"] > 0 and 0 <= body["disk_free_gb"] <= body["disk_total_gb"]
    # Readings this machine cannot provide are None, never made up
    for key in ("cpu_temp_c", "power", "memory_used_pct", "uptime_s"):
        assert key in body


def test_only_an_admin_can_turn_off_and_only_a_raspberry_pi(monkeypatch):
    from tests.test_api_v1 import _admin_headers

    phone = TestClient(server.app, client=LAN_PHONE)
    farmer, _ = _register(phone)
    assert phone.post("/api/v1/device/shutdown", headers=farmer).status_code == 403
    admin = _admin_headers(phone)
    calls = []
    monkeypatch.setattr(device_status, "shutdown_soon", lambda *a: calls.append(a))
    monkeypatch.setattr(device_status, "is_raspberry_pi", lambda: False)
    assert phone.post("/api/v1/device/shutdown", headers=admin).status_code == 409  # never the laptop
    monkeypatch.setattr(device_status, "is_raspberry_pi", lambda: True)
    res = phone.post("/api/v1/device/shutdown", headers=admin)
    assert res.status_code == 200 and res.json()["ok"] and calls == [()]


class _Stop(Exception):
    pass


def test_idle_watchdog_turns_off_only_after_the_idle_time(monkeypatch):
    offs = []
    monkeypatch.setattr(device_status, "_last_activity", 1000.0)
    sleeps = iter(range(2))

    def sleep(_):
        if next(sleeps, None) is None:
            raise _Stop

    # 1 h idle with a 2 h limit: keeps running (stopped by the test)
    try:
        device_status.idle_watchdog(2, clock=lambda: 1000.0 + 3600, sleep=sleep, off=offs.append)
    except _Stop:
        pass
    assert offs == []
    # 2 h idle: turns off once
    device_status.idle_watchdog(2, clock=lambda: 1000.0 + 7200, sleep=lambda _: None, off=offs.append)
    assert offs == [0]


def test_phone_requests_count_as_activity(monkeypatch):
    monkeypatch.setattr(device_status, "_last_activity", 0.0)
    TestClient(server.app, client=LAN_PHONE).get("/health")
    assert device_status._last_activity > 0


def test_pi_report_needs_the_status_key(monkeypatch):
    from src import config

    phone = TestClient(server.app, client=LAN_PHONE)
    monkeypatch.setattr(config, "STATUS_TOKEN", "")
    assert phone.get("/api/v1/device/report", headers={"X-Status-Token": ""}).status_code == 401  # off when unset
    monkeypatch.setattr(config, "STATUS_TOKEN", "k" * 32)
    assert phone.get("/api/v1/device/report", headers={"X-Status-Token": "wrong"}).status_code == 401
    body = phone.get("/api/v1/device/report", headers={"X-Status-Token": "k" * 32}).json()
    assert {"device", "stats", "sessions", "online_users"} <= body.keys()


def test_laptop_admin_page_shows_pi_report_or_a_clear_error(monkeypatch):
    import httpx

    from src import config
    from tests.test_api_v1 import _admin_headers

    phone = TestClient(server.app, client=LAN_PHONE)
    admin = _admin_headers(phone)
    monkeypatch.setattr(config, "PI_URL", "")
    assert phone.get("/api/v1/admin/pi", headers=admin).json() == {"configured": False}
    monkeypatch.setattr(config, "PI_URL", "http://agrobotai-pi.local:8000")
    monkeypatch.setattr(config, "PI_STATUS_TOKEN", "k" * 32)
    sent = {}

    def fake_get(url, headers, timeout):
        sent.update(url=url, key=headers["X-Status-Token"])
        return httpx.Response(200, json={"device": {"cpu_temp_c": 46.0}, "sessions": [], "online_users": 0, "stats": {}})

    monkeypatch.setattr(httpx, "get", fake_get)
    body = phone.get("/api/v1/admin/pi", headers=admin).json()
    assert body["ok"] and body["device"]["cpu_temp_c"] == 46.0
    assert sent == {"url": "http://agrobotai-pi.local:8000/api/v1/device/report", "key": "k" * 32}

    def offline(url, headers, timeout):
        raise httpx.ConnectTimeout("off")

    monkeypatch.setattr(httpx, "get", offline)
    body = phone.get("/api/v1/admin/pi", headers=admin).json()
    assert body["ok"] is False and "not reachable" in body["error"]
    farmer, _ = _register(phone)
    assert phone.get("/api/v1/admin/pi", headers=farmer).status_code == 403
