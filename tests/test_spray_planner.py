from src import spray_planner


def hour(t, rain=0, chance=0, wind=8, temp=26, day=True):
    return {"time": f"2026-11-10T{t:02d}:00", "precip_mm": rain, "chance_of_rain": chance, "wind_kph": wind, "temp_c": temp, "is_day": day}


def test_good_morning_is_the_window_and_reasons_are_given():
    hours = [hour(6), hour(7), hour(8), hour(9, temp=34), hour(10, wind=22), hour(11, wind=1)] + [hour(12 + i) for i in range(8)]
    p = spray_planner.plan(hours)
    assert p["ok_now"] and p["best_window"] == {"start": "2026-11-10T06:00", "end": "2026-11-10T08:00", "hours": 3}
    by_time = {h["time"][-5:]: h["problems"] for h in p["hours"]}
    assert by_time["09:00"] == ["hot"] and by_time["10:00"] == ["windy"] and by_time["11:00"] == ["too_calm"]


def test_rain_within_six_hours_blocks_spraying_now():
    hours = [hour(6), hour(7), hour(8), hour(9), hour(10, rain=1.2), hour(11)]
    p = spray_planner.plan(hours)
    assert not p["ok_now"] and p["now_problems"] == ["rain_soon"]
    assert [h["problems"] for h in p["hours"]][4] == ["rain"]
    assert p["best_window"] is None  # after the rain only 1 dry hour remains in this forecast


def test_missing_wind_or_night_is_never_called_safe():
    p = spray_planner.plan([hour(21, day=False), hour(22, wind=None)])
    assert p["hours"][0]["problems"] == ["dark"] and "wind_unknown" in p["hours"][1]["problems"]
    assert p["best_window"] is None and spray_planner.plan([])["now_problems"] == ["no_forecast"]
