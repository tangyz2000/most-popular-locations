"""Diagnose why Westfield Valley Fair is missing from San Jose results.

Hypothesis: `shopping_mall` is not in any TYPE_SWEEP, so the mall can only be
captured by the generic top-20 NearbySearch. In its dense cell, the top-20 is
dominated by retail/food *inside* the mall, pushing the mall itself past rank 20.

Cost: ~6-8 API calls.
"""

import json

import h3
import httpx

from constants import (
    API_KEY,
    CULTURE_AND_LANDMARK_TYPES,
    EXCLUDED_TYPES,
    H3_RESOLUTION,
    NEARBY_SEARCH_URL,
    OUTDOOR_AND_RECREATION_TYPES,
    PLACE_FIELD_MASK,
    TEXT_SEARCH_URL,
)
from sources.utils import normalize


SAN_JOSE_CENTER = (37.3387, -121.8853)


def text_search_one(query: str, lat: float, lng: float) -> dict | None:
    """Find the top result for `query` biased near (lat, lng)."""
    payload = {
        "textQuery": query,
        "locationBias": {"circle": {"center": {"latitude": lat, "longitude": lng}, "radius": 20000}},
        "maxResultCount": 1,
    }
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": API_KEY,
        "X-Goog-FieldMask": PLACE_FIELD_MASK,
    }
    r = httpx.post(TEXT_SEARCH_URL, json=payload, headers=headers)
    r.raise_for_status()
    places = r.json().get("places", [])
    return normalize(places[0]) if places else None


def nearby_top20(lat: float, lng: float, radius_m: float, type_filter: dict | None = None,
                 exclude_mode: str = "excludedTypes") -> list[dict]:
    """exclude_mode: 'excludedTypes' (any-of, current algorithm) or 'excludedPrimaryTypes' (primary only) or 'none'."""
    payload = {
        "locationRestriction": {"circle": {"center": {"latitude": lat, "longitude": lng}, "radius": radius_m}},
        "rankPreference": "POPULARITY",
        "maxResultCount": 20,
    }
    if exclude_mode in ("excludedTypes", "excludedPrimaryTypes"):
        payload[exclude_mode] = list(EXCLUDED_TYPES)
    if type_filter:
        payload.update(type_filter)
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": API_KEY,
        "X-Goog-FieldMask": PLACE_FIELD_MASK,
    }
    r = httpx.post(NEARBY_SEARCH_URL, json=payload, headers=headers)
    r.raise_for_status()
    return [normalize(p) for p in r.json().get("places", [])]


def show_rank(label: str, results: list[dict], target_id: str) -> None:
    sorted_r = sorted(results, key=lambda p: p.get("rating_count") or 0, reverse=True)
    ids = [p["id"] for p in sorted_r]
    if target_id in ids:
        rank = ids.index(target_id) + 1
        print(f"  {label}: FOUND at rank {rank}/{len(sorted_r)}")
    else:
        weakest = sorted_r[-1] if sorted_r else None
        print(f"  {label}: MISSING (returned {len(sorted_r)} places; "
              f"weakest = '{weakest['name']}' w/ {weakest.get('rating_count')} reviews)" if weakest
              else f"  {label}: MISSING (no results)")


def main():
    # 1. Find Valley Fair via TextSearch.
    vf = text_search_one("Westfield Valley Fair mall", *SAN_JOSE_CENTER)
    assert vf, "TextSearch returned no result"
    print("=" * 70)
    print(f"Target: {vf['name']}")
    print(f"  id          = {vf['id']}")
    print(f"  rating      = {vf.get('rating')}  ({vf.get('rating_count'):,} reviews)")
    print(f"  lat,lng     = {vf['lat']}, {vf['lng']}")
    print(f"  types       = {vf.get('types')}")
    print()

    # 2. Diagnose: does any TYPE_SWEEP include any of its types?
    sweep_buckets = {
        "CULTURE_AND_LANDMARK": CULTURE_AND_LANDMARK_TYPES,
        "OUTDOOR_AND_RECREATION": OUTDOOR_AND_RECREATION_TYPES,
        "FOOD_AND_DRINK": {"restaurant", "bar", "cafe"},
    }
    vf_types = set(vf.get("types") or [])
    print("Sweep coverage:")
    for name, bucket in sweep_buckets.items():
        overlap = vf_types & set(bucket)
        print(f"  {name:25s} overlap with place types: {overlap or '(none)'}")
    excluded_overlap = vf_types & EXCLUDED_TYPES
    print(f"  EXCLUDED_TYPES            overlap with place types: {excluded_overlap or '(none)'}")
    print()

    # 3. Walk H3 cells: at each resolution the algorithm searches, check rank.
    print("Coverage by H3 cell (generic top-20, no type filter):")
    for res in (H3_RESOLUTION, H3_RESOLUTION + 1, H3_RESOLUTION + 2):
        cell = h3.latlng_to_cell(vf["lat"], vf["lng"], res)
        clat, clng = h3.cell_to_latlng(cell)
        edge_m = h3.average_hexagon_edge_length(res, unit="m")
        print(f"  res={res}  cell={cell}  center=({clat:.4f},{clng:.4f})  edge~{edge_m:.0f}m")
        results = nearby_top20(clat, clng, edge_m)
        show_rank(f"    generic", results, vf["id"])

    # 4. Test the real fix: switch from excludedTypes (any-of) to excludedPrimaryTypes.
    print()
    print("Proposed fix — same generic search, but using excludedPrimaryTypes:")
    for res in (H3_RESOLUTION, H3_RESOLUTION + 1, H3_RESOLUTION + 2):
        cell = h3.latlng_to_cell(vf["lat"], vf["lng"], res)
        clat, clng = h3.cell_to_latlng(cell)
        edge_m = h3.average_hexagon_edge_length(res, unit="m")
        results = nearby_top20(clat, clng, edge_m, exclude_mode="excludedPrimaryTypes")
        show_rank(f"    res={res} (excludedPrimaryTypes)", results, vf["id"])

    # 5. Also test: with no exclude filter at all, does it appear?
    print()
    print("Sanity check — same generic search with NO exclude filter:")
    for res in (H3_RESOLUTION, H3_RESOLUTION + 1, H3_RESOLUTION + 2):
        cell = h3.latlng_to_cell(vf["lat"], vf["lng"], res)
        clat, clng = h3.cell_to_latlng(cell)
        edge_m = h3.average_hexagon_edge_length(res, unit="m")
        results = nearby_top20(clat, clng, edge_m, exclude_mode="none")
        show_rank(f"    res={res} (no excludes)", results, vf["id"])


if __name__ == "__main__":
    main()
