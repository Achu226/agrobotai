"""
Weather Integration & Disease Risk Forecasting
Connects to weather APIs and predicts disease outbreak risk based on conditions
"""

from __future__ import annotations
import os
import requests
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from dotenv import load_dotenv

load_dotenv()


# WMO weather interpretation codes used by Open-Meteo
_WMO_CODES = {
    0: "Clear sky", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast", 45: "Fog", 48: "Rime fog",
    51: "Light drizzle", 53: "Drizzle", 55: "Dense drizzle", 56: "Freezing drizzle", 57: "Freezing drizzle",
    61: "Light rain", 63: "Rain", 65: "Heavy rain", 66: "Freezing rain", 67: "Freezing rain",
    71: "Light snow", 73: "Snow", 75: "Heavy snow", 77: "Snow grains",
    80: "Light rain showers", 81: "Rain showers", 82: "Violent rain showers", 85: "Snow showers", 86: "Snow showers",
    95: "Thunderstorm", 96: "Thunderstorm with hail", 99: "Thunderstorm with heavy hail",
}


class WeatherService:
    """Weather data fetching and disease risk modeling"""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("WEATHER_API_KEY", "")
        self.base_url = "http://api.weatherapi.com/v1"

    def get_weather_data(
        self,
        location: str = None,
        lat: float = None,
        lon: float = None,
        days: int = 3
    ) -> Dict[str, Any]:
        """
        Fetch weather data from WeatherAPI.com

        Args:
            location: City name or ZIP code (e.g., "New York" or "10001")
            lat: Latitude (alternative to location)
            lon: Longitude (alternative to location)
            days: Number of forecast days (1-3 for free tier)

        Returns:
            Weather data dictionary
        """
        if not self.api_key:
            # No WeatherAPI.com key: use Open-Meteo (free, no key). Errors are reported, never invented.
            return self._open_meteo(location, lat, lon, days)

        # Determine query parameter
        if lat is not None and lon is not None:
            query = f"{lat},{lon}"
        elif location:
            query = location
        else:
            return {"ok": False, "error": "No location provided"}

        try:
            # Get current weather + forecast
            url = f"{self.base_url}/forecast.json"
            params = {
                "key": self.api_key,
                "q": query,
                "days": min(days, 3),
                "aqi": "no",
                "alerts": "yes"
            }

            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            return {
                "ok": True,
                "provider": "WeatherAPI.com",
                "fetched_at": datetime.now().isoformat(timespec="seconds"),
                "location": data["location"]["name"],
                "region": data["location"]["region"],
                "country": data["location"]["country"],
                "localtime": data["location"]["localtime"],
                "current": self._parse_current_weather(data["current"]),
                "forecast": self._parse_forecast(data["forecast"]["forecastday"]),
                "alerts": data.get("alerts", {}).get("alert", [])
            }

        except requests.exceptions.RequestException as e:
            return {
                "ok": False,
                "error": f"Weather API request failed: {str(e)}"
            }
        except Exception as e:
            return {
                "ok": False,
                "error": f"Weather data parsing failed: {str(e)}"
            }

    def _open_meteo(self, location, lat, lon, days: int) -> Dict[str, Any]:
        try:
            place = {"name": location or f"{lat},{lon}", "admin1": "", "country": ""}
            if lat is None or lon is None:
                if not location:
                    return {"ok": False, "error": "No location provided"}
                found = requests.get("https://geocoding-api.open-meteo.com/v1/search",
                                     params={"name": location, "count": 1}, timeout=10).json().get("results")
                if not found:
                    return {"ok": False, "code": "location_not_found", "error": f"Location '{location}' was not found."}
                place = found[0]
                lat, lon = place["latitude"], place["longitude"]
            res = requests.get("https://api.open-meteo.com/v1/forecast", timeout=10, params={
                # 7 days for the app's weather view; the disease-risk model reads only the first 3
                "latitude": lat, "longitude": lon, "timezone": "auto", "forecast_days": 7,
                "current": "temperature_2m,relative_humidity_2m,precipitation,wind_speed_10m,weather_code,uv_index,is_day",
                "hourly": "temperature_2m,precipitation_probability,precipitation,weather_code,is_day,wind_speed_10m",
                "daily": "temperature_2m_max,temperature_2m_min,temperature_2m_mean,relative_humidity_2m_max,"
                         "relative_humidity_2m_mean,precipitation_sum,precipitation_probability_max,weather_code",
            })
            res.raise_for_status()
            data = res.json()
            cur, daily, hourly = data["current"], data["daily"], data.get("hourly") or {}
            # Next 24 hours from the current hour (times are local, same format as cur["time"])
            now_hour = cur["time"][:13]
            hours = [i for i, t in enumerate(hourly.get("time", [])) if t[:13] >= now_hour][:24]
            return {
                "ok": True,
                "provider": "Open-Meteo",
                "fetched_at": datetime.now().isoformat(timespec="seconds"),
                "location": place.get("name"),
                "region": place.get("admin1", ""),
                "country": place.get("country", ""),
                "localtime": cur["time"].replace("T", " "),
                "current": {
                    "temp_c": cur["temperature_2m"],
                    "temp_f": round(cur["temperature_2m"] * 9 / 5 + 32, 1),
                    "humidity": cur["relative_humidity_2m"],
                    "precipitation_mm": cur["precipitation"],
                    "wind_kph": cur["wind_speed_10m"],
                    "condition": _WMO_CODES.get(cur["weather_code"], "Unknown"),
                    "weather_code": cur["weather_code"],
                    "is_day": bool(cur.get("is_day", 1)),
                    "uv_index": cur.get("uv_index"),
                },
                "hourly": [{
                    "time": hourly["time"][i],
                    "temp_c": hourly["temperature_2m"][i],
                    "chance_of_rain": hourly["precipitation_probability"][i] or 0,
                    "precip_mm": hourly["precipitation"][i],
                    "weather_code": hourly["weather_code"][i],
                    "is_day": bool(hourly["is_day"][i]),
                    "wind_kph": (hourly.get("wind_speed_10m") or [None] * len(hourly["time"]))[i],
                } for i in hours],
                "forecast": [{
                    "date": daily["time"][i],
                    "max_temp_c": daily["temperature_2m_max"][i],
                    "min_temp_c": daily["temperature_2m_min"][i],
                    "avg_temp_c": daily["temperature_2m_mean"][i],
                    "max_humidity": daily["relative_humidity_2m_max"][i],
                    "avg_humidity": daily["relative_humidity_2m_mean"][i],
                    "total_precip_mm": daily["precipitation_sum"][i],
                    "chance_of_rain": daily["precipitation_probability_max"][i] or 0,
                    "condition": _WMO_CODES.get(daily["weather_code"][i], "Unknown"),
                    "weather_code": daily["weather_code"][i],
                } for i in range(len(daily["time"]))],
                "alerts": [],
            }
        except (requests.exceptions.RequestException, KeyError, ValueError, TypeError) as e:
            return {"ok": False, "code": "weather_unavailable", "error": f"Open-Meteo weather request failed: {e}"}

    def _parse_current_weather(self, current: dict) -> dict:
        """Extract relevant current weather metrics"""
        return {
            "temp_c": current["temp_c"],
            "temp_f": current["temp_f"],
            "humidity": current["humidity"],
            "precipitation_mm": current["precip_mm"],
            "wind_kph": current["wind_kph"],
            "condition": current["condition"]["text"],
            "uv_index": current["uv"]
        }

    def _parse_forecast(self, forecast_days: list) -> list:
        """Extract forecast data"""
        parsed = []
        for day in forecast_days:
            parsed.append({
                "date": day["date"],
                "max_temp_c": day["day"]["maxtemp_c"],
                "min_temp_c": day["day"]["mintemp_c"],
                "avg_temp_c": day["day"]["avgtemp_c"],
                "max_humidity": day["day"].get("maxhumidity", 0),
                "avg_humidity": day["day"]["avghumidity"],
                "total_precip_mm": day["day"]["totalprecip_mm"],
                "chance_of_rain": day["day"]["daily_chance_of_rain"],
                "condition": day["day"]["condition"]["text"]
            })
        return parsed


