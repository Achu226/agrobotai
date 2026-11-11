from src.weather_forecast import calculate_disease_risk


def _weather(temp, humidity, precip, days):
    """days: (min_temp, avg_temp, avg_humidity, max_humidity, precip_mm) per forecast day."""
    return {
        "ok": True, "location": "Test", "localtime": "2026-10-27 12:00",
        "current": {"temp_c": temp, "humidity": humidity, "precipitation_mm": precip, "condition": "x"},
        "forecast": [{"date": f"2026-10-{27 + i}", "min_temp_c": lo, "max_temp_c": avg + 5, "avg_temp_c": avg,
                      "avg_humidity": h, "max_humidity": hmax, "total_precip_mm": p, "chance_of_rain": 0,
                      "condition": "x"} for i, (lo, avg, h, hmax, p) in enumerate(days)],
    }


SALEM_DRY = _weather(26, 60, 0, [(21, 27, 62, 85, 0)] * 3)          # the live reading that gave "CRITICAL"
TN_MONSOON = _weather(27, 85, 2, [(24, 27, 86, 96, 12)] * 3)        # NE-monsoon wet spell on the plains
NILGIRIS_BLIGHT = _weather(17, 95, 4, [(13, 17, 92, 99, 8)] * 3)    # cool, wet hill weather


def _no_spray(r):
    text = f"{r['recommended_action']} {r['warning'] or ''}".lower()
    return "spray" not in text and "fungicide" not in text


def test_ordinary_tamil_nadu_weather_is_not_alarming():
    r = calculate_disease_risk(SALEM_DRY)
    assert r["risk_level"] in ("LOW", "MODERATE")
    assert r["highest_risk_disease"] == "Powdery Mildew"
    assert "inspect" in r["recommended_action"].lower()
    assert r["disease_risks"]["Late Blight"] == 0


def test_monsoon_weather_is_never_critical_without_a_detection():
    r = calculate_disease_risk(TN_MONSOON)
    assert r["risk_level"] == "HIGH"
    assert r["disease_risks"]["Late Blight"] == 0   # plains are too warm for late blight


def test_cool_wet_blight_weather_is_high():
    r = calculate_disease_risk(NILGIRIS_BLIGHT)
    assert r["risk_level"] == "HIGH"
    assert r["highest_risk_disease"] == "Late Blight"


def test_blight_needs_consecutive_days():
    one_day = _weather(30, 60, 0, [(13, 17, 92, 99, 8), (22, 28, 60, 80, 0), (22, 28, 60, 80, 0)])
    assert calculate_disease_risk(one_day)["disease_risks"]["Late Blight"] < 30


def test_no_spray_advice_from_weather_alone():
    for w in (SALEM_DRY, TN_MONSOON, NILGIRIS_BLIGHT):
        r = calculate_disease_risk(w)
        assert _no_spray(r) and r["warning"] is None
        assert r["risk_level"] != "CRITICAL"


def test_confirmed_detection_with_favourable_weather_escalates():
    r = calculate_disease_risk(NILGIRIS_BLIGHT, detected_disease="Tomato___Late_blight")
    assert r["risk_level"] == "CRITICAL"
    assert "spray" in r["recommended_action"].lower() and r["warning"]


def test_healthy_or_unfavoured_detection_does_not_escalate():
    assert _no_spray(calculate_disease_risk(SALEM_DRY, detected_disease="Tomato___healthy"))
    r = calculate_disease_risk(SALEM_DRY, detected_disease="Tomato___Late_blight")
    assert r["risk_level"] != "CRITICAL" and r["warning"] is None
