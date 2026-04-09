"""
Most Popular Locations — Streamlit Frontend

Run from the project root:
    streamlit run frontend/app.py
"""

import json
import math
from pathlib import Path

import pandas as pd
import numpy as np
import plotly.express as px
import streamlit as st
import streamlit.components.v1 as components
import h3
from shapely.geometry import Point, Polygon, mapping
from shapely.ops import unary_union

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="Most Popular Locations",
    page_icon="📍",
    layout="wide",
)

CACHED_DIR = Path(__file__).parent.parent / "cached_cities"

# ── Named constants ──
US_CENTER_LAT = 39.8283   # geographic center of contiguous US
US_CENTER_LNG = -98.5795  # geographic center of contiguous US
DEFAULT_MAP_HEIGHT = 500
MAX_MAP_PLACES = 10_000
MAX_TYPES_SHOWN = 3
MAX_CHART_PLACES = 30
MAX_CHART_NAME_LEN = 45
MIN_CHART_HEIGHT = 350
CHART_PX_PER_BAR = 20
RATING_BENCHMARK = 4.5
DATAFRAME_HEIGHT = 400
H3_RESOLUTION = 7  # must match constants.py

# (min_reviews, label, [r, g, b], color_name)
TIERS = [
    (50_000, "50K+",       [255,  20,  20], "Red"),
    (20_000, "20K–50K",    [255,  90,   0], "Orange-Red"),
    (10_000, "10K–20K",    [255, 170,   0], "Orange"),
    ( 5_000, "5K–10K",     [255, 230,   0], "Yellow"),
    ( 2_000, "2K–5K",      [140, 230,   0], "Yellow-Green"),
    ( 1_000, "1K–2K",      [  0, 210,  80], "Green"),
    (   500, "500–1K",     [  0, 200, 210], "Cyan"),
    (   200, "200–500",    [ 30, 100, 255], "Blue"),
    (     0, "< 200",      [130, 130, 130], "Gray"),
]


def tier_color_css(review_count: int | None) -> str:
    """Return an rgb() CSS string for the tier color matching review_count."""
    review_count = review_count or 0
    for threshold, _, color, _ in TIERS:
        if review_count >= threshold:
            return f"rgb({color[0]},{color[1]},{color[2]})"
    return "rgb(180,180,180)"


def tier_label(review_count: int | None) -> str:
    """Return the human-readable tier label for a review count."""
    review_count = review_count or 0
    for threshold, label, _, _ in TIERS:
        if review_count >= threshold:
            return label
    return "< 200"


def star_rating(r: float | None) -> str:
    """Format a numeric rating as '★ X.X', or '—' if None."""
    if r is None:
        return "—"
    return f"★ {r:.1f}"


def h3_grid_boundary(center_lat: float, center_lng: float, radius_m: int) -> Polygon:
    """Return a Shapely polygon of the actual H3 grid used for searching."""
    center_cell = h3.latlng_to_cell(center_lat, center_lng, H3_RESOLUTION)
    cell_edge_m = h3.average_hexagon_edge_length(H3_RESOLUTION, unit="m")
    k = math.ceil(radius_m / cell_edge_m)
    cells = h3.grid_disk(center_cell, k)
    hex_polys = []
    for cell in cells:
        boundary = h3.cell_to_boundary(cell)
        hex_polys.append(Polygon([(lng, lat) for lat, lng in boundary]))
    return unary_union(hex_polys)


# ---------------------------------------------------------------------------
# Custom MapLibre component — initialises map ONCE, then updates GeoJSON
# sources in-place via postMessage.  No iframe recreation, no white flash.
#
# Highlight is computed *client-side* from a tiny list of selected names,
# avoiding the need to serialise and transfer the full GeoJSON on every
# table selection change.
# ---------------------------------------------------------------------------

_MAP_DIR = Path(__file__).parent / "components" / "map_component"
_map_component = components.declare_component("map_component", path=str(_MAP_DIR))

_TABLE_DIR = Path(__file__).parent / "components" / "table_component"
_table_component = components.declare_component("table_component", path=str(_TABLE_DIR))


