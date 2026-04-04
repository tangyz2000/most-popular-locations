import httpx

import api_stats
from constants import (
    API_KEY,
    EXCLUDED_TYPES,
    MAX_RADIUS_METERS,
    NEARBY_SEARCH_URL,
    PLACE_FIELD_MASK,
    TEXT_SEARCH_QUERY,
    TEXT_SEARCH_URL,
)


def fetch(lat: float, lng: float, radius_meters: float) -> list[dict]:
    """Return normalized places by running Text Search once per nearby city center."""
    cities = _get_nearby_cities(lat, lng)
    places = []
    for city in cities:
        loc = city.get("location", {})
        city_name = city.get("displayName", {}).get("text", "unknown")
        print(f"[TextSearch] {city_name} ({loc['latitude']:.4f}, {loc['longitude']:.4f})")
        results = _search_text(loc["latitude"], loc["longitude"], radius_meters)
        places.extend(p for p in results if not EXCLUDED_TYPES.intersection(p.get("types", [])))
    return places


@api_stats.track
def _get_nearby_cities(lat: float, lng: float, radius_meters: float = 40000) -> list[dict]:
    payload = {
        "locationRestriction": {
            "circle": {
                "center": {"latitude": lat, "longitude": lng},
                "radius": radius_meters,
            }
        },
        "includedTypes": ["locality"],
        "rankPreference": "POPULARITY",
        "maxResultCount": 20,
    }
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": API_KEY,
        "X-Goog-FieldMask": "places.id,places.displayName,places.location",
    }
    response = httpx.post(NEARBY_SEARCH_URL, json=payload, headers=headers)
    response.raise_for_status()
    places = response.json().get("places", [])
    print(f"[TextSearch] Found {len(places)} nearby cities")

    seen_ids: set[str] = set()
    unique = []
    for place in places:
        place_id = place.get("id")
        if place_id and place_id not in seen_ids:
            seen_ids.add(place_id)
            unique.append(place)
    return unique


@api_stats.track
def _search_text(lat: float, lng: float, radius_meters: float) -> list[dict]:
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": API_KEY,
        "X-Goog-FieldMask": f"{PLACE_FIELD_MASK},nextPageToken",
    }

    raw_places: list[dict] = []
    page_token: str | None = None

    for _ in range(3):  # max 3 pages × 20 results = 60
        payload: dict = {
            "textQuery": TEXT_SEARCH_QUERY,
            "locationBias": {
                "circle": {
                    "center": {"latitude": lat, "longitude": lng},
                    "radius": min(radius_meters, MAX_RADIUS_METERS),
                }
            },
            "maxResultCount": 20,
        }
        if page_token:
            payload["pageToken"] = page_token

        response = httpx.post(TEXT_SEARCH_URL, json=payload, headers=headers)
        response.raise_for_status()
        data = response.json()
        raw_places.extend(data.get("places", []))
        page_token = data.get("nextPageToken")
        if not page_token:
            break

    return [_normalize(p) for p in raw_places]


def _normalize(place: dict) -> dict:
    return {
        "id": place.get("id", ""),
        "name": place.get("displayName", {}).get("text", ""),
        "address": place.get("formattedAddress", ""),
        "rating": place.get("rating"),
        "rating_count": place.get("userRatingCount"),
        "types": place.get("types", []),
    }
