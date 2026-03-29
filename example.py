import os
import httpx
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("GOOGLE_PLACES_API_KEY")

GEOCODING_URL = "https://maps.googleapis.com/maps/api/geocode/json"
NEARBY_SEARCH_URL = "https://places.googleapis.com/v1/places:searchNearby"

MAX_RADIUS_METERS = 50000  # Nearby Search hard cap


def get_coordinates(city: str) -> tuple[float, float]:
    """Get latitude and longitude for a city name using the Geocoding API."""
    response = httpx.get(GEOCODING_URL, params={"address": city, "key": API_KEY})
    response.raise_for_status()
    data = response.json()

    if data["status"] != "OK":
        raise ValueError(f"Geocoding failed for '{city}': {data['status']}")

    location = data["results"][0]["geometry"]["location"]
    return location["lat"], location["lng"]


def get_popular_places(city: str, radius_meters: float, top_n: int = 10) -> list[dict]:
    """Return the top N most popular places in a city within the given radius."""
    if radius_meters > MAX_RADIUS_METERS:
        raise ValueError(f"Radius must be {MAX_RADIUS_METERS} meters or less.")

    lat, lng = get_coordinates(city)

    payload = {
        "locationRestriction": {
            "circle": {
                "center": {"latitude": lat, "longitude": lng},
                "radius": radius_meters,
            }
        },
        "rankPreference": "POPULARITY",
        "maxResultCount": 20,
    }

    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": API_KEY,
        "X-Goog-FieldMask": "places.displayName,places.formattedAddress,places.rating,places.userRatingCount,places.types",
    }

    response = httpx.post(NEARBY_SEARCH_URL, json=payload, headers=headers)
    response.raise_for_status()
    places = response.json().get("places", [])

    return places[:top_n]


def main():
    city = "San Francisco, CA"
    radius_meters = 8000

    print(f"Top 10 most popular places in {city} within {radius_meters} meters:\n")
    places = get_popular_places(city, radius_meters)

    for i, place in enumerate(places, start=1):
        name = place.get("displayName", {}).get("text", "N/A")
        address = place.get("formattedAddress", "N/A")
        rating = place.get("rating", "N/A")
        rating_count = place.get("userRatingCount", "N/A")
        print(f"{i}. {name}")
        print(f"   Address:  {address}")
        print(f"   Rating:   {rating} ({rating_count} reviews)")
        print()


if __name__ == "__main__":
    main()