def render_map(*, places_geojson, boundary_geojson, selected_names,
               center_lat, center_lng, zoom, view_revision, height=DEFAULT_MAP_HEIGHT, key=None):
    """Render the custom MapLibre component with the given GeoJSON and view state."""
    return _map_component(
        places_geojson=places_geojson,
        boundary_geojson=boundary_geojson,
        selected_names=selected_names,
        center_lat=center_lat,
        center_lng=center_lng,
        zoom=zoom,
        view_revision=view_revision,
        height=height,
        key=key,
        default=None,
    )


# ---------------------------------------------------------------------------
# GeoJSON helpers
# ---------------------------------------------------------------------------

_EMPTY_FC: dict = {"type": "FeatureCollection", "features": []}


def _places_to_geojson(places_list: list[dict]) -> dict:
    """Convert a list of place dicts to a GeoJSON FeatureCollection."""
    features = []
    for p in places_list:
        if not (p.get("lat") and p.get("lng")):
            continue
        rc = p.get("rating_count") or 0
        features.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [p["lng"], p["lat"]]},
            "properties": {
                "name": p.get("name", ""),
                "color": tier_color_css(rc),
                "rating_fmt": star_rating(p.get("rating")),
                "reviews_fmt": f"{rc:,}",
                "types_short": ", ".join((p.get("types") or [])[:MAX_TYPES_SHOWN]),
                "sort_key": rc,
            },
        })
    return {"type": "FeatureCollection", "features": features}


def _boundary_to_geojson(poly: Polygon | None) -> dict:
    """Convert a Shapely polygon to a GeoJSON FeatureCollection, or return empty."""
    if poly is None:
        return _EMPTY_FC
    return {
        "type": "FeatureCollection",
        "features": [{"type": "Feature", "geometry": mapping(poly), "properties": {}}],
    }


# ---------------------------------------------------------------------------
# Helper utilities
# ---------------------------------------------------------------------------

def rgb_to_hex(rgb: list[int]) -> str:
    """Convert [r, g, b] to '#rrggbb'."""
    return "#{:02x}{:02x}{:02x}".format(*rgb)


def calculate_map_center(city_metas: list[dict]) -> tuple[float, float]:
    """Return the average center of all cities, or the geographic center of the US."""
    lats = [m["center_lat"] for m in city_metas if m["center_lat"] is not None]
    lngs = [m["center_lng"] for m in city_metas if m["center_lng"] is not None]
    if lats:
        return sum(lats) / len(lats), sum(lngs) / len(lngs)
    return US_CENTER_LAT, US_CENTER_LNG


def calculate_zoom(latitudes: list[float], longitudes: list[float]) -> int:
    """Return an appropriate map zoom level based on the geographic spread of city centers."""
    if len(latitudes) <= 1:
        return 12  # neighborhood
    span = max(max(latitudes) - min(latitudes), max(longitudes) - min(longitudes))
    if span > 5:
        return 4   # continental
    if span > 2:
        return 5   # multi-state
    if span > 1:
        return 7   # state
    if span > 0.5:
        return 8   # metro
    if span > 0.1:
        return 10  # city
    return 12      # neighborhood


def render_selectable_table(*, rows, columns, selected_names,
                            height=DATAFRAME_HEIGHT, data_key="", key=None):
    """Render the custom clickable table. Returns list of selected place names."""
    return _table_component(
        rows=rows, columns=columns, selected_names=selected_names,
        height=height, data_key=data_key,
        key=key, default=None,
    )


def _sync_table_selection(table_key: str, filtered: list[dict]) -> list[str]:
    """
    Read the custom table component's selection from session state.

    The table component calls ``setComponentValue(names)`` on every click,
    which Streamlit stores under *table_key* before the next rerun starts.
    We read that stored value here—*before* the map renders—so the map
    highlight is always in sync with the table.
    """
    if "selected_place_names" not in st.session_state:
        st.session_state.selected_place_names = set()

    # The component stores its value under the key in session state.
    component_value = st.session_state.get(table_key)
    if isinstance(component_value, list):
        st.session_state.selected_place_names = set(component_value)

    # Prune names that disappeared after a filter change.
    current_names = {p.get("name", "") for p in filtered}
    st.session_state.selected_place_names &= current_names

    return list(st.session_state.selected_place_names)


