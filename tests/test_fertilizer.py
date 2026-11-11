import pytest
from fastapi.testclient import TestClient

import server
from src import fertilizer_calculator as fc
from tests.conftest import LAN_PHONE
from tests.test_api_v1 import _register


def _item(plan, name):
    return next(i for i in plan["items"] if i["product"] == name)


def test_npk_to_bags_per_acre():
    # 46 kg P2O5 -> 100 kg DAP (18 kg N); 100-18 = 82 kg N -> 178.3 kg urea; 30 kg K2O -> 50 kg MOP
    plan = fc.plan(n=100, p2o5=46, k2o=30, acres=1)
    assert _item(plan, "DAP")["kg"] == 100 and _item(plan, "DAP")["bags_to_buy"] == 2
    assert _item(plan, "Urea")["kg"] == pytest.approx(178.3) and _item(plan, "Urea")["bags_to_buy"] == 4
    assert _item(plan, "MOP (Potash)")["kg"] == 50 and _item(plan, "MOP (Potash)")["bags_to_buy"] == 1
    assert plan["extra_n_kg"] == 0


def test_hectare_dose_on_acres_and_extra_nitrogen():
    plan = fc.plan(n=0, p2o5=46 * 2.471, k2o=0, acres=1, dose_per="hectare")
    assert _item(plan, "DAP")["kg"] == 100 and _item(plan, "Urea")["kg"] == 0
    assert plan["extra_n_kg"] == 18  # DAP alone gives more N than asked


def test_fertilizer_endpoint():
    phone = TestClient(server.app, client=LAN_PHONE)
    me, _ = _register(phone)
    body = phone.get("/api/v1/fertilizer", headers=me, params={"n": 100, "p2o5": 46, "k2o": 30, "acres": 2}).json()
    assert _item(body, "DAP")["kg"] == 200
    assert phone.get("/api/v1/fertilizer", headers=me, params={"n": -1, "p2o5": 0, "k2o": 0}).status_code == 422
    assert phone.get("/api/v1/fertilizer", params={"n": 1, "p2o5": 0, "k2o": 0}).status_code == 401
