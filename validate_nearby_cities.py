import os

import httpx
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("GOOGLE_PLACES_API_KEY")

GEOCODING_URL = "https://maps.googleapis.com/maps/api/geocode/json"
NEARBY_SEARCH_URL = "https://places.googleapis.com/v1/places:searchNearby"


def get_coordinates(city: str) -> tuple[float, float]:
    response = httpx.get(GEOCODING_URL, params={"address": city, "key": API_KEY})
    response.raise_for_status()
    data = response.json()
    if data["status"] != "OK":
        raise ValueError(f"Geocoding failed for '{city}': {data['status']}")
    location = data["results"][0]["geometry"]["location"]
    return location["lat"], location["lng"]


def get_nearby_cities(lat: float, lng: float, radius_meters: float = 40000) -> list[dict]:
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
        "X-Goog-FieldMask": "places.id,places.displayName,places.location,places.userRatingCount",
    }
    response = httpx.post(NEARBY_SEARCH_URL, json=payload, headers=headers)
    response.raise_for_status()
    return response.json().get("places", [])


def main():
    city = "San Francisco, CA"
    print(f"Finding nearby cities for: {city}\n")

    lat, lng = get_coordinates(city)
    print(f"Coordinates: {lat:.4f}, {lng:.4f}\n")

    cities = get_nearby_cities(lat, lng)

    if not cities:
        print("No cities found.")
        return

    print(f"Found {len(cities)} nearby localities:\n")
    for i, place in enumerate(cities, start=1):
        name = place.get("displayName", {}).get("text", "N/A")
        loc = place.get("location", {})
        rating_count = place.get("userRatingCount", "N/A")
        print(f"{i:>2}. {name:<30} ({loc.get('latitude', 0):.4f}, {loc.get('longitude', 0):.4f})  reviews: {rating_count}")


if __name__ == "__main__":
    main()