def _render_rating_chart(filtered: list[dict]) -> None:
    """Render a Plotly horizontal bar chart of top places by rating and review count."""
    chart_places = [p for p in filtered if p.get("rating_count") and p.get("rating")]
    if not chart_places:
        return
    top_n = sorted(chart_places, key=lambda p: p.get("rating_count") or 0, reverse=True)[:MAX_CHART_PLACES]
    top_n = list(reversed(top_n))
    chart_df = pd.DataFrame([{
        "Name": p["name"][:MAX_CHART_NAME_LEN],
        "Reviews": int(p["rating_count"]),
        "Rating": float(p["rating"]),
        "Tier": tier_label(p["rating_count"]),
        "Reviews_fmt": f"{int(p['rating_count']):,}",
    } for p in top_n])

    tier_order = [t[1] for t in TIERS]
    tier_colors = {t[1]: "rgb({},{},{})".format(*t[2]) for t in TIERS}

    fig = px.bar(
        chart_df, x="Rating", y="Name", orientation="h",
        color="Tier", category_orders={"Tier": tier_order},
        color_discrete_map=tier_colors, hover_name="Name",
        hover_data={"Rating": ":.2f", "Reviews_fmt": True, "Tier": True, "Name": False},
        title=f"Top {len(top_n)} Places — Rating (color = popularity tier)",
    )
    fig.update_layout(
        height=max(MIN_CHART_HEIGHT, len(top_n) * CHART_PX_PER_BAR),
        margin={"l": 20, "r": 20, "t": 50, "b": 40},
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font_color="#ccc", legend_title_text="Review tier",
        xaxis_title="Rating", yaxis_title=None,
        xaxis=dict(range=[3.0, 5.1], gridcolor="#333", dtick=0.5),
        yaxis=dict(gridcolor="#333"), bargap=0.25,
    )
    fig.add_vline(x=RATING_BENCHMARK, line_dash="dot", line_color="#555",
                  annotation_text="4.5", annotation_font_color="#777")
    st.plotly_chart(fig, use_container_width=True)


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

@st.cache_data
def load_city(path: Path) -> dict:
    """Load and return a cached city JSON file."""
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def available_cities() -> dict[str, Path]:
    """Return a mapping of city name → JSON path for all cached cities."""
    return {p.stem: p for p in sorted(CACHED_DIR.glob("*.json"))}


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------

cities = available_cities()

st.sidebar.title("📍 Most Popular Locations")

if not cities:
    st.sidebar.error("No cached JSON files found in `cached_cities/`. Run `example.py` first.")
    st.stop()

default_city = "San Francisco" if "San Francisco" in cities else list(cities.keys())[0]
selected_cities = st.sidebar.multiselect(
    "Cities", list(cities.keys()), default=[default_city]
)

city_metas: list[dict] = []
_seen_names: dict[str, int] = {}
places: list[dict] = []
for city_name in selected_cities:
    data = load_city(cities[city_name])
    for p in data.get("places", []):
        name = p.get("name", "")
        if name in _seen_names:
            existing = places[_seen_names[name]]
            if (p.get("rating_count") or 0) > (existing.get("rating_count") or 0):
                places[_seen_names[name]] = p
        else:
            _seen_names[name] = len(places)
            places.append(p)
    city_metas.append({
        "name": city_name,
        "center_lat": data.get("center_lat"),
        "center_lng": data.get("center_lng"),
        "radius_meters": data.get("radius_meters"),
    })

if selected_cities:
    for meta in city_metas:
        radius = meta["radius_meters"]
        label = f"{radius:,} m" if isinstance(radius, int) else str(radius)
        st.sidebar.markdown(f"**{meta['name']}:** search radius {label}")
    st.sidebar.markdown(f"**Total places:** {len(places):,}")
    with_coords = [p for p in places if p.get("lat") and p.get("lng")]
    without_coords = len(places) - len(with_coords)
    st.sidebar.markdown(f"**With coordinates:** {len(with_coords):,}")
    if without_coords:
        st.sidebar.caption(f"{without_coords} places have no coordinates (run `example.py` again to collect them).")