# Daily "favourable weather" tests on a forecast day (or current conditions shaped like one).
# Daily data cannot count wet hours, so mean RH >= 85 (or RH >= 90 with rain) stands in for leaf wetness.
def _wet(d, rain_mm: float = 2) -> bool:
    return d["avg_humidity"] >= 85 or (d["max_humidity"] >= 90 and d["total_precip_mm"] >= rain_mm)


_DISEASE_RULES = {
    # Hutton/Smith: min temp >= 10 °C with long RH >= 90 % spells; sporulation favoured at 10–25 °C.
    "Late Blight": lambda d: d["min_temp_c"] >= 10 and d["avg_temp_c"] <= 25 and _wet(d),
    # Alternaria: warm (about 20–30 °C) with leaf wetness from rain or dew.
    "Early Blight": lambda d: 20 <= d["avg_temp_c"] <= 30 and _wet(d),
    # Downy mildews: cool (15–23 °C) and near-saturated air.
    "Downy Mildew": lambda d: 15 <= d["avg_temp_c"] <= 23 and _wet(d, 1),
    # Bacterial spot spreads by rain splash: warm and properly rainy days.
    "Bacterial Spot": lambda d: 24 <= d["avg_temp_c"] <= 30 and d["total_precip_mm"] >= 5 and d["avg_humidity"] >= 80,
    # Septoria needs extended wetness: humid and rainy, 20–26 °C.
    "Septoria Leaf Spot": lambda d: 20 <= d["avg_temp_c"] <= 26 and d["avg_humidity"] >= 85 and d["total_precip_mm"] >= 1,
    # Powdery mildew: warm, dry, moderate humidity. Common in ordinary dry-season weather.
    "Powdery Mildew": lambda d: 20 <= d["avg_temp_c"] <= 30 and 50 <= d["avg_humidity"] <= 80 and d["total_precip_mm"] < 1,
}
# Powdery mildew also needs inoculum and a susceptible crop stage, so weather alone never makes it urgent.
_WEATHER_CAP = {"Powdery Mildew": 45}


