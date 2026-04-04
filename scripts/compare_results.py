"""
compare_results.py  —  compare two cached-city result files.

Usage:
    python scripts/compare_results.py <file_a> <file_b> [min_reviews]

Only places with review count >= MIN_REVIEWS (default: 500) are compared.

Prints:
    - Places that appear in A but not in B
    - Places that appear in B but not in A
Matching is done by place name (case-insensitive).
"""

import re
import sys
from pathlib import Path

MIN_REVIEWS = 500


def parse_places(path: Path) -> dict[str, dict]:
    """Return {normalised_name: {name, address, rating, review_count}} from a results file."""
    places: dict[str, dict] = {}
    current: dict | None = None

    for line in path.read_text(encoding="utf-8").splitlines():
        # Numbered entry header: "42. Some Place Name"
        m = re.match(r"^\d+\.\s+(.+)$", line)
        if m:
            current = {"name": m.group(1).strip()}
            places[current["name"].lower()] = current
            continue

        if current is None:
            continue

        m = re.match(r"^\s+Address:\s+(.+)$", line)
        if m:
            current["address"] = m.group(1).strip()
            continue

        # "Rating:   4.8 (85533 reviews)"
        m = re.match(r"^\s+Rating:\s+([\d.]+|N/A)\s+\((\d+) reviews\)$", line)
        if m:
            current["rating"] = m.group(1)
            current["review_count"] = int(m.group(2))
            continue

    return places


def filter_by_reviews(places: dict[str, dict], min_reviews: int) -> dict[str, dict]:
    return {k: v for k, v in places.items() if v.get("review_count", 0) >= min_reviews}


def only_in(a: dict[str, dict], b: dict[str, dict]) -> list[dict]:
    return sorted(
        [v for k, v in a.items() if k not in b],
        key=lambda p: p.get("review_count", 0),
        reverse=True,
    )


def main() -> None:
    if len(sys.argv) < 3:
        print("Usage: python scripts/compare_results.py <file_a> <file_b> [min_reviews]")
        sys.exit(1)

    path_a, path_b = Path(sys.argv[1]), Path(sys.argv[2])
    min_reviews = int(sys.argv[3]) if len(sys.argv) > 3 else MIN_REVIEWS

    for p in (path_a, path_b):
        if not p.exists():
            print(f"Error: file not found: {p}")
            sys.exit(1)

    all_a = parse_places(path_a)
    all_b = parse_places(path_b)

    places_a = filter_by_reviews(all_a, min_reviews)
    places_b = filter_by_reviews(all_b, min_reviews)

    in_a_not_b = only_in(places_a, places_b)
    in_b_not_a = only_in(places_b, places_a)

    print(f"File A: {path_a.name}  ({len(all_a)} total, {len(places_a)} with >={min_reviews} reviews)")
    print(f"File B: {path_b.name}  ({len(all_b)} total, {len(places_b)} with >={min_reviews} reviews)")
    print(f"Min reviews filter: {min_reviews}")
    print()

    print(f"--- In A but not B ({len(in_a_not_b)}) ---")
    for p in in_a_not_b:
        print(f"  {p['name']}  ({p.get('review_count', '?')} reviews, rated {p.get('rating', 'N/A')})")
        print(f"    {p.get('address', 'N/A')}")
    if not in_a_not_b:
        print("  (none)")

    print()
    print(f"--- In B but not A ({len(in_b_not_a)}) ---")
    for p in in_b_not_a:
        print(f"  {p['name']}  ({p.get('review_count', '?')} reviews, rated {p.get('rating', 'N/A')})")
        print(f"    {p.get('address', 'N/A')}")
    if not in_b_not_a:
        print("  (none)")


if __name__ == "__main__":
    main()
