"""Diagnose why Scarlett's Cabaret is missing from Miami results."""
import json
import math
import httpx
import h3

from constants import (
    API_KEY,
    H3_RESOLUTION,
    NEARBY_SEARCH_URL,
    TEXT_SEARCH_URL,
    PLACE_FIELD_MASK,
    EXCLUDED_TYPES,
)

MIAMI_LAT = 25.7616798
MIAMI_LNG = -80.1917902
RADIUS = 8000


def haversine_m(lat1, lng1, lat2, lng2):
    R = 6_371_000
    a, b = math.radians(lat1), math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    h = math.sin(dlat / 2) ** 2 + math.cos(a) * math.cos(b) * math.sin(dlng / 2) ** 2
    return 2 * R * math.asin(math.sqrt(h))


def text_search(query, lat, lng, radius_m=20000):
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": API_KEY,
        "X-Goog-FieldMask": PLACE_FIELD_MASK,
    }
    payload = {
        "textQuery": query,
        "locationBias": {
            "circle": {"center": {"latitude": lat, "longitude": lng}, "radius": radius_m},
        },
        "maxResultCount": 20,
    }
    r = httpx.post(TEXT_SEARCH_URL, json=payload, headers=headers)
    r.raise_for_status()
    return r.json().get("places", [])


def nearby_search(lat, lng, radius_m, type_filter=None, excluded=True):
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": API_KEY,
        "X-Goog-FieldMask": PLACE_FIELD_MASK,
    }
    payload = {
        "locationRestriction": {
            "circle": {"center": {"latitude": lat, "longitude": lng}, "radius": radius_m},
        },
        "rankPreference": "POPULARITY",
        "maxResultCount": 20,
    }
    if excluded:
        payload["excludedPrimaryTypes"] = list(EXCLUDED_TYPES)
    if type_filter:
        payload.update(type_filter)
    r = httpx.post(NEARBY_SEARCH_URL, json=payload, headers=headers)
    r.raise_for_status()
    return r.json().get("places", [])


print("=" * 70)
print("STEP 1: Find Scarlett's Cabaret via TextSearch")
print("=" * 70)
results = text_search("Scarlett's Cabaret Miami", MIAMI_LAT, MIAMI_LNG, radius_m=20000)
target = None
for p in results:
    name = p.get("displayName", {}).get("text", "")
    addr = p.get("formattedAddress", "")
    rc = p.get("userRatingCount")
    rating = p.get("rating")
    primary = p.get("primaryType", "")
    types = p.get("types", [])
    loc = p.get("location", {})
    print(f"  {name}")
    print(f"    addr: {addr}")
    print(f"    primaryType: {primary}")
    print(f"    types: {types}")
    print(f"    rating: {rating}, reviews: {rc}")
    print(f"    location: {loc}")
    print()
    if "Scarlett" in name and "Miami" in addr and target is None:
        target = p

if target is None:
    print("** Scarlett's Cabaret not found at all via TextSearch! **")
    raise SystemExit(0)

print("=" * 70)
print("STEP 2: Distance check from Miami search center")
print("=" * 70)
loc = target["location"]
plat, plng = loc["latitude"], loc["longitude"]
dist = haversine_m(MIAMI_LAT, MIAMI_LNG, plat, plng)
print(f"  Scarlett's at ({plat:.5f}, {plng:.5f})")
print(f"  Miami center ({MIAMI_LAT:.5f}, {MIAMI_LNG:.5f})")
print(f"  Distance: {dist:.0f} m  (search radius: {RADIUS} m)")
print(f"  Within radius? {dist <= RADIUS}")

print()
print("=" * 70)
print("STEP 3: Check if its primary type is in EXCLUDED_TYPES")
print("=" * 70)
primary = target.get("primaryType", "")
types = target.get("types", [])
print(f"  primaryType: {primary}")
print(f"  in EXCLUDED_TYPES? {primary in EXCLUDED_TYPES}")
excluded_in_types = [t for t in types if t in EXCLUDED_TYPES]
print(f"  Any excluded secondary types: {excluded_in_types}")

print()
print("=" * 70)
print("STEP 4: Which H3 cell does it belong to (res 7)?")
print("=" * 70)
cell = h3.latlng_to_cell(plat, plng, H3_RESOLUTION)
cell_lat, cell_lng = h3.cell_to_latlng(cell)
edge_m = h3.average_hexagon_edge_length(H3_RESOLUTION, unit="m")
print(f"  Cell: {cell}")
print(f"  Cell center: ({cell_lat:.5f}, {cell_lng:.5f})")
print(f"  Cell edge length: {edge_m:.1f} m")

