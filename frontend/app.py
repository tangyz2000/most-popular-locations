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
import pydeck as pdk
import streamlit as st
import h3
from shapely.geometry import Polygon
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


def tier_color(review_count: int | None) -> list[int]:
    rc = review_count or 0
    for threshold, _, color, _ in TIERS:
        if rc >= threshold:
            return color
    return [180, 180, 180]


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


MAX_MAP_PLACES = 10_000  # pydeck ScatterplotLayer cap for smooth rendering


H3_RESOLUTION = 7  # must match constants.py


def h3_grid_boundary(center_lat: float, center_lng: float, radius_m: int) -> Polygon:
    """Return a Shapely polygon of the actual H3 grid used for searching."""
    center_cell = h3.latlng_to_cell(center_lat, center_lng, H3_RESOLUTION)
    cell_edge_m = h3.average_hexagon_edge_length(H3_RESOLUTION, unit="m")
    k = math.ceil(radius_m / cell_edge_m)
    cells = h3.grid_disk(center_cell, k)
    # Union all hex cell polygons into one boundary
    hex_polys = []
    for cell in cells:
        boundary = h3.cell_to_boundary(cell)  # list of (lat, lng) tuples
        # Shapely uses (lng, lat) ordering
        hex_polys.append(Polygon([(lng, lat) for lat, lng in boundary]))
    return unary_union(hex_polys)


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

