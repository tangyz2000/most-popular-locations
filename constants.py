import os

from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("GOOGLE_PLACES_API_KEY")

GEOCODING_URL = "https://maps.googleapis.com/maps/api/geocode/json"
NEARBY_SEARCH_URL = "https://places.googleapis.com/v1/places:searchNearby"
TEXT_SEARCH_URL = "https://places.googleapis.com/v1/places:searchText"

# Maps each HTTP-calling function name to the API it hits.
# api_stats uses this to resolve @track decorators and pre-initialise counters.
TRACKED_APIS: dict[str, str] = {
    "get_coordinates": "Geocoding",
    "_search_nearby": "NearbySearch",
    "_get_nearby_cities": "NearbySearch",
    "_search_text": "TextSearch",
}

# Fixed query for Text Search — kept constant so results are reproducible across runs.
TEXT_SEARCH_QUERY = "landmarks and tourist attractions"

MAX_RADIUS_METERS = 50000  # Nearby Search hard cap

# H3 resolution 6 has an average edge length of ~3.2 km.
# Use a finer resolution for denser cities (res 7 ≈ 1.2 km, res 8 ≈ 0.46 km).
H3_RESOLUTION = 7

# Adaptive subdivision: if all 20 results are returned AND the least popular place
# has a rating count above this threshold, the cell is considered dense and will be
# subdivided into child H3 cells for a more granular search.
# Dense-area subdivision: a cell is considered dense (and will be subdivided) when
# at least DENSE_AREA_RANK_CUTOFF of its 20 results have >= DENSE_AREA_MIN_RATING_COUNT
# reviews (results sorted by rating_count descending).
# i.e. "the Kth most-reviewed result must still be popular enough."
DENSE_AREA_RANK_CUTOFF = 15       # K — check the 15th result (75th percentile)
DENSE_AREA_MIN_RATING_COUNT = 500  # minimum review count at that rank

# Maximum recursion depth for dense-area subdivision (H3_RESOLUTION + depth).
# Depth 0 = base resolution (7, ~1.2 km edge)
# Depth 1 = resolution 8  (~0.46 km edge)
# Depth 2 = resolution 9  (~0.17 km edge)
MAX_SUBDIVISION_DEPTH = 2

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
}