print()
print("=" * 70)
print("STEP 5: Generic NearbySearch at that cell — top 20 by popularity")
print("=" * 70)
results = nearby_search(cell_lat, cell_lng, edge_m, excluded=True)
print(f"  Found {len(results)} results")
sorted_results = sorted(results, key=lambda p: p.get("userRatingCount") or 0, reverse=True)
found = False
for i, p in enumerate(sorted_results, 1):
    name = p.get("displayName", {}).get("text", "")
    rc = p.get("userRatingCount") or 0
    mark = "  -> SCARLETT'S" if "Scarlett" in name else ""
    if "Scarlett" in name:
        found = True
    print(f"  {i:2d}. {name[:60]:60s}  {rc:>7} reviews{mark}")
print(f"  Scarlett's in top 20? {found}")

# Check if cell would even be searched: distance from base hex cell center to Miami center
print()
print("=" * 70)
print("STEP 6: Would this H3 cell be in the search grid?")
print("=" * 70)
center_cell = h3.latlng_to_cell(MIAMI_LAT, MIAMI_LNG, H3_RESOLUTION)
k = math.ceil(RADIUS / edge_m)
grid = list(h3.grid_disk(center_cell, k))
print(f"  Grid: k={k}, {len(grid)} cells from center")
print(f"  Cell in grid? {cell in grid}")

print()
print("=" * 70)
print("STEP 7: Was the parent cell dense? (would be subdivided)")
print("=" * 70)
if cell in grid:
    parent_results = nearby_search(cell_lat, cell_lng, edge_m, excluded=True)
    sorted_p = sorted(parent_results, key=lambda p: p.get("userRatingCount") or 0, reverse=True)
    if len(sorted_p) >= 15:
        kth = sorted_p[14]
        print(f"  15th place: {kth.get('displayName', {}).get('text', '')} - {kth.get('userRatingCount')} reviews")
        kth_count = kth.get("userRatingCount") or 0
        is_dense = len(sorted_p) >= 20 and kth_count > 500
        print(f"  Dense cell? {is_dense}")
        if is_dense:
            print(f"  -> Would be subdivided to res 8")
            child_cell = h3.latlng_to_cell(plat, plng, H3_RESOLUTION + 1)
            cl, cln = h3.cell_to_latlng(child_cell)
            cedge = h3.average_hexagon_edge_length(H3_RESOLUTION + 1, unit="m")
            print(f"  Scarlett's in child cell {child_cell} at ({cl:.5f}, {cln:.5f})")
            child_results = nearby_search(cl, cln, cedge, excluded=True)
            sorted_c = sorted(child_results, key=lambda p: p.get("userRatingCount") or 0, reverse=True)
            found_c = any("Scarlett" in p.get("displayName", {}).get("text", "") for p in sorted_c)
            print(f"  Scarlett's in res 8 child cell? {found_c}")
            if not found_c:
                print(f"  Top 5 in child cell:")
                for i, p in enumerate(sorted_c[:5], 1):
                    print(f"    {i}. {p.get('displayName', {}).get('text', '')[:60]} - {p.get('userRatingCount') or 0} reviews")
                # Check res 9 (max subdivision)
                gc_cell = h3.latlng_to_cell(plat, plng, H3_RESOLUTION + 2)
                gcl, gcln = h3.cell_to_latlng(gc_cell)
                gcedge = h3.average_hexagon_edge_length(H3_RESOLUTION + 2, unit="m")
                gc_results = nearby_search(gcl, gcln, gcedge, excluded=True)
                gc_sorted = sorted(gc_results, key=lambda p: p.get("userRatingCount") or 0, reverse=True)
                found_gc = any("Scarlett" in p.get("displayName", {}).get("text", "") for p in gc_sorted)
                print(f"  Scarlett's in res 9 grandchild? {found_gc}")
                if not found_gc:
                    print(f"  Top 5 in grandchild cell:")
                    for i, p in enumerate(gc_sorted[:5], 1):
                        print(f"    {i}. {p.get('displayName', {}).get('text', '')[:60]} - {p.get('userRatingCount') or 0} reviews")

print()
print("=" * 70)
print("STEP 8: Try NearbySearch WITHOUT excludedPrimaryTypes filter")
print("=" * 70)
no_filter_results = nearby_search(cell_lat, cell_lng, edge_m, excluded=False)
no_f_sorted = sorted(no_filter_results, key=lambda p: p.get("userRatingCount") or 0, reverse=True)
found_nf = False
for i, p in enumerate(no_f_sorted, 1):
    name = p.get("displayName", {}).get("text", "")
    if "Scarlett" in name:
        found_nf = True
        rc = p.get("userRatingCount") or 0
        print(f"  Found at rank {i}: {name} - {rc} reviews")
        break
if not found_nf:
    print("  Not found even without the EXCLUDED_TYPES filter")
