import functools

from constants import TRACKED_APIS

# Pre-initialise every known API to 0 so they always appear in the summary.
_counts: dict[str, int] = {api: 0 for api in set(TRACKED_APIS.values())}


def track(fn):
    """Decorator — records one call to the API mapped to this function in TRACKED_APIS."""
    api = TRACKED_APIS.get(fn.__name__, fn.__name__)
    if api not in _counts:
        _counts[api] = 0

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        _counts[api] += 1
        return fn(*args, **kwargs)

    return wrapper


def print_stats() -> None:
    print("\n--- API call statistics ---")
    for api, count in sorted(_counts.items()):
        print(f"  {api}: {count}")
    print(f"  Total: {sum(_counts.values())}")
    print("---------------------------\n")


def reset() -> None:
    for key in _counts:
        _counts[key] = 0
