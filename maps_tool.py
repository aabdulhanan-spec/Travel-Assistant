import json
import math
import time
from functools import lru_cache
from threading import Lock
from typing import List

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from tools.http import ExternalServiceError, get_json


NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
OSRM_ROUTE_URL = "https://router.project-osrm.org/route/v1/driving"
OSRM_TRIP_URL = "https://router.project-osrm.org/trip/v1/driving"
_GEOCODE_LOCK = Lock()
_LAST_GEOCODE_AT = 0.0


class MapsInput(BaseModel):
    locations: List[str] = Field(
        min_length=1,
        max_length=8,
        description=(
            "One to eight place names. Put the starting location first when "
            "requesting an optimized trip."
        ),
    )


@lru_cache(maxsize=128)
def _geocode(place: str):
    global _LAST_GEOCODE_AT
    with _GEOCODE_LOCK:
        elapsed = time.monotonic() - _LAST_GEOCODE_AT
        if elapsed < 1:
            time.sleep(1 - elapsed)
        results = get_json(
            NOMINATIM_URL,
            {"q": place, "format": "jsonv2", "limit": 1},
            headers={
                "User-Agent": (
                    "TorontoTravelAssistant/1.0 "
                    "(open-source educational travel planner)"
                )
            },
        )
        _LAST_GEOCODE_AT = time.monotonic()

    matches = results if isinstance(results, list) else []
    if not matches:
        return None
    result = matches[0]
    return {
        "query": place,
        "display_name": result.get("display_name"),
        "latitude": float(result["lat"]),
        "longitude": float(result["lon"]),
        "source": "OpenStreetMap Nominatim",
    }


def _straight_line_km(first, second):
    earth_radius_km = 6371.0
    lat1 = math.radians(first["latitude"])
    lat2 = math.radians(second["latitude"])
    delta_lat = lat2 - lat1
    delta_lon = math.radians(second["longitude"] - first["longitude"])
    value = (
        math.sin(delta_lat / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin(delta_lon / 2) ** 2
    )
    return 2 * earth_radius_km * math.asin(math.sqrt(value))


def _nearby_groups(locations, threshold_km=1.5):
    groups = []
    for location in locations:
        matching_group = None
        for group in groups:
            if any(
                _straight_line_km(location, member) <= threshold_km
                for member in group
            ):
                matching_group = group
                break
        if matching_group is None:
            groups.append([location])
        else:
            matching_group.append(location)
    return [
        {
            "places": [place["query"] for place in group],
            "basis": (
                "Approximate straight-line proximity between geocoded points; "
                "not a route distance."
            ),
        }
        for group in groups
        if len(group) > 1
    ]


def get_route_information(locations: List[str]) -> str:
    cleaned = [location.strip() for location in locations if location.strip()]
    if not cleaned:
        return json.dumps({"error": "At least one non-empty location is required."})
    if len(cleaned) > 8:
        return json.dumps({"error": "The public routing request is limited to 8 places."})

    try:
        points = [_geocode(location) for location in cleaned]
    except ExternalServiceError as exc:
        return json.dumps({
            "error": f"OpenStreetMap geocoding failed: {exc}",
            "source": "OpenStreetMap Nominatim",
        })
    missing = [cleaned[index] for index, point in enumerate(points) if point is None]
    if missing:
        return json.dumps({
            "error": "Some locations could not be geocoded.",
            "unmatched_locations": missing,
            "source": "OpenStreetMap Nominatim",
        })

    result = {
        "source": "OpenStreetMap Nominatim and public OSRM demo server",
        "routing_profile": (
            "Driving only. Public OSRM routing does not provide walking or "
            "public-transit estimates."
        ),
        "locations": points,
        "nearby_groups": _nearby_groups(points),
    }
    if len(points) == 1:
        result["route_note"] = "One place was geocoded; no route was requested."
        return json.dumps(result, ensure_ascii=False)

    coordinates = ";".join(
        f"{point['longitude']},{point['latitude']}" for point in points
    )
    try:
        if len(points) == 2:
            route_data = get_json(
                f"{OSRM_ROUTE_URL}/{coordinates}",
                {"overview": "false", "steps": "false"},
            )
            routes = route_data.get("routes") or []
            if route_data.get("code") != "Ok" or not routes:
                return json.dumps({
                    **result,
                    "error": "OSRM did not return a route for these locations.",
                }, ensure_ascii=False)
            route = routes[0]
            result["route"] = {
                "from": points[0]["query"],
                "to": points[1]["query"],
                "distance_km": round(route["distance"] / 1000, 2),
                "duration_minutes": round(route["duration"] / 60),
                "basis": "OSRM driving route estimate.",
            }
        else:
            trip_data = get_json(
                f"{OSRM_TRIP_URL}/{coordinates}",
                {
                    "source": "first",
                    "roundtrip": "false",
                    "overview": "false",
                    "steps": "false",
                },
            )
            trips = trip_data.get("trips") or []
            if trip_data.get("code") != "Ok" or not trips:
                return json.dumps({
                    **result,
                    "error": "OSRM did not return an optimized trip for these locations.",
                }, ensure_ascii=False)
            ordered = sorted(
                enumerate(trip_data.get("waypoints") or []),
                key=lambda item: item[1].get("waypoint_index", item[0]),
            )
            result["optimized_order"] = [
                points[original_index]["query"]
                for original_index, _waypoint in ordered
            ]
            result["route"] = {
                "distance_km": round(trips[0]["distance"] / 1000, 2),
                "duration_minutes": round(trips[0]["duration"] / 60),
                "basis": "OSRM optimized driving-route estimate.",
            }
    except (ExternalServiceError, KeyError, IndexError) as exc:
        return json.dumps({
            **result,
            "error": f"OSRM route data could not be retrieved: {exc}",
        }, ensure_ascii=False)

    result["route_source_url"] = "https://project-osrm.org/"
    return json.dumps(result, ensure_ascii=False)


def create_maps_tool() -> StructuredTool:
    return StructuredTool.from_function(
        func=get_route_information,
        name="maps_distance",
        description=(
            "Geocode places worldwide with OpenStreetMap and obtain real driving "
            "distance/time from OSRM. For one place, return its coordinates; "
            "for two, calculate a route; for three or more, request an optimized "
            "driving order. Never present straight-line proximity as route distance."
        ),
        args_schema=MapsInput,
    )
