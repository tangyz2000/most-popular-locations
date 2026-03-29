import os

from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("GOOGLE_PLACES_API_KEY")

GEOCODING_URL = "https://maps.googleapis.com/maps/api/geocode/json"
NEARBY_SEARCH_URL = "https://places.googleapis.com/v1/places:searchNearby"
TEXT_SEARCH_URL = "https://places.googleapis.com/v1/places:searchText"

# Fixed query for Text Search — kept constant so results are reproducible across runs.
TEXT_SEARCH_QUERY = "landmarks and tourist attractions"

MAX_RADIUS_METERS = 50000  # Nearby Search hard cap

# H3 resolution 6 has an average edge length of ~3.2 km.
# Use a finer resolution for denser cities (res 7 ≈ 1.2 km, res 8 ≈ 0.46 km).
H3_RESOLUTION = 7

# Shared field mask for place results returned by both sources.
PLACE_FIELD_MASK = "places.id,places.displayName,places.formattedAddress,places.rating,places.userRatingCount,places.types"

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
    # Lodging
    "hotel",
    "motel",
    "extended_stay_hotel",
    "budget_japanese_inn",
    "japanese_inn",
    "lodging",
    # Automotive
    "car_dealer",
    "car_rental",
    "used_car_dealer",
}