def _norm(text: str) -> str:
    return "".join(ch for ch in text.lower() if ch.isalpha())


def calculate_disease_risk(
    weather_data: Dict[str, Any],
    crop: str = "Tomato",
    detected_disease: Optional[str] = None
) -> Dict[str, Any]:
    """
    Weather-based disease *favourability* over the next 3 days (forecast first, current conditions as a nudge).

    Score per disease: 20 per favourable forecast day, +10 if conditions are favourable right now, and for
    late blight +20 when two consecutive days are favourable (a Hutton-style blight period).
    LOW < 30 <= MODERATE < 60 <= HIGH. Weather alone never gives CRITICAL and never recommends spraying:
    CRITICAL and any mention of spraying need a confirmed detection (`detected_disease`) of a disease the
    weather favours.
    """
    if not weather_data.get("ok"):
        return {
            "ok": False,
            "error": "Invalid weather data",
            "risk_level": "Unknown"
        }

    current = weather_data["current"]
    forecast = weather_data.get("forecast") or []

    temp = current["temp_c"]
    humidity = current["humidity"]
    precip = current["precipitation_mm"]
    now = {"min_temp_c": temp, "avg_temp_c": temp, "avg_humidity": humidity,
           "max_humidity": humidity, "total_precip_mm": precip}

    risks = {}
    for disease, favourable in _DISEASE_RULES.items():
        days = [favourable(d) for d in forecast[:3]]
        score = 20 * sum(days) + (10 if favourable(now) else 0)
        if disease == "Late Blight" and any(a and b for a, b in zip(days, days[1:])):
            score += 20
        risks[disease] = min(score, _WEATHER_CAP.get(disease, 100))

    max_risk_disease = max(risks, key=risks.get)
    max_risk_value = risks[max_risk_disease]

    if max_risk_value >= 60:
        risk_level, risk_color = "HIGH", "orange"
        action = (f"Weather strongly favours {max_risk_disease}. Scout daily: inspect lower and older leaves "
                  "(both sides) for spots or mould, and scan any suspicious leaf with the app before any treatment.")
    elif max_risk_value >= 30:
        risk_level, risk_color = "MODERATE", "yellow"
        action = (f"Weather is suitable for {max_risk_disease}. Inspect leaves every 2–3 days "
                  "and scan any suspicious leaf with the app.")
    else:
        risk_level, risk_color = "LOW", "green"
        action = "Low weather risk. Keep routine weekly scouting of leaves."

    warning = None
    if detected_disease and "healthy" not in detected_disease.lower():
        matched = next((d for d in risks if _norm(d) in _norm(detected_disease)), None)
        action = (f"{detected_disease} was confirmed by your scan: follow the treatment advice from that scan "
                  f"(spray only the product and dose advised there) and keep inspecting nearby plants. {action}")
        if matched and risks[matched] >= 30:
            warning = (f"⚠️ Weather over the next days favours {matched}, so your confirmed {detected_disease} "
                       "may spread. Act on the scan's treatment advice soon.")
            if risks[matched] >= 60:
                risk_level, risk_color = "CRITICAL", "red"

    return {
        "ok": True,
        "location": weather_data["location"],
        "timestamp": weather_data["localtime"],
        "current_conditions": {
            "temperature_c": temp,
            "humidity_percent": humidity,
            "precipitation_mm": precip,
            "condition": current["condition"]
        },
        "disease_risks": risks,
        "highest_risk_disease": max_risk_disease,
        "risk_value": max_risk_value,
        "risk_level": risk_level,
        "risk_color": risk_color,
        "recommended_action": action,
        "warning": warning,
        "forecast_summary": _generate_forecast_summary(forecast)
    }


