"""
Irrigation advice from live soil moisture (Raspberry Pi) + the rain forecast.

Only fresh readings are used (older than SENSOR_STALE_SECONDS = offline). Without a sensor, the advice
says so and only reports the forecast — it never guesses the soil moisture.
"""
from __future__ import annotations

from datetime import datetime, timezone

from src import config


def _rain_outlook(weather: dict | None) -> tuple[float | None, int | None]:
    """Total rain (mm) and highest rain chance (%) for today + tomorrow, or (None, None) without a forecast."""
    days = (weather or {}).get("forecast") or []
    if not (weather or {}).get("ok") or not days:
        return None, None
    nxt = days[:2]
    return round(sum(float(d.get("total_precip_mm") or 0) for d in nxt), 1), max(int(d.get("chance_of_rain") or 0) for d in nxt)


def advice(devices: list[dict], weather: dict | None, now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    rain_mm, rain_chance = _rain_outlook(weather)
    rain_expected = rain_mm is not None and rain_mm >= config.IRRIGATION_RAIN_MM and (rain_chance or 0) >= 60
    fields = []
    for d in devices:
        moisture = d["readings"].get("soil_moisture_pct")
        age = (now - datetime.fromisoformat(d["received_at"])).total_seconds()
        if moisture is None or age > config.SENSOR_STALE_SECONDS:
            continue
        if moisture > config.ALERT_SOIL_WET_PCT:
            code = "waterlogged"
        elif moisture < config.ALERT_SOIL_DRY_PCT:
            code = "dry_rain_coming" if rain_expected else "water_now"
        elif moisture < config.IRRIGATION_SOON_PCT:
            code = "skip_rain_expected" if rain_expected else "water_this_evening"
        else:
            code = "moisture_ok"
        fields.append({"device": d["device_id"], "moisture_pct": moisture, "code": code})
    return {
        "fields": fields,
        "rain_next_2_days_mm": rain_mm,
        "rain_chance_pct": rain_chance,
        "rain_expected": rain_expected,
        "forecast_available": rain_mm is not None,
        # No live moisture: report the forecast only, never a guessed soil state
        "code": None if fields else ("no_sensor_rain_expected" if rain_expected else "no_sensor"),
    }
