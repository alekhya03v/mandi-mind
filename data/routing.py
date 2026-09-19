"""Best-effort road-distance lookup for farmer-to-market comparisons."""
from __future__ import annotations

import math
from functools import lru_cache
from typing import Any

import requests

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
OSRM_URL = "https://router.project-osrm.org/route/v1/driving"
USER_AGENT = "MandiMind/1.0 (agricultural market comparison)"


def _query(params: dict[str, Any]) -> requests.Response:
    response = requests.get(
        NOMINATIM_URL,
        params=params,
        headers={"User-Agent": USER_AGENT, "Accept-Language": "en"},
        timeout=10,
    )
    response.raise_for_status()
    return response


@lru_cache(maxsize=256)
def _geocode(query: str) -> tuple[float, float] | None:
    try:
        records = _query({"q": query, "format": "jsonv2", "limit": 1}).json()
        if not records:
            return None
        return float(records[0]["lon"]), float(records[0]["lat"])
    except (requests.RequestException, ValueError, KeyError, TypeError):
        return None


def _haversine_km(origin: tuple[float, float], destination: tuple[float, float]) -> float:
    lon1, lat1 = map(math.radians, origin)
    lon2, lat2 = map(math.radians, destination)
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return round(2 * 6371 * math.asin(math.sqrt(a)), 1)


def _road_distance_km(origin: tuple[float, float], destination: tuple[float, float]) -> float | None:
    try:
        coordinates = f"{origin[0]},{origin[1]};{destination[0]},{destination[1]}"
        response = requests.get(
            f"{OSRM_URL}/{coordinates}",
            params={"overview": "false"},
            headers={"User-Agent": USER_AGENT},
            timeout=15,
        )
        response.raise_for_status()
        routes = response.json().get("routes", [])
        return round(float(routes[0]["distance"]) / 1000, 1) if routes else None
    except (requests.RequestException, ValueError, KeyError, TypeError):
        return None


def estimate_distance_between_places(origin: str, destination: str) -> dict[str, Any]:
    """Return the best available distance estimate between two places, using road routing when possible and haversine as a fallback."""
    origin_coords = _geocode(origin)
    destination_coords = _geocode(destination)
    if origin_coords is None or destination_coords is None:
        return {"distance_km": 0.0, "source": "unavailable", "note": "Could not geocode both places, so no distance could be estimated."}

    road_distance = _road_distance_km(origin_coords, destination_coords)
    if road_distance is not None:
        return {"distance_km": road_distance, "source": "osrm", "note": None}

    fallback_distance = _haversine_km(origin_coords, destination_coords)
    return {"distance_km": fallback_distance, "source": "fallback_haversine", "note": "Road routing failed; used a geographic fallback estimate."}


def estimate_market_distances(
    place: str,
    district: str,
    state: str,
    pincode: str,
    markets: list[dict[str, Any]],
) -> dict[str, Any]:
    """Return road distances for markets, or a clear fallback note."""
    origin_query = ", ".join(part for part in (place, pincode, district, state, "India") if part)
    origin = _geocode(origin_query)
    if origin is None:
        return {"distances_km": {}, "source": "unavailable", "note": "Could not locate the farmer's place and PIN code, so transport costs need location data."}

    distances: dict[str, float] = {}
    fallback_used = False
    for market in markets:
        destination_query = ", ".join(
            part for part in (market.get("market"), market.get("district"), state, "India") if part
        )
        destination = _geocode(destination_query)
        if destination is None:
            continue
        distance = _road_distance_km(origin, destination)
        if distance is None:
            distance = _haversine_km(origin, destination)
            fallback_used = True
        distances[market["market"]] = distance

    if not distances:
        return {"distances_km": {}, "source": "unavailable", "note": "No market-to-place distance could be computed with the available routing data."}

    note = None
    if fallback_used:
        note = "Some markets were routed with a geographic fallback because road routing was unavailable."
    elif len(distances) != len(markets):
        note = "Some market locations could not be routed; those markets are shown without an automatic transport estimate."
    return {"distances_km": distances, "source": "OpenStreetMap, OSRM, and haversine fallback" if fallback_used else "OpenStreetMap and OSRM", "note": note}
