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

MAX_RADIUS_METERS = 50000       # Nearby Search hard cap
CITY_DISCOVERY_RADIUS_M = 40000  # radius for finding nearby city centers (text search)

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
PLACE_FIELD_MASK = "places.id,places.displayName,places.formattedAddress,places.rating,places.userRatingCount,places.types,places.location"

# Type-specific sweep groups run at base H3 resolution alongside the generic search.
# Splitting into cohesive groups keeps the popularity ranking meaningful within
# each group (avoids mixing tiny sculptures with major stadiums in one bucket).
#
# Food sweep uses includedTypes (broad match) so all cuisine subtypes are captured:
# e.g. peruvian_restaurant, seafood_restaurant all include "restaurant" in their
# types list, so a single broad filter catches every cuisine without enumerating
# all 200+ food subtypes.
FOOD_AND_DRINK_INCLUDED_TYPES = ["restaurant", "bar", "cafe"]

CULTURE_AND_LANDMARK_TYPES = frozenset({
    # Museums & galleries
    "art_gallery", "art_museum", "history_museum", "museum",
    # Monuments & landmarks
    "castle", "cultural_landmark", "historical_landmark", "monument",
    "observation_deck", "tourist_attraction",
    # Performing arts & entertainment venues
    "amphitheatre", "auditorium", "comedy_club", "concert_hall",
    "live_music_venue", "movie_theater", "opera_house", "philharmonic_hall",
    "planetarium", "performing_arts_theater",
    # Iconic structures
    "ferris_wheel", "fountain", "sculpture",
    # Visitor-oriented
    "visitor_center",
    # Education (tourist-relevant)
    "library", "university",
    # Places of worship
    "buddhist_temple", "church", "hindu_temple", "mosque", "shinto_shrine", "synagogue",
    # Civic landmarks
    "city_hall",
})

OUTDOOR_AND_RECREATION_TYPES = frozenset({
    # Parks & green spaces
    "botanical_garden", "city_park", "dog_park", "garden", "national_park",
    "park", "picnic_ground", "state_park", "wildlife_park", "wildlife_refuge",
    # Nature & scenery
    "beach", "hiking_area", "lake", "mountain_peak", "nature_preserve",
    "scenic_spot", "woods",
    # Zoos & wildlife
    "aquarium", "zoo",
    # Amusement & recreation
    "amusement_center", "amusement_park", "bowling_alley", "casino",
    "event_venue", "golf_course", "ice_skating_rink", "marina",
    "night_club", "plaza", "race_course", "ski_resort", "vineyard",
    "water_park",
    # Sports venues
    "arena", "sports_complex", "stadium",
})

# Places that have any of these types will be excluded from results.
EXCLUDED_TYPES = {
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
    "discount_store",
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
