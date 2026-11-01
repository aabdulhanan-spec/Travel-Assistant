import json
from datetime import date, timedelta
from typing import Optional

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from tools.http import ExternalServiceError, get_json


GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
WEATHER_CODES = {
    0: "clear",
    1: "mainly clear",
    2: "partly cloudy",
    3: "overcast",
    45: "fog",
    48: "depositing rime fog",
    51: "light drizzle",
    53: "moderate drizzle",
    55: "dense drizzle",
    61: "slight rain",
    63: "moderate rain",
    65: "heavy rain",
    71: "slight snow",
    73: "moderate snow",
    75: "heavy snow",
    80: "rain showers",
    81: "moderate rain showers",
    82: "violent rain showers",
    95: "thunderstorm",
}


class WeatherInput(BaseModel):
    location: str = Field(description="A city or place name.")
    travel_date: Optional[str] = Field(
        default=None,
        description="Optional single date in YYYY-MM-DD format.",
    )
    start_date: Optional[str] = Field(
        default=None,
        description="Optional forecast-range start date in YYYY-MM-DD format.",
    )
    end_date: Optional[str] = Field(
        default=None,
        description="Optional forecast-range end date in YYYY-MM-DD format.",
    )
    forecast_days: int = Field(
        default=5,
        ge=1,
        le=16,
        description="Number of forecast days when no exact date is supplied.",
    )


def get_weather(
    location: str,
    travel_date: Optional[str] = None,
    forecast_days: int = 5,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> str:
    if not location.strip():
        return json.dumps({"error": "A location is required."})
    if travel_date and (start_date or end_date):
        return json.dumps({
            "error": "Use travel_date or start_date/end_date, not both.",
        })
    if end_date and not start_date:
        return json.dumps({"error": "end_date requires start_date."})
    try:
        if start_date:
            requested_start = date.fromisoformat(start_date)
        elif travel_date:
            requested_start = date.fromisoformat(travel_date)
        else:
            requested_start = None
        requested_end = date.fromisoformat(end_date) if end_date else requested_start
    except ValueError:
        return json.dumps({"error": "Weather dates must use YYYY-MM-DD format."})

    today = date.today()
    if requested_start and (
        requested_start < today
        or requested_start > today + timedelta(days=15)
        or requested_end is None
        or requested_end < requested_start
        or requested_end > today + timedelta(days=15)
    ):
        return json.dumps({
            "location": location,
            "error": (
                "Open-Meteo's forecast is not available for that date range. "
                "No historical or long-range weather was inferred."
            ),
        })

    try:
        geocoding = get_json(
            GEOCODING_URL,
            {"name": location, "count": 1, "language": "en", "format": "json"},
        )
        results = geocoding.get("results") or []
        if not results:
            return json.dumps({"location": location, "error": "Location not found."})
        place = results[0]
        params = {
            "latitude": place["latitude"],
            "longitude": place["longitude"],
            "current": "temperature_2m,precipitation,weather_code",
            "daily": (
                "weather_code,temperature_2m_max,temperature_2m_min,"
                "precipitation_probability_max"
            ),
            "timezone": "auto",
        }
        if requested_start:
            params["start_date"] = requested_start.isoformat()
            params["end_date"] = requested_end.isoformat()
        else:
            params["forecast_days"] = max(1, min(forecast_days, 16))
        forecast = get_json(FORECAST_URL, params)
    except (ExternalServiceError, KeyError) as exc:
        return json.dumps({
            "location": location,
            "error": f"Live weather data could not be retrieved: {exc}",
        })

    daily = forecast.get("daily") or {}
    dates = daily.get("time") or []
    daily_rows = []

    def daily_value(name, index):
        values = daily.get(name)
        if isinstance(values, list) and index < len(values):
            return values[index]
        return None

    for index, forecast_date in enumerate(dates):
        code = daily_value("weather_code", index)
        rain = daily_value("precipitation_probability_max", index)
        is_rainy = code in {51, 53, 55, 61, 63, 65, 80, 81, 82, 95}
        if isinstance(rain, (int, float)):
            is_rainy = is_rainy or rain >= 50
        is_sunny = code in {0, 1} and (
            rain is None or (isinstance(rain, (int, float)) and rain < 30)
        )
        daily_rows.append({
            "date": forecast_date,
            "condition": WEATHER_CODES.get(code, "unknown"),
            "temperature_max_c": daily_value("temperature_2m_max", index),
            "temperature_min_c": daily_value("temperature_2m_min", index),
            "precipitation_probability_percent": rain,
            "is_rainy": is_rainy,
            "is_sunny": is_sunny,
            "activity_hint": (
                "Prefer indoor attractions."
                if is_rainy
                else "Outdoor activities may be suitable."
                if is_sunny
                else "Use the detailed forecast and local conditions to choose."
            ),
        })
    if requested_start and not daily_rows:
        return json.dumps({
            "location": location,
            "error": "No forecast was returned for the requested date range.",
        })

    current = forecast.get("current")
    if isinstance(current, dict):
        current = {
            **current,
            "condition": WEATHER_CODES.get(
                current.get("weather_code"),
                "unknown",
            ),
        }

    return json.dumps({
        "location": {
            "name": place.get("name"),
            "admin1": place.get("admin1"),
            "country": place.get("country"),
        },
        "source": "Open-Meteo",
        "source_url": "https://open-meteo.com/",
        "current": current,
        "daily": daily_rows,
        "forecast_note": "Forecast values are model estimates, not guarantees.",
    }, ensure_ascii=False)


def create_weather_tool() -> StructuredTool:
    return StructuredTool.from_function(
        func=get_weather,
        name="weather",
        description=(
            "Get current conditions and Open-Meteo forecasts for a location, "
            "including temperature and precipitation probability. Use for "
            "weather questions and to plan activities around requested dates. "
            "For a multi-day trip, request start_date and end_date together."
        ),
        args_schema=WeatherInput,
    )
