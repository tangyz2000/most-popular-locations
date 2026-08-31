import math

import h3

import api_stats
from sources.utils import normalize, post_with_retry
from constants import (
    API_KEY,
    CULTURE_AND_LANDMARK_TYPES,
    DENSE_AREA_MIN_RATING_COUNT,
    DENSE_AREA_RANK_CUTOFF,
    EXCLUDED_TYPES,
    FOOD_AND_DRINK_INCLUDED_TYPES,
    H3_RESOLUTION,
    MAX_RADIUS_METERS,
    MAX_SUBDIVISION_DEPTH,
    NEARBY_SEARCH_URL,
    OUTDOOR_AND_RECREATION_TYPES,
    PLACE_FIELD_MASK,
)


# Type-specific sweeps run at every leaf cell alongside the generic search.
_TYPE_SWEEPS: list[dict] = [
    {"includedPrimaryTypes": list(CULTURE_AND_LANDMARK_TYPES)},
    {"includedPrimaryTypes": list(OUTDOOR_AND_RECREATION_TYPES)},
    {"includedTypes": FOOD_AND_DRINK_INCLUDED_TYPES},
]


def fetch(lat: float, lng: float, radius_meters: float) -> list[dict]:
    """Return normalized places by covering the area with an H3 hex grid.

    Dense cells (saturated at 20 results where the Kth most-reviewed place still
    has >= DENSE_AREA_MIN_RATING_COUNT reviews) are recursively subdivided into
    child H3 cells for more granular coverage.
    """
    cells = _get_hex_cells(lat, lng, radius_meters)
    places: dict[str, dict] = {}
    dense_count = 0
    for cell in cells:
        dense_count += _search_cell(cell, H3_RESOLUTION, places, depth=0)
    print(f"[NearbySearch] {dense_count} dense cells found out of {len(cells)} base cells")
    return list(places.values())


def _search_cell(cell: str, resolution: int, places: dict[str, dict], depth: int) -> int:
    """Search a single cell. Returns the number of dense cells found (including sub-cells)."""
    cell_lat, cell_lng = h3.cell_to_latlng(cell)
    cell_search_radius_m = h3.average_hexagon_edge_length(resolution, unit="m")
    indent = "  " * depth
    print(f"[NearbySearch]{indent} res={resolution} ({cell_lat:.4f}, {cell_lng:.4f})")

    results = _search_nearby(cell_lat, cell_lng, cell_search_radius_m)
    for place in results:
        places.setdefault(place["id"], place)

    # Decide subdivision first so we know whether this is a leaf node.
    dense_count = 0
    will_subdivide = depth < MAX_SUBDIVISION_DEPTH and _is_dense(results)

    if will_subdivide:
        # Dense cell: subdivide into children. Type sweeps are skipped here and
        # delegated to each child so every sub-area is swept exactly once at the
        # finest available resolution — no duplicate calls from parent + children
        # covering the same area.
        kth_place = _kth_by_rating_count(results, DENSE_AREA_RANK_CUTOFF)
        child_resolution = resolution + 1
        print(
            f"[NearbySearch]{indent} dense cell (#{DENSE_AREA_RANK_CUTOFF} by reviews:"
            f" '{kth_place['name']}', {kth_place['rating_count']})"
            f" -> subdividing to res={child_resolution}"
        )
        dense_count = 1
        for child_cell in h3.cell_to_children(cell, child_resolution):
            dense_count += _search_cell(child_cell, child_resolution, places, depth + 1)
    else:
        # Leaf node: run type-specific sweeps to capture popular places that get
        # crowded out by the dominant category in the generic ranking.
        before = len(places)
        for type_filter in _TYPE_SWEEPS:
            for place in _search_nearby(cell_lat, cell_lng, cell_search_radius_m, type_filter):
                places.setdefault(place["id"], place)
        new_found = len(places) - before
        if new_found:
            print(f"[NearbySearch]{indent}   type sweeps added {new_found} new places")

    return dense_count


def _kth_by_rating_count(results: list[dict], k: int) -> dict:
    """Return the Kth result when sorted by rating_count descending (1-indexed)."""
    sorted_results = sorted(results, key=lambda p: p.get("rating_count") or 0, reverse=True)
    return sorted_results[k - 1]


def _is_dense(results: list[dict]) -> bool:
    """True if the cell is saturated and the Kth most-reviewed result clears the threshold.

    Checks that at least DENSE_AREA_RANK_CUTOFF results have >= DENSE_AREA_MIN_RATING_COUNT
    reviews, meaning the cap is likely hiding more popular places beyond position 20.
    """
    if len(results) < 20:
        return False
    kth_rating_count = (_kth_by_rating_count(results, DENSE_AREA_RANK_CUTOFF).get("rating_count") or 0)
    return kth_rating_count > DENSE_AREA_MIN_RATING_COUNT


def _get_hex_cells(lat: float, lng: float, radius_meters: float) -> list[str]:
    center_cell = h3.latlng_to_cell(lat, lng, H3_RESOLUTION)
    cell_edge_m = h3.average_hexagon_edge_length(H3_RESOLUTION, unit="m")
    k = math.ceil(radius_meters / cell_edge_m)
    return list(h3.grid_disk(center_cell, k))


@api_stats.track
def _search_nearby(lat: float, lng: float, radius_meters: float, type_filter: dict | None = None) -> list[dict]:
    payload = {
        "locationRestriction": {
            "circle": {
                "center": {"latitude": lat, "longitude": lng},
                "radius": min(radius_meters, MAX_RADIUS_METERS),
            }
        },
        "excludedPrimaryTypes": list(EXCLUDED_TYPES),
        "rankPreference": "POPULARITY",
        "maxResultCount": 20,
    }
    if type_filter:
        payload.update(type_filter)
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": API_KEY,
        "X-Goog-FieldMask": PLACE_FIELD_MASK,
    }
    response = post_with_retry(NEARBY_SEARCH_URL, json=payload, headers=headers, label="NearbySearch")
    response.raise_for_status()
    return [normalize(p) for p in response.json().get("places", [])]
