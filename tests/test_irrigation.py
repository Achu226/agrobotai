from datetime import datetime, timedelta, timezone

import pytest

from src import irrigation


def _device(moisture, age_s=10, device="pi-1"):
    received = (datetime.now(timezone.utc) - timedelta(seconds=age_s)).astimezone().isoformat(timespec="seconds")
    return {"device_id": device, "received_at": received, "readings": {"soil_moisture_pct": moisture}}


def _weather(mm_today, mm_tomorrow, chance):
    return {"ok": True, "forecast": [{"total_precip_mm": mm_today, "chance_of_rain": chance},
                                     {"total_precip_mm": mm_tomorrow, "chance_of_rain": chance},
                                     {"total_precip_mm": 50, "chance_of_rain": 100}]}  # day 3 is ignored


DRY_WEEK = _weather(0, 0, 5)
RAINY = _weather(4, 6, 80)


@pytest.mark.parametrize("moisture, weather, code", [
    (18, DRY_WEEK, "water_now"),
    (18, RAINY, "dry_rain_coming"),
    (33, DRY_WEEK, "water_this_evening"),
    (33, RAINY, "skip_rain_expected"),
    (55, DRY_WEEK, "moisture_ok"),
    (92, DRY_WEEK, "waterlogged"),
])
def test_moisture_and_rain_decide_the_advice(moisture, weather, code):
    res = irrigation.advice([_device(moisture)], weather)
    assert [f["code"] for f in res["fields"]] == [code]
    assert res["code"] is None


def test_rain_total_uses_today_and_tomorrow_only():
    res = irrigation.advice([], RAINY)
    assert res["rain_next_2_days_mm"] == 10.0 and res["rain_chance_pct"] == 80 and res["rain_expected"] is True


def test_light_or_unlikely_rain_is_not_a_reason_to_skip():
    assert irrigation.advice([_device(33)], _weather(1, 1, 90))["fields"][0]["code"] == "water_this_evening"
    assert irrigation.advice([_device(33)], _weather(10, 10, 30))["fields"][0]["code"] == "water_this_evening"


def test_no_sensor_never_guesses_soil_moisture():
    assert irrigation.advice([], DRY_WEEK)["code"] == "no_sensor"
    assert irrigation.advice([], RAINY)["code"] == "no_sensor_rain_expected"
    stale = irrigation.advice([_device(10, age_s=3600)], DRY_WEEK)
    assert stale["fields"] == [] and stale["code"] == "no_sensor"


def test_without_forecast_moisture_alone_decides():
    res = irrigation.advice([_device(18)], {"ok": False})
    assert res["forecast_available"] is False and res["fields"][0]["code"] == "water_now"
