# Most Popular Locations

This project discovers and ranks popular places in any city using the Google Places API, with review count as a proxy for real-world foot traffic. A review is a small act, but thousands of them reveal where the world actually goes. A place with 10K reviews has been visited far more than one with 1K.

## Quick Start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Create a `.env` file with your Google Places API key:

```
GOOGLE_PLACES_API_KEY=your_key_here
```

Run a search:

```bash
python example.py
```

Edit `example.py` to change the city and radius:

```python
city = "San Francisco"
radius_meters = 8000
```

Results are written to `results.txt` and cached in `cached_cities/`.

## Frontend

A Streamlit dashboard for exploring results:

```bash
streamlit run frontend/app.py --server.headless true
```

- **Map tab** — places plotted on a dark map, colored by review-count tier, with search radius overlay
- **Explorer tab** — searchable/filterable table with bar chart of top places by rating

## API Cost

Google Places API provides 1,000 free calls/month. Each NearbySearch call returns up to 20 places.

| City | Radius | NearbySearch calls | TextSearch calls | Places found |
|------|--------|--------------------|------------------|--------------|
| Sunnyvale | 4 km | ~174 | ~13 | ~2,000 |
| San Francisco | 8 km | ~600 | ~40 | ~7,000 |

Type sweeps triple the NearbySearch calls per leaf cell (generic + 3 type groups), but only fire at leaf nodes of the subdivision tree to avoid redundant queries.

## Project Structure

```
example.py                 # Entry point — configure city/radius here
constants.py               # API keys, H3 resolution, type sweep groups, thresholds
sources/
  GoogleMapsAPI_nearby_search.py   # H3 grid search + type sweeps + dense subdivision
  GoogleMapsAPI_text_search.py     # Text search across nearby city centers
api_stats.py               # Tracks API call counts per run
search_log.py              # Appends quality metrics to logs/search_quality.log
frontend/app.py            # Streamlit dashboard
scripts/                   # Utility scripts (comparison, backfill, visualization)
cached_cities/             # Cached results (.txt and .json per city)
logs/search_quality.log    # Historical search quality metrics across runs
```

## How It Works

1. **Geocode** the city name to coordinates
2. **NearbySearch** covers the area with an [H3 hex grid](https://h3geo.org/), querying Google Places at each cell center ranked by popularity
3. **Type sweeps** run additional queries per cell for culture/landmarks, outdoor/recreation, and food/drink — so popular parks and museums aren't crowded out by restaurants in the generic ranking
4. **Dense-area subdivision** detects saturated cells (where the 15th result still has 500+ reviews) and recursively subdivides them into finer hexagons for deeper coverage
5. **TextSearch** queries nearby city centers for "landmarks and tourist attractions" to catch additional places
6. Results are **deduplicated** by Place ID, tagged with which sources found them, and ranked by review count

## License

MIT