else:
    with_coords = []

st.sidebar.markdown("---")
st.sidebar.markdown("**Map colour tiers**")
for _, label, color, _ in TIERS:
    hex_color = rgb_to_hex(color)
    st.sidebar.markdown(
        f'<span style="display:inline-block;width:12px;height:12px;border-radius:50%;'
        f'background:{hex_color};margin-right:6px;"></span>{label}',
        unsafe_allow_html=True,
    )

# ---------------------------------------------------------------------------
# Title
# ---------------------------------------------------------------------------

cities_label = ", ".join(selected_cities) if selected_cities else "No city selected"
st.subheader(f"Popular Places — {cities_label}")

# Pre-compute H3 boundary
h3_boundary_poly = None
if city_metas:
    parts = []
    for meta in city_metas:
        radius = meta["radius_meters"]
        if isinstance(radius, int) and meta["center_lat"] is not None:
            parts.append(h3_grid_boundary(meta["center_lat"], meta["center_lng"], radius))
    if parts:
        h3_boundary_poly = unary_union(parts)

# view_revision changes only when city selection changes → map flies to new center
view_revision = ",".join(sorted(selected_cities))

# Full-page rerun (city change, page load) → clear cached data key so the
# component receives the full GeoJSON on the first fragment render.
# Only clear when city selection *actually changes* — custom component
# setComponentValue triggers full reruns, and we must not resend ~1.4 MB
# of GeoJSON on every table row click.
_city_sig = ",".join(sorted(selected_cities))
if st.session_state.get("_city_sig") != _city_sig:
    st.session_state._city_sig = _city_sig
    st.session_state.pop("_map_filter_key", None)

# ---------------------------------------------------------------------------
# Map + Explorer
#
# @st.fragment keeps filter / table interactions scoped to this section.
# The custom MapLibre component never recreates the map; it only calls
# source.setData() on existing GeoJSON sources.
#
# Perf: on selection-only reruns the filter key is unchanged, so we send
# places_geojson=None and boundary_geojson=None.  The JS side skips the
# heavy source update and only recomputes the highlight from the tiny
# selected_names list (~a few strings vs ~1.4 MB of GeoJSON).
# ---------------------------------------------------------------------------

