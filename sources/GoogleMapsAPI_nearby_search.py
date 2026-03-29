import math
import time

import h3
import httpx

from constants import API_KEY, EXCLUDED_TYPES, H3_RESOLUTION, MAX_RADIUS_METERS, NEARBY_SEARCH_URL, PLACE_FIELD_MASK


def fetch(lat: float, lng: float, radius_meters: float) -> list[dict]:
    """Return normalized places by covering the area with an H3 hex grid."""
    cell_search_radius_m = h3.average_hexagon_edge_length(H3_RESOLUTION, unit="m")
    cells = _get_hex_cells(lat, lng, radius_meters)
    places = []
    for cell in cells:
        cell_lat, cell_lng = h3.cell_to_latlng(cell)
        print(f"[NearbySearch] ({cell_lat:.4f}, {cell_lng:.4f})")
        places.extend(_search_nearby(cell_lat, cell_lng, cell_search_radius_m))
    return places


def _get_hex_cells(lat: float, lng: float, radius_meters: float) -> list[str]:
    center_cell = h3.latlng_to_cell(lat, lng, H3_RESOLUTION)
    cell_edge_m = h3.average_hexagon_edge_length(H3_RESOLUTION, unit="m")
    k = math.ceil(radius_meters / cell_edge_m)
    return list(h3.grid_disk(center_cell, k))


def _search_nearby(lat: float, lng: float, radius_meters: float) -> list[dict]:
    payload = {
        "locationRestriction": {
            "circle": {
                "center": {"latitude": lat, "longitude": lng},
                "radius": min(radius_meters, MAX_RADIUS_METERS),
            }
        },
        "excludedTypes": list(EXCLUDED_TYPES),
        "rankPreference": "POPULARITY",
        "maxResultCount": 20,
    }
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": API_KEY,
        "X-Goog-FieldMask": PLACE_FIELD_MASK,
    }
    for attempt in range(3):
        response = httpx.post(NEARBY_SEARCH_URL, json=payload, headers=headers)
        if response.status_code < 500:
            break
        print(f"[NearbySearch] {response.status_code} error (attempt {attempt + 1}): {response.text}")
        time.sleep(2 ** attempt)
    response.raise_for_status()
    return [_normalize(p) for p in response.json().get("places", [])]


def _normalize(place: dict) -> dict:
    return {
        "id": place.get("id", ""),
        "name": place.get("displayName", {}).get("text", ""),
        "address": place.get("formattedAddress", ""),
        "rating": place.get("rating"),
        "rating_count": place.get("userRatingCount"),
        "types": place.get("types", []),
    }