@st.cache_data
def load_city(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def available_cities() -> dict[str, Path]:
    """Return {display_name: path} for all cached JSON files."""
    return {p.stem: p for p in sorted(CACHED_DIR.glob("*.json"))}


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------

cities = available_cities()

st.sidebar.title("📍 Most Popular Locations")

if not cities:
    st.sidebar.error("No cached JSON files found in `cached_cities/`. Run `example.py` first.")
    st.stop()

selected_cities = st.sidebar.multiselect(
    "Cities", list(cities.keys()), default=[list(cities.keys())[0]]
)

# Load and merge data from all selected cities, deduplicating by name
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

# Map legend
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
# Map
# ---------------------------------------------------------------------------

cities_label = ", ".join(selected_cities) if selected_cities else "No city selected"
st.subheader(f"Popular Places — {cities_label}")

# ---------------------------------------------------------------------------
# Unified filters
# ---------------------------------------------------------------------------

# Pre-compute merged H3 boundary for spatial filtering
_h3_boundary_poly = None
if city_metas:
    _boundary_parts = []
    for meta in city_metas:
        r = meta["radius_meters"]
        if isinstance(r, int) and meta["center_lat"] is not None:
            _boundary_parts.append(
                h3_grid_boundary(meta["center_lat"], meta["center_lng"], r)
            )
    if _boundary_parts:
        _h3_boundary_poly = unary_union(_boundary_parts)

if with_coords:
    all_review_counts = sorted(int(p.get("rating_count") or 0) for p in places)
    all_review_max = all_review_counts[-1] if all_review_counts else 1000
    median_reviews = all_review_counts[len(all_review_counts) // 2] if all_review_counts else 0
    all_types = sorted({t for p in places for t in (p.get("types") or [])})

    col_search, col_min, col_types = st.columns([2, 1, 3])

    search_query = col_search.text_input("Search by name", placeholder="e.g. park, museum, cafe...")

    with col_min:
        log_options = [0] + sorted(set(
            int(v) for v in np.geomspace(1, all_review_max, num=300)
        ))
        # Default to median review count
        default_min = min(log_options, key=lambda x: abs(x - median_reviews))
        min_reviews = st.select_slider(
            "Min reviews",
            options=log_options,
            value=default_min,
            format_func=lambda x: f"{x:,}",
        )

    selected_types = col_types.multiselect(
        "Filter by type",
        all_types,
        placeholder="All types",
    )

    only_in_boundary = st.checkbox("Within boundary only", value=False)

    # Apply filters once — used by both map and table
    filtered = places
    if search_query:
        q = search_query.lower()
        filtered = [p for p in filtered if q in (p.get("name") or "").lower()]
    if selected_types:
        selected_set = set(selected_types)
        filtered = [p for p in filtered if selected_set.intersection(p.get("types") or [])]
    filtered = [p for p in filtered if (p.get("rating_count") or 0) >= min_reviews]
    if only_in_boundary and _h3_boundary_poly is not None:
        from shapely.geometry import Point
        filtered = [
            p for p in filtered
            if p.get("lat") and p.get("lng")
            and _h3_boundary_poly.contains(Point(p["lng"], p["lat"]))
        ]

# ---------------------------------------------------------------------------
# Map
# ---------------------------------------------------------------------------

# Reserve a placeholder so the map can be rendered after the table selection
map_container = st.empty()

if not with_coords:
    # Show an empty map when no cities are selected
    with map_container:
        view = pdk.ViewState(latitude=39.8283, longitude=-98.5795, zoom=3, pitch=0)
        st.pydeck_chart(
            pdk.Deck(
                layers=[],
                initial_view_state=view,
                map_style="https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json",
            ),
            use_container_width=True,
            height=620,
        )
    if not selected_cities:
        st.info("Select one or more cities from the sidebar to see places on the map.")
    else:
        st.warning("No coordinate data found. Run `example.py` to collect lat/lng.")
else:
    filtered_with_coords = [p for p in filtered if p.get("lat") and p.get("lng")]
    df_map = pd.DataFrame(filtered_with_coords) if filtered_with_coords else pd.DataFrame()

    if not df_map.empty:
        df_map["rating_count"] = pd.to_numeric(df_map["rating_count"], errors="coerce").fillna(0).astype(int)

        # Sort ascending so popular places are drawn last (on top)
        df_map = df_map.sort_values("rating_count", ascending=True).reset_index(drop=True)

        df_map["color"]       = df_map["rating_count"].apply(tier_color)
        df_map["tier"]        = df_map["rating_count"].apply(tier_label)
        df_map["reviews_fmt"] = df_map["rating_count"].apply(
            lambda rc: f"{rc:,}" if rc else "—"
        )
        df_map["types_short"] = df_map["types"].apply(
            lambda ts: ", ".join(ts[:3]) if ts else "—"
        )
        df_map["rating_fmt"]  = df_map["rating"].apply(star_rating)

    # Compute map center from all selected cities
    meta_lats = [m["center_lat"] for m in city_metas if m["center_lat"] is not None]
    meta_lngs = [m["center_lng"] for m in city_metas if m["center_lng"] is not None]
    if meta_lats:
        center_lat = sum(meta_lats) / len(meta_lats)
        center_lng = sum(meta_lngs) / len(meta_lngs)
    else:
        center_lat = df_map["lat"].median() if not df_map.empty else 39.8283
        center_lng = df_map["lng"].median() if not df_map.empty else -98.5795

    # Performance cap — keep map responsive
    if not df_map.empty and len(df_map) > MAX_MAP_PLACES:
        st.warning(
            f"Showing top {MAX_MAP_PLACES:,} places by reviews "
            f"(out of {len(df_map):,}). Raise the **Min reviews** "
            f"slider or filter by type to narrow further."
        )
        df_map = df_map.nlargest(MAX_MAP_PLACES, "rating_count")

    layers = []

    if not df_map.empty:
        layers.append(pdk.Layer(
            "ScatterplotLayer",
            data=df_map,
            get_position="[lng, lat]",
            get_fill_color="color",
            get_radius=50,
            radius_min_pixels=2.5,
            radius_max_pixels=2.5,
            pickable=True,
            opacity=0.85,
        ))

    # Render pre-computed H3 boundary
    if _h3_boundary_poly is not None:
        polys = _h3_boundary_poly.geoms if _h3_boundary_poly.geom_type == "MultiPolygon" else [_h3_boundary_poly]
        boundary_data = [
            {"polygon": [list(coord) for coord in poly.exterior.coords]}
            for poly in polys
        ]
        layers.append(pdk.Layer(
            "PolygonLayer",
            data=boundary_data,
            get_polygon="polygon",
            get_line_color=[255, 255, 255, 180],
            get_fill_color=[0, 0, 0, 0],
            stroked=True,
            filled=False,
            line_width_min_pixels=2,
        ))

    # Auto-zoom to fit all selected cities
    if len(city_metas) > 1 and len(meta_lats) > 1:
        lat_range = max(meta_lats) - min(meta_lats)
        lng_range = max(meta_lngs) - min(meta_lngs)
        span = max(lat_range, lng_range)
        if span > 5:
            zoom = 4
        elif span > 2:
            zoom = 5
        elif span > 1:
            zoom = 7
        elif span > 0.5:
            zoom = 8
        elif span > 0.1:
            zoom = 10
        else:
            zoom = 12
    else:
        zoom = 12

    view = pdk.ViewState(
        latitude=center_lat,
        longitude=center_lng,
        zoom=zoom,
        pitch=0,
    )

    tooltip = {
        "html": (
            "<b>{name}</b><br/>"
            "Rating: {rating_fmt}<br/>"
            "Reviews: {reviews_fmt}<br/>"
            "Types: {types_short}"
        ),
        "style": {
            "backgroundColor": "#1e1e2e",
            "color": "white",
            "fontSize": "13px",
            "padding": "8px 12px",
            "borderRadius": "6px",
        },
    }

    # -------------------------------------------------------------------
    # Explorer table (below map)
    # -------------------------------------------------------------------

    st.markdown("---")

    filtered = sorted(filtered, key=lambda p: p.get("rating_count") or 0, reverse=True)

    selected_names: set[str] = set()

    if not filtered:
        st.info("No places match the current filters.")
    else:
        rows = []
        for rank, p in enumerate(filtered, 1):
            rc = p.get("rating_count") or 0
            rows.append({
                "Rank":    rank,
                "Name":    p.get("name", "—"),
                "Rating":  star_rating(p.get("rating")),
                "Reviews": f"{rc:,}" if rc else "—",
                "Tier":    tier_label(rc),
                "Types":   ", ".join((p.get("types") or [])[:3]),
                "Sources": ", ".join(
                    s.replace("GoogleMapsAPI_", "") for s in (p.get("sources") or [])
                ),
            })

        df = pd.DataFrame(rows)

        event = st.dataframe(
            df,
            use_container_width=True,
            hide_index=True,
            height=500,
            on_select="rerun",
            selection_mode="multi-row",
        )

        # Collect names of selected rows
        for idx in event.selection.rows:
            if idx < len(filtered):
                selected_names.add(filtered[idx].get("name", ""))

        # Rating bar chart
        st.markdown("---")
        chart_places = [
            p for p in filtered
            if p.get("rating_count") and p.get("rating")
        ]
        if chart_places:
            top_n = sorted(chart_places, key=lambda p: p.get("rating_count") or 0, reverse=True)[:40]
            top_n = list(reversed(top_n))
            chart_df = pd.DataFrame([{
                "Name":        p["name"][:45],
                "Reviews":     int(p["rating_count"]),
                "Rating":      float(p["rating"]),
                "Tier":        tier_label(p["rating_count"]),
                "Reviews_fmt": f"{int(p['rating_count']):,}",
            } for p in top_n])

            tier_order = [t[1] for t in TIERS]
            tier_colors = {t[1]: "rgb({},{},{})".format(*t[2]) for t in TIERS}

            fig = px.bar(
                chart_df,
                x="Rating",
                y="Name",
                orientation="h",
                color="Tier",
                category_orders={"Tier": tier_order},
                color_discrete_map=tier_colors,
                hover_name="Name",
                hover_data={"Rating": ":.2f", "Reviews_fmt": True, "Tier": True, "Name": False},
                title=f"Top {len(top_n)} Places — Rating (color = popularity tier)",
            )
            fig.update_layout(
                height=max(400, len(top_n) * 22),
                margin={"l": 20, "r": 20, "t": 50, "b": 40},
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                font_color="#ccc",
                legend_title_text="Review tier",
                xaxis_title="Rating",
                yaxis_title=None,
                xaxis=dict(range=[3.0, 5.1], gridcolor="#333", dtick=0.5),
                yaxis=dict(gridcolor="#333"),
                bargap=0.25,
            )
            fig.add_vline(x=4.5, line_dash="dot", line_color="#555",
                          annotation_text="4.5", annotation_font_color="#777")
            st.plotly_chart(fig, use_container_width=True)

    # Add highlight layer for selected places, then render map
    if selected_names:
        highlight_places = [
            p for p in filtered
            if p.get("name") in selected_names and p.get("lat") and p.get("lng")
        ]
        if highlight_places:
            hl_df = pd.DataFrame(highlight_places)
            hl_df["rating_count"] = pd.to_numeric(hl_df["rating_count"], errors="coerce").fillna(0).astype(int)
            hl_df["reviews_fmt"] = hl_df["rating_count"].apply(lambda rc: f"{rc:,}" if rc else "—")
            hl_df["types_short"] = hl_df["types"].apply(lambda ts: ", ".join(ts[:3]) if ts else "—")
            hl_df["rating_fmt"]  = hl_df["rating"].apply(star_rating)
            # Pulsing ring around selected places
            layers.append(pdk.Layer(
                "ScatterplotLayer",
                data=hl_df,
                get_position="[lng, lat]",
                get_fill_color=[0, 0, 0, 0],
                get_line_color=[255, 0, 255, 230],
                get_radius=150,
                radius_min_pixels=16,
                radius_max_pixels=50,
                stroked=True,
                filled=False,
                line_width_min_pixels=3,
                pickable=True,
                opacity=1.0,
            ))

    with map_container:
        st.pydeck_chart(
            pdk.Deck(
                layers=layers,
                initial_view_state=view,
                tooltip=tooltip,
                map_style="https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json",
            ),
            use_container_width=True,
            height=620,
        )