@st.fragment
def render_explorer():
    """Render the interactive map, filter controls, data table, and rating chart."""
    # ── Empty-data fallback ──
    if not with_coords:
        render_map(
            places_geojson=_EMPTY_FC, boundary_geojson=_EMPTY_FC,
            selected_names=[], center_lat=US_CENTER_LAT, center_lng=US_CENTER_LNG,
            zoom=3, view_revision="empty", height=DEFAULT_MAP_HEIGHT, key="main_map",
        )
        if not selected_cities:
            st.info("Select one or more cities from the sidebar to see places on the map.")
        else:
            st.warning("No coordinate data found. Run `example.py` to collect lat/lng.")
        return

    # ── Filters ──
    all_review_counts = sorted(int(p.get("rating_count") or 0) for p in places)
    all_review_max = all_review_counts[-1] if all_review_counts else 1000
    median_reviews = all_review_counts[len(all_review_counts) // 2] if all_review_counts else 0
    all_types = sorted({t for p in places for t in (p.get("types") or [])})

    search_query = st.text_input("Search by name", placeholder="e.g. park, museum, cafe...")
    col_min, col_types = st.columns([1, 2])
    with col_min:
        log_options = [0] + sorted(set(int(v) for v in np.geomspace(1, all_review_max, num=300)))
        default_min = min(log_options, key=lambda x: abs(x - median_reviews))
        min_reviews = st.select_slider(
            "Min reviews", options=log_options, value=default_min,
            format_func=lambda x: f"{x:,}",
        )
    selected_types = col_types.multiselect("Filter by type", all_types, placeholder="All types")
    only_in_boundary = st.checkbox("Within boundary only", value=False)

    # Apply filters
    filtered = list(places)
    if search_query:
        query_lower = search_query.lower()
        filtered = [p for p in filtered if query_lower in (p.get("name") or "").lower()]
    if selected_types:
        type_set = set(selected_types)
        filtered = [p for p in filtered if type_set.intersection(p.get("types") or [])]
    filtered = [p for p in filtered if (p.get("rating_count") or 0) >= min_reviews]
    if only_in_boundary and h3_boundary_poly is not None:
        filtered = [
            p for p in filtered
            if p.get("lat") and p.get("lng")
            and h3_boundary_poly.contains(Point(p["lng"], p["lat"]))
        ]

    # Sort once — shared by the table and the index→name mapping below.
    filtered = sorted(filtered, key=lambda p: p.get("rating_count") or 0, reverse=True)

    # ── Data-change detection ──
    filter_key = (min_reviews, tuple(sorted(selected_types)), search_query, only_in_boundary)
    data_changed = st.session_state.get("_map_filter_key") != filter_key

    filtered_with_coords = [p for p in filtered if p.get("lat") and p.get("lng")]
    capped = filtered_with_coords
    if len(capped) > MAX_MAP_PLACES:
        st.warning(
            f"Showing top {MAX_MAP_PLACES:,} of {len(capped):,} places. "
            f"Raise **Min reviews** to narrow further."
        )
        capped = capped[:MAX_MAP_PLACES]

    if data_changed:
        st.session_state._map_filter_key = filter_key
        st.session_state._cached_places_gj = _places_to_geojson(capped)
        st.session_state._cached_boundary_gj = _boundary_to_geojson(h3_boundary_poly)

    # ── Map ──
    meta_lats = [m["center_lat"] for m in city_metas if m["center_lat"] is not None]
    meta_lngs = [m["center_lng"] for m in city_metas if m["center_lng"] is not None]
    center_lat, center_lng = calculate_map_center(city_metas)
    zoom = calculate_zoom(meta_lats, meta_lngs)

    # Read table-component selection *before* the map so highlights are in sync.
    table_key = f"explorer_{hash(filter_key)}"
    selected_names = _sync_table_selection(table_key, filtered)

    render_map(
        places_geojson=st.session_state.get("_cached_places_gj") if data_changed else None,
        boundary_geojson=st.session_state.get("_cached_boundary_gj") if data_changed else None,
        selected_names=selected_names,
        center_lat=center_lat, center_lng=center_lng, zoom=zoom,
        view_revision=view_revision, height=DEFAULT_MAP_HEIGHT, key="main_map",
    )

    # ── Explorer table ──
    st.markdown("---")

    if not filtered:
        st.info("No places match the current filters.")
    else:
        # Selection feedback — show which places are highlighted.
        sel_set = st.session_state.get("selected_place_names", set())
        if sel_set:
            col_info, col_clear = st.columns([5, 1])
            names_preview = ", ".join(sorted(sel_set)[:5])
            more = f" +{len(sel_set) - 5} more" if len(sel_set) > 5 else ""
            col_info.caption(f"📍 **{len(sel_set)}** highlighted: {names_preview}{more}")
            if col_clear.button("Clear", type="secondary", key="clear_sel"):
                st.session_state.selected_place_names.clear()
                st.rerun(scope="fragment")
        else:
            st.caption("_Click any row to highlight it on the map_")

        rows = []
        for rank, p in enumerate(filtered, 1):
            rc = p.get("rating_count") or 0
            rows.append({
                "__name": p.get("name", "—"),
                "Rank": rank,
                "Name": p.get("name", "—"),
                "Rating": star_rating(p.get("rating")),
                "Reviews": f"{rc:,}" if rc else "—",
                "Types": ", ".join((p.get("types") or [])[:MAX_TYPES_SHOWN]),
            })
        render_selectable_table(
            rows=rows,
            columns=["Rank", "Name", "Rating", "Reviews", "Types"],
            selected_names=selected_names,
            height=DATAFRAME_HEIGHT,
            data_key=str(filter_key),
            key=table_key,
        )

        # ── Rating chart ──
        st.markdown("---")
        _render_rating_chart(filtered)


render_explorer()
