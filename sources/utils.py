import time

import httpx


def post_with_retry(
    url: str, *, json: dict, headers: dict, label: str, max_attempts: int = 3
) -> httpx.Response:
    """POST with retries on HTTP 5xx and transport errors (timeouts, connection drops).

    Caller is still responsible for raise_for_status() on the returned response.
    """
    last_exc: Exception | None = None
    response: httpx.Response | None = None
    for attempt in range(max_attempts):
        try:
            response = httpx.post(url, json=json, headers=headers)
        except httpx.TransportError as exc:
            last_exc = exc
            print(f"[{label}] transport error (attempt {attempt + 1}): {type(exc).__name__}: {exc}")
            if attempt + 1 < max_attempts:
                time.sleep(2 ** attempt)
            continue
        if response.status_code < 500:
            return response
        print(f"[{label}] {response.status_code} error (attempt {attempt + 1}): {response.text[:200]}")
        if attempt + 1 < max_attempts:
            time.sleep(2 ** attempt)
    if response is not None:
        return response
    assert last_exc is not None
    raise last_exc


def normalize(place: dict) -> dict:
    location = place.get("location", {})
    return {
        "id": place.get("id", ""),
        "name": place.get("displayName", {}).get("text", ""),
        "address": place.get("formattedAddress", ""),
        "rating": place.get("rating"),
        "rating_count": place.get("userRatingCount"),
        "types": place.get("types", []),
        "primary_type": place.get("primaryType", ""),
        "lat": location.get("latitude"),
        "lng": location.get("longitude"),
    }
