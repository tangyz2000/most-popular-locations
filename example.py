import shutil
from pathlib import Path

import httpx

import api_stats
import search_log
from constants import API_KEY, GEOCODING_URL, MAX_RADIUS_METERS
from sources import GoogleMapsAPI_nearby_search, GoogleMapsAPI_text_search

SOURCES = [
    GoogleMapsAPI_nearby_search,
    GoogleMapsAPI_text_search,
]


@api_stats.track
def get_coordinates(city: str) -> tuple[float, float]:
    """Get latitude and longitude for a city name using the Geocoding API."""
    response = httpx.get(GEOCODING_URL, params={"address": city, "key": API_KEY})
    response.raise_for_status()
    data = response.json()

    if data["status"] != "OK":
        raise ValueError(f"Geocoding failed for '{city}': {data['status']}")

    location = data["results"][0]["geometry"]["location"]
    return location["lat"], location["lng"]


def get_popular_places(city: str, radius_meters: float) -> list[dict]:
    """Return places in a city by merging results from all sources.

    Each source owns its search strategy. Results are deduplicated by place ID,
    tagged with which sources returned them, and ranked by rating_count descending.
    """
    if radius_meters > MAX_RADIUS_METERS:
        raise ValueError(f"Radius must be {MAX_RADIUS_METERS} meters or less.")

    lat, lng = get_coordinates(city)
    print(f"[Geocode] {city} -> ({lat:.4f}, {lng:.4f})")

    seen_ids: dict[str, int] = {}
    all_places: list[dict] = []

    for source in SOURCES:
        source_name = source.__name__.split(".")[-1]
        for place in source.fetch(lat, lng, radius_meters):
            place_id = place.get("id")
            if not place_id:
                continue
            if place_id not in seen_ids:
                place["_sources"] = [source_name]
                seen_ids[place_id] = len(all_places)
                all_places.append(place)
            else:
                existing = all_places[seen_ids[place_id]]
                if source_name not in existing["_sources"]:
                    existing["_sources"].append(source_name)

    all_places.sort(key=lambda p: p.get("rating_count") or 0, reverse=True)
    return all_places


def main():
    city = "San Francisco"
    radius_meters = 8000
    output_file = "results.txt"

    places = get_popular_places(city, radius_meters)
    header = f"Found {len(places)} places in {city} within {radius_meters} meters:\n"

    lines = [header]
    for i, place in enumerate(places, start=1):
        name = place.get("name", "N/A")
        address = place.get("address", "N/A")
        rating = place.get("rating", "N/A")
        rating_count = place.get("rating_count", "N/A")
        types = ", ".join(place.get("types", []))
        sources = ", ".join(place.get("_sources", []))
        lines.append(f"{i}. {name}")
        lines.append(f"   Address:  {address}")
        lines.append(f"   Rating:   {rating} ({rating_count} reviews)")
        lines.append(f"   Types:    {types}")
        lines.append(f"   Sources:  {sources}")
        lines.append("")

    output = "\n".join(lines)

    with open(output_file, "w", encoding="utf-8") as f:
        f.write(output)

    cached = Path("cached_cities") / f"{city}.txt"
    shutil.copy(output_file, cached)
    print(f"Done. {len(places)} places written to {output_file} and cached to {cached}.")
    search_log.record(city, radius_meters, places)
    api_stats.print_stats()


if __name__ == "__main__":
    main()
