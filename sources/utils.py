def normalize(place: dict) -> dict:
    location = place.get("location", {})
    return {
        "id": place.get("id", ""),
        "name": place.get("displayName", {}).get("text", ""),
        "address": place.get("formattedAddress", ""),
        "rating": place.get("rating"),
        "rating_count": place.get("userRatingCount"),
        "types": place.get("types", []),
        "lat": location.get("latitude"),
        "lng": location.get("longitude"),
    }
