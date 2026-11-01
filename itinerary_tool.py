import json
from datetime import date, timedelta
from typing import Optional

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field


class ItineraryInput(BaseModel):
    destination: str = Field(description="Requested city, region, or country.")
    days: int = Field(ge=1, le=14)
    attractions_json: str = Field(
        description=(
            "JSON array of attractions found by other tools. Each item may include "
            "name, indoor (boolean), cost_cad (number or null), neighborhood, "
            "latitude, longitude, verified_opening_hours, and source_url."
        )
    )
    budget_cad: Optional[float] = Field(default=None, ge=0)
    start_date: Optional[str] = Field(default=None, description="YYYY-MM-DD.")
    starting_location: Optional[str] = Field(default=None)
    preference: str = Field(
        default="balanced",
        description="One of: balanced, indoor, or outdoor.",
    )
    weather_preference: str = Field(default="")
    interests: str = Field(default="")
    weather_json: str = Field(default="{}", description="Weather-tool result JSON.")
    routes_json: str = Field(default="{}", description="Maps-tool result JSON.")


def _decode_object(value: str, label: str):
    try:
        decoded = json.loads(value)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{label} must be valid JSON.") from exc
    if not isinstance(decoded, (dict, list)):
        raise ValueError(f"{label} must contain a JSON object or array.")
    return decoded


