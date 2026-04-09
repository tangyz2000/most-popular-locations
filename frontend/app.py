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
    rc = review_count or 0
    for threshold, _, color, _ in TIERS:
        if rc >= threshold:
            return f"rgb({color[0]},{color[1]},{color[2]})"
    return "rgb(180,180,180)"


def tier_label(review_count: int | None) -> str:
    rc = review_count or 0
    for threshold, label, _, _ in TIERS:
        if rc >= threshold:
            return label
    return "< 500"


def star_rating(r: float | None) -> str:
    if r is None:
        return "—"
    return f"★ {r:.1f}"


MAX_MAP_PLACES = 10_000
H3_RESOLUTION = 7  # must match constants.py


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


def render_map(*, places_geojson, boundary_geojson, selected_names,
               center_lat, center_lng, zoom, view_revision, height=620, key=None):
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
                "types_short": ", ".join((p.get("types") or [])[:3]),
                "sort_key": rc,
            },
        })
    return {"type": "FeatureCollection", "features": features}


def _boundary_to_geojson(poly) -> dict:
    if poly is None:
        return _EMPTY_FC
    return {
        "type": "FeatureCollection",
        "features": [{"type": "Feature", "geometry": mapping(poly), "properties": {}}],
    }


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

@st.cache_data
def load_city(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def available_cities() -> dict[str, Path]:
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
        r = meta["radius_meters"]
        label = f"{r:,} m" if isinstance(r, int) else str(r)
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
    hex_color = "#{:02x}{:02x}{:02x}".format(*color)
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
_h3_boundary_poly = None
if city_metas:
    parts = []
    for meta in city_metas:
        r = meta["radius_meters"]
        if isinstance(r, int) and meta["center_lat"] is not None:
            parts.append(h3_grid_boundary(meta["center_lat"], meta["center_lng"], r))
    if parts:
        _h3_boundary_poly = unary_union(parts)

# view_revision changes only when city selection changes → map flies to new center
_view_revision = ",".join(sorted(selected_cities))

# Full-page rerun (city change, page load) → clear cached data key so the
# component receives the full GeoJSON on the first fragment render.
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
    # ------------------------------------------------------------------
    # Empty-data fallback
    # ------------------------------------------------------------------
    if not with_coords:
        render_map(
            places_geojson=_EMPTY_FC, boundary_geojson=_EMPTY_FC,
            selected_names=[], center_lat=39.8283, center_lng=-98.5795,
            zoom=3, view_revision="empty", height=620, key="main_map",
        )
        if not selected_cities:
            st.info("Select one or more cities from the sidebar to see places on the map.")
        else:
            st.warning("No coordinate data found. Run `example.py` to collect lat/lng.")
        return

    # ------------------------------------------------------------------
    # Filters
    # ------------------------------------------------------------------
    all_review_counts = sorted(int(p.get("rating_count") or 0) for p in places)
    all_review_max = all_review_counts[-1] if all_review_counts else 1000
    median_reviews = all_review_counts[len(all_review_counts) // 2] if all_review_counts else 0
    all_types = sorted({t for p in places for t in (p.get("types") or [])})

    col_search, col_min, col_types = st.columns([2, 1, 3])
    search_query = col_search.text_input("Search by name", placeholder="e.g. park, museum, cafe...")
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
        q = search_query.lower()
        filtered = [p for p in filtered if q in (p.get("name") or "").lower()]
    if selected_types:
        selected_set = set(selected_types)
        filtered = [p for p in filtered if selected_set.intersection(p.get("types") or [])]
    filtered = [p for p in filtered if (p.get("rating_count") or 0) >= min_reviews]
    if only_in_boundary and _h3_boundary_poly is not None:
        filtered = [
            p for p in filtered
            if p.get("lat") and p.get("lng")
            and _h3_boundary_poly.contains(Point(p["lng"], p["lat"]))
        ]

    # Sort once — shared by the table and the index→name mapping below.
    filtered = sorted(filtered, key=lambda p: p.get("rating_count") or 0, reverse=True)

    # ------------------------------------------------------------------
    # Determine whether the *data* changed (filter tweak / city switch)
    # vs. only the table selection changed.
    # ------------------------------------------------------------------
    _filter_key = (min_reviews, tuple(sorted(selected_types)), search_query, only_in_boundary)
    _data_changed = st.session_state.get("_map_filter_key") != _filter_key

    filtered_with_coords = [p for p in filtered if p.get("lat") and p.get("lng")]
    capped = filtered_with_coords
    if len(capped) > MAX_MAP_PLACES:
        st.warning(
            f"Showing top {MAX_MAP_PLACES:,} of {len(capped):,} places. "
            f"Raise **Min reviews** to narrow further."
        )
        capped = sorted(capped, key=lambda p: p.get("rating_count") or 0, reverse=True)[:MAX_MAP_PLACES]

    if _data_changed:
        st.session_state._map_filter_key = _filter_key
        st.session_state._cached_places_gj = _places_to_geojson(capped)
        st.session_state._cached_boundary_gj = _boundary_to_geojson(_h3_boundary_poly)

    # ------------------------------------------------------------------
    # Read table selection from widget state *before* rendering the map
    # so we can show the correct highlight in a single pass (no double
    # rerun).  The key changes when filters change, which auto-clears
    # stale row indices that would otherwise point to wrong rows.
    # ------------------------------------------------------------------
    _table_key = f"explorer_{hash(_filter_key)}"
    _table_state = st.session_state.get(_table_key)
    try:
        _sel_rows = _table_state.selection.rows if _table_state else []
    except AttributeError:
        _sel_rows = []
    selected_names = [
        filtered[i].get("name", "")
        for i in _sel_rows
        if i < len(filtered)
    ]

    # ------------------------------------------------------------------
    # Map
    # ------------------------------------------------------------------
    meta_lats = [m["center_lat"] for m in city_metas if m["center_lat"] is not None]
    meta_lngs = [m["center_lng"] for m in city_metas if m["center_lng"] is not None]
    if meta_lats:
        center_lat = sum(meta_lats) / len(meta_lats)
        center_lng = sum(meta_lngs) / len(meta_lngs)
    else:
        center_lat, center_lng = 39.8283, -98.5795

    if len(meta_lats) > 1:
        span = max(max(meta_lats) - min(meta_lats), max(meta_lngs) - min(meta_lngs))
        zoom = 4 if span > 5 else 5 if span > 2 else 7 if span > 1 else 8 if span > 0.5 else 10 if span > 0.1 else 12
    else:
        zoom = 12

    render_map(
        places_geojson=st.session_state.get("_cached_places_gj") if _data_changed else None,
        boundary_geojson=st.session_state.get("_cached_boundary_gj") if _data_changed else None,
        selected_names=selected_names,
        center_lat=center_lat, center_lng=center_lng, zoom=zoom,
        view_revision=_view_revision, height=620, key="main_map",
    )

    # ------------------------------------------------------------------
    # Explorer table
    # ------------------------------------------------------------------
    st.markdown("---")

    if not filtered:
        st.info("No places match the current filters.")
    else:
        rows = []
        for rank, p in enumerate(filtered, 1):
            rc = p.get("rating_count") or 0
            rows.append({
                "Rank": rank,
                "Name": p.get("name", "—"),
                "Rating": star_rating(p.get("rating")),
                "Reviews": f"{rc:,}" if rc else "—",
                "Types": ", ".join((p.get("types") or [])[:3]),
            })
        df = pd.DataFrame(rows)
        st.dataframe(
            df, use_container_width=True, hide_index=True,
            height=500, on_select="rerun", selection_mode="multi-row",
            key=_table_key,
        )

        # Rating bar chart
        st.markdown("---")
        chart_places = [p for p in filtered if p.get("rating_count") and p.get("rating")]
        if chart_places:
            top_n = sorted(chart_places, key=lambda p: p.get("rating_count") or 0, reverse=True)[:40]
            top_n = list(reversed(top_n))
            chart_df = pd.DataFrame([{
                "Name": p["name"][:45],
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
                height=max(400, len(top_n) * 22),
                margin={"l": 20, "r": 20, "t": 50, "b": 40},
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                font_color="#ccc", legend_title_text="Review tier",
                xaxis_title="Rating", yaxis_title=None,
                xaxis=dict(range=[3.0, 5.1], gridcolor="#333", dtick=0.5),
                yaxis=dict(gridcolor="#333"), bargap=0.25,
            )
            fig.add_vline(x=4.5, line_dash="dot", line_color="#555",
                          annotation_text="4.5", annotation_font_color="#777")
            st.plotly_chart(fig, use_container_width=True)


render_explorer()
