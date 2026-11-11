import requests

from src import config, market_prices


class _Res:
    def __init__(self, body, status=200):
        self.body, self.status_code = body, status

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code}")

    def json(self):
        return self.body


def test_no_key_says_how_to_get_one(monkeypatch):
    monkeypatch.setattr(config, "DATA_GOV_API_KEY", "")
    r = market_prices.prices("Tomato")
    assert r["ok"] is False and r["code"] == "not_configured" and "data.gov.in" in r["error"]


def test_published_prices_are_passed_through_and_bad_rows_dropped(monkeypatch):
    monkeypatch.setattr(config, "DATA_GOV_API_KEY", "user-key")
    market_prices._cache.clear()
    sent = {}

    def get(url, timeout, params):
        sent.update(params)
        return _Res({"records": [
            {"state": "Tamil Nadu", "district": "Salem", "market": "Salem(Uzhavar Sandhai)", "commodity": "Tomato", "variety": "Hybrid",
             "arrival_date": "10/11/2026", "min_price": "1500", "max_price": "2200", "modal_price": "1800"},
            {"district": "Erode", "market": "Erode", "modal_price": "NR"},  # not a price: dropped, never guessed
        ]})

    r = market_prices.prices("Tomato", get=get)
    assert sent["filters[commodity]"] == "Tomato" and sent["filters[state.keyword]"] == "Tamil Nadu" and sent["api-key"] == "user-key"
    assert r["ok"] and r["unit"].startswith("Rs per quintal")
    assert r["records"] == [{"market": "Salem(Uzhavar Sandhai)", "district": "Salem", "variety": "Hybrid", "arrival_date": "10/11/2026",
                             "min_price": 1500.0, "max_price": 2200.0, "modal_price": 1800.0}]


def test_service_down_is_reported(monkeypatch):
    monkeypatch.setattr(config, "DATA_GOV_API_KEY", "user-key")
    market_prices._cache.clear()
    r = market_prices.prices("Onion", get=lambda *a, **k: _Res({}, status=503))
    assert r["ok"] is False and r["code"] == "unavailable"