def build_itinerary(
    days: int,
    attractions_json: str,
    destination: str,
    budget_cad: Optional[float] = None,
    start_date: Optional[str] = None,
    starting_location: Optional[str] = None,
    preference: str = "balanced",
    weather_preference: str = "",
    interests: str = "",
    weather_json: str = "{}",
    routes_json: str = "{}",
) -> str:
    if not 1 <= days <= 14:
        return json.dumps({"error": "Trip length must be between 1 and 14 days."})
    try:
        attractions = _decode_object(attractions_json, "attractions_json")
        weather = _decode_object(weather_json, "weather_json")
        routes = _decode_object(routes_json, "routes_json")
        first_date = date.fromisoformat(start_date) if start_date else None
    except ValueError as exc:
        return json.dumps({"error": str(exc)})

    if not isinstance(attractions, list):
        return json.dumps({"error": "attractions_json must be a JSON array."})
    candidates = [
        item for item in attractions
        if isinstance(item, dict) and str(item.get("name", "")).strip()
    ]
    if not candidates:
        return json.dumps({
            "error": (
                "No attraction candidates were supplied. Search the local guide "
                "when applicable or current web sources before generating an itinerary."
            )
        })

    route_order = routes.get("optimized_order", []) if isinstance(routes, dict) else []
    route_positions = {
        str(place).strip().lower(): index
        for index, place in enumerate(route_order)
    }
    nearby_groups = routes.get("nearby_groups", []) if isinstance(routes, dict) else []

    budget_pruned_count = 0
    all_candidate_costs_known = all(
        isinstance(item.get("cost_cad"), (int, float))
        and item.get("cost_cad") >= 0
        for item in candidates
    )
    if budget_cad is not None and all_candidate_costs_known:
        affordable = []
        remaining_budget = budget_cad
        for attraction in sorted(candidates, key=lambda item: item["cost_cad"]):
            cost = float(attraction["cost_cad"])
            if cost <= remaining_budget:
                affordable.append(attraction)
                remaining_budget -= cost
            else:
                budget_pruned_count += 1
        candidates = affordable

    normalized_preference = preference.strip().lower()
    if normalized_preference not in {"balanced", "indoor", "outdoor"}:
        normalized_preference = "balanced"
    interest_terms = {
        term.strip().lower() for term in interests.split(",") if term.strip()
    }
    days_data = (weather.get("daily") or []) if isinstance(weather, dict) else []
    if not isinstance(days_data, list):
        days_data = []

    def day_weather(index):
        if first_date:
            wanted_date = (first_date + timedelta(days=index)).isoformat()
            for forecast in days_data:
                if (
                    isinstance(forecast, dict)
                    and forecast.get("date") == wanted_date
                ):
                    return forecast
            return {}
        if index < len(days_data) and isinstance(days_data[index], dict):
            return days_data[index]
        return {}

    def score(attraction, day_index):
        indoor = attraction.get("indoor")
        forecast = day_weather(day_index)
        rain = forecast.get("precipitation_probability_percent")
        value = 0
        if normalized_preference == "indoor" and indoor is True:
            value += 4
        elif normalized_preference == "outdoor" and indoor is False:
            value += 4
        if isinstance(rain, (int, float)):
            if rain >= 50 and indoor is True:
                value += 5
            elif rain < 30 and indoor is False:
                value += 3
        category = str(attraction.get("category", "")).lower()
        if any(term in category or term in str(attraction.get("name", "")).lower()
               for term in interest_terms):
            value += 2
        return value

    def route_position(attraction):
        name = str(attraction.get("name", "")).strip().lower()
        if name in route_positions:
            return route_positions[name]
        for route_name, position in route_positions.items():
            if name and (name in route_name or route_name in name):
                return position
        return len(route_positions)

    def nearby_group(attraction):
        name = str(attraction.get("name", "")).strip().lower()
        for index, group in enumerate(nearby_groups):
            if not isinstance(group, dict):
                continue
            places = group.get("places") or []
            if any(
                name and (
                    name in str(place).lower()
                    or str(place).lower() in name
                )
                for place in places
            ):
                return index + 1
        return None

    remaining = list(candidates)
    itinerary_days = []
    known_cost_total = 0.0
    unknown_cost_count = 0
    all_costs_known = True
    for day_index in range(days):
        forecast = day_weather(day_index)
        ranked = sorted(
            remaining,
            key=lambda item: (
                -score(item, day_index),
                route_position(item),
            ),
        )
        selected = ranked[:3]
        remaining = [item for item in remaining if item not in selected]
        stops = []
        for attraction in selected:
            cost = attraction.get("cost_cad")
            if isinstance(cost, (int, float)) and cost >= 0:
                known_cost_total += float(cost)
            else:
                cost = None
                unknown_cost_count += 1
                all_costs_known = False
            stops.append({
                "name": str(attraction["name"]).strip(),
                "indoor": attraction.get("indoor"),
                "neighborhood": attraction.get("neighborhood"),
                "admission_cost_cad": cost,
                "price_source": attraction.get("source_url"),
                "verified_opening_hours": attraction.get("verified_opening_hours"),
                "nearby_group": nearby_group(attraction),
            })
        itinerary_days.append({
            "date": (
                (first_date + timedelta(days=day_index)).isoformat()
                if first_date else None
            ),
            "weather": forecast or None,
            "stops": stops,
        })

    within_budget = None
    if budget_cad is not None and all_costs_known:
        within_budget = known_cost_total <= budget_cad

    return json.dumps({
        "destination": destination,
        "starting_location": starting_location,
        "weather_preference": weather_preference,
        "days": itinerary_days,
        "estimated_known_admission_total_cad": round(known_cost_total, 2),
        "unknown_admission_price_count": unknown_cost_count,
        "budget_cad": budget_cad,
        "known_admission_costs_within_budget": within_budget,
        "attractions_omitted_to_respect_budget": budget_pruned_count,
        "budget_note": (
            "Only supplied admission prices are included. Meals, local transport, "
            "taxes, and unpriced attractions are excluded; unknown costs prevent "
            "a total-budget guarantee."
        ),
        "route_information": routes,
        "route_note": (
            "Routes and travel durations are included only when supplied by the "
            "maps tool; no missing distance or duration was estimated."
        ),
    }, ensure_ascii=False)


def create_itinerary_tool() -> StructuredTool:
    return StructuredTool.from_function(
        func=build_itinerary,
        name="build_itinerary",
        description=(
            "Turn verified attraction, weather, budget, and route tool results "
            "into a day-by-day plan. Pass facts from other tools as JSON; do not "
            "invent attractions, prices, opening hours, weather, distances, or times."
        ),
        args_schema=ItineraryInput,
    )
