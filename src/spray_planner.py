"""
Is it safe to spray? Uses only the real hourly forecast (Open-Meteo); nothing is guessed.

General pesticide-label guidance, not product-specific (always follow the product label):
  - no rain for the next 6 hours, so the spray is not washed off
  - wind 3-15 km/h: stronger wind blows droplets away, near-calm air lets fine drift hang and travel
  - air below 32 °C: hot air evaporates droplets before they reach the leaf
  - daylight only
"""
from __future__ import annotations

RAIN_FREE_HOURS = 6
MAX_RAIN_CHANCE = 40  # %
MIN_RAIN_MM = 0.2
MIN_WIND_KPH, MAX_WIND_KPH = 3, 15
MAX_TEMP_C = 32
MIN_WINDOW_HOURS = 2


def _wet(h: dict) -> bool:
    return (h.get("precip_mm") or 0) >= MIN_RAIN_MM or (h.get("chance_of_rain") or 0) >= MAX_RAIN_CHANCE


def hour_problems(hours: list[dict], i: int) -> list[str]:
    """Reasons hour i is not good for spraying (empty list = good)."""
    h = hours[i]
    problems = []
    if not h.get("is_day", True):
        problems.append("dark")
    if _wet(h):
        problems.append("rain")
    elif any(_wet(x) for x in hours[i + 1:i + RAIN_FREE_HOURS]):
        problems.append("rain_soon")
    wind = h.get("wind_kph")
    if wind is None:
        problems.append("wind_unknown")
    elif wind > MAX_WIND_KPH:
        problems.append("windy")
    elif wind < MIN_WIND_KPH:
        problems.append("too_calm")
    if h.get("temp_c") is not None and h["temp_c"] > MAX_TEMP_C:
        problems.append("hot")
    return problems


def plan(hourly: list[dict]) -> dict:
    """Hour-by-hour verdict for the next 24 h and the first window of at least 2 good hours."""
    hours = [dict(h, problems=hour_problems(hourly, i)) for i, h in enumerate(hourly)]
    for h in hours:
        h["ok"] = not h["problems"]
    window, run = None, []
    for h in hours + [{"ok": False}]:  # sentinel closes the last run
        if h["ok"]:
            run.append(h)
            continue
        if window is None and len(run) >= MIN_WINDOW_HOURS:
            window = run
        run = []
    return {
        "ok_now": bool(hours) and hours[0]["ok"],
        "now_problems": hours[0]["problems"] if hours else ["no_forecast"],
        "best_window": {"start": window[0]["time"], "end": window[-1]["time"], "hours": len(window)} if window else None,
        "hours": [{k: h.get(k) for k in ("time", "ok", "problems", "temp_c", "wind_kph", "chance_of_rain", "precip_mm")} for h in hours],
        "rules": {"rain_free_hours": RAIN_FREE_HOURS, "wind_kph": [MIN_WIND_KPH, MAX_WIND_KPH], "max_temp_c": MAX_TEMP_C},
    }
