import pytest
from fastapi.testclient import TestClient

import server
from tests.conftest import LAN_PHONE
from tests.test_api_v1 import _admin_headers, _register


@pytest.fixture()
def phone():
    return TestClient(server.app, client=LAN_PHONE)


SPRAY = {"plot": "North field", "kind": "spray", "product": "Neem oil", "quantity": "3 ml/L", "cost": 250,
         "done_on": "2026-10-27", "remind_on": "2026-11-03"}


def test_diary_add_list_delete_is_private(phone):
    me, _ = _register(phone, "farmer1")
    other, _ = _register(phone, "farmer2")
    entry = phone.post("/api/v1/diary", headers=me, json=SPRAY).json()["entry"]
    assert entry["product"] == "Neem oil" and entry["remind_on"] == "2026-11-03" and entry["cost"] == 250
    phone.post("/api/v1/diary", headers=me, json=SPRAY | {"plot": "South field", "kind": "note", "note": "weeded", "remind_on": None})
    assert [e["plot"] for e in phone.get("/api/v1/diary", headers=me).json()["entries"]] == ["South field", "North field"]
    assert len(phone.get("/api/v1/diary?plot=north field", headers=me).json()["entries"]) == 1
    assert phone.get("/api/v1/diary", headers=other).json()["entries"] == []
    assert phone.delete(f"/api/v1/diary/{entry['id']}", headers=other).status_code == 404
    assert phone.delete(f"/api/v1/diary/{entry['id']}", headers=me).json() == {"ok": True}


@pytest.mark.parametrize("bad", [{"kind": "magic"}, {"done_on": "27-10-2026"}, {"done_on": "2026-02-30"},
                                 {"cost": -5}, {"plot": ""}])
def test_diary_rejects_invalid_entries(phone, bad):
    me, _ = _register(phone)
    assert phone.post("/api/v1/diary", headers=me, json=SPRAY | bad).status_code == 422


def test_admin_sees_who_is_logged_in_with_device(phone):
    phone.post("/api/v1/auth/register", json={"username": "ravi", "password": "secret-pass-1"},
               headers={"X-Client": "AGROBOTAI app / Android 16"})
    admin = _admin_headers(phone)
    body = phone.get("/api/v1/admin/sessions", headers=admin).json()
    ravi = next(s for s in body["sessions"] if s["username"] == "ravi")
    assert ravi["device"] == "AGROBOTAI app / Android 16" and ravi["ip"] == "192.168.1.50" and ravi["online"] is True
    assert body["online_users"] == 2
    assert all("token" not in k for s in body["sessions"] for k in s)


def test_farmers_cannot_see_sessions(phone):
    me, _ = _register(phone)
    assert phone.get("/api/v1/admin/sessions", headers=me).status_code == 403
    assert phone.get("/api/v1/admin/sessions").status_code == 401


def test_diary_accepts_labour_and_sale_for_profit_book(phone):
    me, _ = _register(phone)
    sale = phone.post("/api/v1/diary", headers=me, json=SPRAY | {"kind": "sale", "cost": 12000, "remind_on": None}).json()["entry"]
    assert sale["kind"] == "sale" and sale["cost"] == 12000
    assert phone.post("/api/v1/diary", headers=me, json=SPRAY | {"kind": "labour", "cost": 800}).status_code == 201


def test_repeating_reminder_rolls_forward_and_needs_a_first_date(phone):
    from datetime import date

    from src.store import next_reminder

    today = date(2026, 11, 11)
    assert next_reminder("2026-11-01", 3, today) == "2026-11-13"   # 1, 4, 7, 10, 13
    assert next_reminder("2026-11-11", 3, today) == "2026-11-11"   # due today stays today
    assert next_reminder("2026-11-20", 3, today) == "2026-11-20"   # future first date untouched
    assert next_reminder("2026-11-01", None, today) == "2026-11-01"  # one-time reminders never move
    me, _ = _register(phone)
    water = SPRAY | {"kind": "irrigation", "remind_on": "2020-01-01", "repeat_days": 7}
    entry = phone.post("/api/v1/diary", headers=me, json=water).json()["entry"]
    assert entry["repeat_days"] == 7 and entry["remind_on"] >= date.today().isoformat()
    assert phone.post("/api/v1/diary", headers=me, json=water | {"remind_on": None}).status_code == 422
    assert phone.post("/api/v1/diary", headers=me, json=water | {"repeat_days": 0}).status_code == 422


def test_export_csv_is_private_and_excel_safe(phone):
    me, _ = _register(phone, "farmer1")
    other, _ = _register(phone, "farmer2")
    phone.post("/api/v1/diary", headers=me, json=SPRAY | {"remind_on": None})
    phone.post("/api/v1/diary", headers=me, json=SPRAY | {"kind": "sale", "cost": 9000, "product": "=HYPERLINK(1)", "remind_on": None})
    res = phone.get("/api/v1/export.csv", headers=me)
    assert res.headers["content-type"].startswith("text/csv") and "agrobotai_diary.csv" in res.headers["content-disposition"]
    lines = res.text.lstrip("\ufeff").splitlines()
    assert lines[0] == "Date,Plot,Activity,Product,Quantity,Spent (Rs),Earned (Rs),Note"
    assert "2026-10-27,North field,spray,Neem oil,3 ml/L,250.0,," in lines
    assert any(",sale,'=HYPERLINK(1)," in line and ",,9000.0," in line for line in lines)  # formula made harmless, amount under Earned
    assert len(phone.get("/api/v1/export.csv", headers=other).text.splitlines()) == 1  # header only
    assert phone.get("/api/v1/export.csv?what=scans", headers=me).text.lstrip("\ufeff").startswith("Date,Plot,Crop,Result")
    assert phone.get("/api/v1/export.csv?what=users", headers=me).status_code == 422
    assert phone.get("/api/v1/export.csv").status_code == 401
