"""
Appends one record to search_quality.log after each example.py run.

Log format (fixed-width columns, one row per run):
    Timestamp            City                       Radius    Score   Q500+  Q1K+  Q5K+    p90
    2026-04-04 10:23:15  San Francisco               8,000   2970.7    950   539    61   3,913
"""

import math
from datetime import datetime
from pathlib import Path

LOG_FILE = Path("logs/search_quality.log")
MIN_REVIEWS = 500

# Fixed-width column layout
_HEADER = (
    f"{'Timestamp':<20} {'City':<26} {'Radius':>7}  "
    f"{'Score':>7}  {'Q100+':>5}  {'Q500+':>5}  {'Q1K+':>5}  {'Q5K+':>5}  {'p90':>7}"
)
_SEP = "-" * len(_HEADER)


def _compute(places: list[dict]) -> dict:
    counts = [p.get("rating_count") or 0 for p in places]
    qualifying = sorted([c for c in counts if c >= MIN_REVIEWS])
    if not qualifying:
        return {"score": 0.0, "q100": 0, "q500": 0, "q1k": 0, "q5k": 0, "p90": 0}

    q100 = sum(1 for c in counts if c >= 100)
    p90_idx = max(0, int(len(qualifying) * 0.90) - 1)
    return {
        "score": sum(math.log10(c) for c in qualifying),
        "q100": q100,
        "q500": len(qualifying),
        "q1k":  sum(1 for c in qualifying if c >= 1_000),
        "q5k":  sum(1 for c in qualifying if c >= 5_000),
        "p90":  qualifying[p90_idx],
    }


def record(city: str, radius_meters: int, places: list[dict]) -> None:
    m = _compute(places)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    row = (
        f"{timestamp:<20} {city:<26} {radius_meters:>7,}  "
        f"{m['score']:>7.1f}  {m['q100']:>5,}  {m['q500']:>5,}  {m['q1k']:>5,}  {m['q5k']:>5,}  {m['p90']:>7,}"
    )

    # Write header if file is new/empty, then append the row.
    is_new = not LOG_FILE.exists() or LOG_FILE.stat().st_size == 0
    with LOG_FILE.open("a", encoding="utf-8") as f:
        if is_new:
            f.write(_HEADER + "\n")
            f.write(_SEP + "\n")
        f.write(row + "\n")

    print(f"[SearchLog] {row}")
