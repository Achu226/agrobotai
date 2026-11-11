"""
Today's mandi (market) prices from Agmarknet, published on data.gov.in (free API key needed:
register at https://data.gov.in, then put DATA_GOV_API_KEY in .env, e.g. with scripts\\set_market_key.ps1).

Only real published prices are returned; without a key or when the service is down, the reply says so.
Prices are Rs per quintal (100 kg), as published.
"""
from __future__ import annotations

import time

import requests

from src import config

URL = "https://api.data.gov.in/resource/9ef84268-d588-465a-a308-a864a43d0070"  # Current daily price of commodities (Mandi)
CACHE_SECONDS = 1800
_cache: dict[tuple[str, str], tuple[float, dict]] = {}


def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def prices(commodity: str, state: str = "Tamil Nadu", get=requests.get) -> dict:
    key = config.DATA_GOV_API_KEY
    if not key:
        return {"ok": False, "code": "not_configured",
                "error": "Market prices need a free data.gov.in API key. Register at data.gov.in and run scripts\\set_market_key.ps1."}
    cached = _cache.get((commodity, state))
    if cached and time.time() - cached[0] < CACHE_SECONDS:
        return cached[1]
    try:
        res = get(URL, timeout=15, params={"api-key": key, "format": "json", "limit": 100,
                                            "filters[state.keyword]": state, "filters[commodity]": commodity})
        res.raise_for_status()
        rows = res.json().get("records") or []
    except (requests.RequestException, ValueError) as exc:
        return {"ok": False, "code": "unavailable", "error": f"Market prices unavailable ({exc.__class__.__name__})"}
    records = sorted(({
        "market": r.get("market"), "district": r.get("district"), "variety": r.get("variety"),
        "arrival_date": r.get("arrival_date"), "min_price": _num(r.get("min_price")),
        "max_price": _num(r.get("max_price")), "modal_price": _num(r.get("modal_price")),
    } for r in rows if _num(r.get("modal_price")) is not None), key=lambda r: (r["district"] or "", r["market"] or ""))
    out = {"ok": True, "commodity": commodity, "state": state, "unit": "Rs per quintal (100 kg)",
           "source": "Agmarknet via data.gov.in", "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%S"), "records": records}
    _cache[(commodity, state)] = (time.time(), out)
    return out