def _generate_forecast_summary(forecast: List[dict]) -> str:
    """Generate human-readable forecast summary"""
    if not forecast:
        return "No forecast data available"

    summaries = []
    for day in forecast[:3]:
        date = day["date"]
        temp = day["avg_temp_c"]
        humidity = day["avg_humidity"]
        rain = day["chance_of_rain"]
        summaries.append(
            f"{date}: {temp:.1f}°C, {humidity}% humidity, {rain}% rain chance"
        )

    return " | ".join(summaries)


# Example usage
if __name__ == "__main__":
    # Test with a sample location
    weather_service = WeatherService()

    # Example 1: Get weather by city name
    weather_data = weather_service.get_weather_data(location="New Delhi, India")

    if weather_data["ok"]:
        print("Current Weather:")
        print(f"  Location: {weather_data['location']}")
        print(f"  Temperature: {weather_data['current']['temp_c']}°C")
        print(f"  Humidity: {weather_data['current']['humidity']}%")
        print(f"  Condition: {weather_data['current']['condition']}")

        # Calculate disease risk
        risk_data = calculate_disease_risk(weather_data, crop="Tomato")

        print("\nDisease Risk Assessment:")
        print(f"  Risk Level: {risk_data['risk_level']}")
        print(f"  Highest Risk: {risk_data['highest_risk_disease']} ({risk_data['risk_value']}%)")
        print(f"  Action: {risk_data['recommended_action']}")

        print("\nIndividual Disease Risks:")
        for disease, risk in risk_data["disease_risks"].items():
            print(f"  {disease}: {risk}%")
    else:
        print(f"Error: {weather_data['error']}")
