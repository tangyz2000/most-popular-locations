"""Quick script to look up a place by name and print its full types list."""
import httpx
from constants import API_KEY, TEXT_SEARCH_URL, PLACE_FIELD_MASK

query = "La Mar Cocina Peruana San Francisco"

response = httpx.post(
    TEXT_SEARCH_URL,
    json={"textQuery": query, "maxResultCount": 1},
    headers={
        "Content-Type": "application/json",
        "X-Goog-Api-Key": API_KEY,
        "X-Goog-FieldMask": PLACE_FIELD_MASK,
    },
)
response.raise_for_status()
places = response.json().get("places", [])

if not places:
    print("No results found.")
else:
    p = places[0]
    print(f"Name:          {p.get('displayName', {}).get('text')}")
    print(f"Address:       {p.get('formattedAddress')}")
    print(f"Rating:        {p.get('rating')} ({p.get('userRatingCount')} reviews)")
    print(f"Types:         {p.get('types')}")
