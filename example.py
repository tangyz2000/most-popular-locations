import math
import os

import h3
import httpx
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("GOOGLE_PLACES_API_KEY")

GEOCODING_URL = "https://maps.googleapis.com/maps/api/geocode/json"
NEARBY_SEARCH_URL = "https://places.googleapis.com/v1/places:searchNearby"

MAX_RADIUS_METERS = 50000  # Nearby Search hard cap

# H3 resolution 6 has an average edge length of ~3.2 km.
# Use a finer resolution for denser cities (res 7 ≈ 1.2 km, res 8 ≈ 0.46 km).
H3_RESOLUTION = 7

# Places that have any of these types will be excluded from results.
EXCLUDED_TYPES = {
    # Fast food & casual chains
    "fast_food_restaurant",
    # Big-box & general retail
    "supermarket",
    "warehouse_store",
    "grocery_store",
    "discount_supermarket",
    "hypermarket",
    "department_store",
    "electronics_store",
    "furniture_store",
    "home_goods_store",
    "home_improvement_store",
    "clothing_store",
    "discount_store",
    "shopping_mall",
    # Transportation
    "airport",
    "international_airport",
    # Health
    "pharmacy",
    "drugstore",
    "hospital",
    "medical_center",
}


def get_coordinates(city: str) -> tuple[float, float]:
    """Get latitude and longitude for a city name using the Geocoding API."""
    response = httpx.get(GEOCODING_URL, params={"address": city, "key": API_KEY})
    response.raise_for_status()
    data = response.json()

    if data["status"] != "OK":
        raise ValueError(f"Geocoding failed for '{city}': {data['status']}")

    location = data["results"][0]["geometry"]["location"]
    return location["lat"], location["lng"]


def get_hex_cells(lat: float, lng: float, radius_meters: float) -> list[str]:
    """Return all H3 cells at H3_RESOLUTION that cover the circular area."""
    center_cell = h3.latlng_to_cell(lat, lng, H3_RESOLUTION)
    cell_edge_m = h3.average_hexagon_edge_length(H3_RESOLUTION, unit="m")
    # Number of rings to span the requested radius
    k = math.ceil(radius_meters / cell_edge_m)
    return list(h3.grid_disk(center_cell, k))


def search_nearby(lat: float, lng: float, radius_meters: float) -> list[dict]:
    """Call the Nearby Search API for a single circle and return places."""
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
        "X-Goog-FieldMask": "places.id,places.displayName,places.formattedAddress,places.rating,places.userRatingCount,places.types",
    }
    response = httpx.post(NEARBY_SEARCH_URL, json=payload, headers=headers)
    response.raise_for_status()
    return response.json().get("places", [])


def get_popular_places(city: str, radius_meters: float) -> list[dict]:
    """Return all places in a city using hex-grid search, sorted by userRatingCount.

    Splits the target area into H3 hexagonal cells, queries each cell
    independently, deduplicates by place ID, then ranks by userRatingCount.
    """
    if radius_meters > MAX_RADIUS_METERS:
        raise ValueError(f"Radius must be {MAX_RADIUS_METERS} meters or less.")

    lat, lng = get_coordinates(city)

    cells = get_hex_cells(lat, lng, radius_meters)
    # Each hex cell is searched with a circle equal to the cell's edge length
    # (≈ circumradius), ensuring full coverage with minimal overlap.
    cell_search_radius_m = h3.average_hexagon_edge_length(H3_RESOLUTION, unit="m")

    seen_ids: set[str] = set()
    all_places: list[dict] = []

    for cell in cells:
        cell_lat, cell_lng = h3.cell_to_latlng(cell)
        for place in search_nearby(cell_lat, cell_lng, cell_search_radius_m):
            place_id = place.get("id")
            if place_id and place_id not in seen_ids:
                seen_ids.add(place_id)
                all_places.append(place)

    all_places.sort(key=lambda p: p.get("userRatingCount", 0), reverse=True)
    return all_places


def main():
    city = "San Francisco, CA"
    radius_meters = 8000
    output_file = "results.txt"

    places = get_popular_places(city, radius_meters)
    header = f"Found {len(places)} places in {city} within {radius_meters} meters:\n"

    lines = [header]
    for i, place in enumerate(places, start=1):
        name = place.get("displayName", {}).get("text", "N/A")
        address = place.get("formattedAddress", "N/A")
        rating = place.get("rating", "N/A")
        rating_count = place.get("userRatingCount", "N/A")
        types = ", ".join(place.get("types", []))
        lines.append(f"{i}. {name}")
        lines.append(f"   Address:  {address}")
        lines.append(f"   Rating:   {rating} ({rating_count} reviews)")
        lines.append(f"   Types:    {types}")
        lines.append("")

    output = "\n".join(lines)

    with open(output_file, "w", encoding="utf-8") as f:
        f.write(output)
    print(f"Results written to {output_file} ({len(places)} places)")


if __name__ == "__main__":
    main()
