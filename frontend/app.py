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

selected_city = st.sidebar.selectbox("City", list(cities.keys()))
data = load_city(cities[selected_city])
places = data.get("places", [])
radius_m = data.get("radius_meters", "?")
center_lat_stored = data.get("center_lat")
center_lng_stored = data.get("center_lng")

st.sidebar.markdown(f"**Search radius:** {radius_m:,} m" if isinstance(radius_m, int) else f"**Search radius:** {radius_m}")
st.sidebar.markdown(f"**Total places:** {len(places):,}")

with_coords = [p for p in places if p.get("lat") and p.get("lng")]
without_coords = len(places) - len(with_coords)

st.sidebar.markdown(f"**With coordinates:** {len(with_coords):,}")
if without_coords:
    st.sidebar.caption(f"{without_coords} places have no coordinates (run `example.py` again to collect them).")

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
# Main tabs
# ---------------------------------------------------------------------------

tab_map, tab_explorer = st.tabs(["🗺️  Map", "🔍  Explorer"])


# ── MAP TAB ─────────────────────────────────────────────────────────────────

with tab_map:
    st.subheader(f"Popular Places — {selected_city}")

    if not with_coords:
        st.warning("No coordinate data found. Run `example.py` to collect lat/lng for this city.")
    else:
        df_map = pd.DataFrame(with_coords)
        df_map["rating_count"] = pd.to_numeric(df_map["rating_count"], errors="coerce").fillna(0).astype(int)

        map_max = int(df_map["rating_count"].max())

        col_slider, col_types = st.columns([2, 3])

        with col_slider:
            log_options = [0] + sorted(set(
                int(v) for v in np.geomspace(1, map_max, num=300)
            ))
            map_min_reviews = st.select_slider(
                "Min reviews",
                options=log_options,
                value=0,
                format_func=lambda x: f"{x:,}",
                key="map_min_reviews",
            )

        with col_types:
            map_all_types = sorted({
                (p.get("types") or [None])[0]
                for p in with_coords
                if (p.get("types") or [None])[0] is not None
            })
            map_selected_types = st.multiselect(
                "Filter by type (primary)",
                map_all_types,
                placeholder="All types",
                key="map_types",
            )

        df_map = df_map[df_map["rating_count"] >= map_min_reviews]
        if map_selected_types:
            map_type_set = set(map_selected_types)
            df_map = df_map[df_map["types"].apply(
                lambda ts: bool(map_type_set.intersection(ts or []))
            )]

        df_map["color"]       = df_map["rating_count"].apply(tier_color)
        df_map["tier"]        = df_map["rating_count"].apply(tier_label)
        df_map["radius"]      = df_map["rating_count"].apply(
            lambda rc: max(30, int(math.log10(max(rc or 1, 1)) * 28))
        )
        df_map["reviews_fmt"] = df_map["rating_count"].apply(
            lambda rc: f"{rc:,}" if rc else "—"
        )
        df_map["types_short"] = df_map["types"].apply(
            lambda ts: ", ".join(ts[:3]) if ts else "—"
        )
        df_map["rating_fmt"]  = df_map["rating"].apply(star_rating)

        center_lat = center_lat_stored if center_lat_stored is not None else df_map["lat"].median()
        center_lng = center_lng_stored if center_lng_stored is not None else df_map["lng"].median()

        layer = pdk.Layer(
            "ScatterplotLayer",
            data=df_map,
            get_position="[lng, lat]",
            get_fill_color="color",
            get_radius="radius",
            radius_min_pixels=4,
            radius_max_pixels=28,
            pickable=True,
            opacity=0.85,
        )

        layers = [layer]
        if isinstance(radius_m, int):
            radius_layer = pdk.Layer(
                "ScatterplotLayer",
                data=[{"lat": center_lat, "lng": center_lng}],
                get_position="[lng, lat]",
                get_radius=radius_m,
                get_line_color=[255, 255, 255, 180],
                get_fill_color=[0, 0, 0, 0],
                stroked=True,
                filled=False,
                line_width_min_pixels=2,
            )
            layers.append(radius_layer)

        view = pdk.ViewState(
            latitude=center_lat,
            longitude=center_lng,
            zoom=12,
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

        col1, col2, col3 = st.columns(3)
        filtered_out = len(with_coords) - len(df_map)
        col1.metric("Places on map", f"{len(df_map):,}", f"{filtered_out:,} filtered out" if filtered_out > 0 else None)
        col2.metric("Median reviews", f"{int(df_map['rating_count'].median()):,}" if not df_map.empty else "—")
        col3.metric("Max reviews", f"{int(df_map['rating_count'].max()):,}" if not df_map.empty else "—")


# ── EXPLORER TAB ────────────────────────────────────────────────────────────

with tab_explorer:
    st.subheader(f"Place Explorer — {selected_city}")

    # Controls
    col_search, col_sort = st.columns([3, 1])
    search_query = col_search.text_input("Search by name", placeholder="e.g. park, museum, café…")
    sort_by = col_sort.radio("Sort by", ["Reviews", "Rating", "Name"], horizontal=True)

    col_types, col_min = st.columns([3, 1])

    all_types = sorted({t for p in places for t in (p.get("types") or [])})
    selected_types = col_types.multiselect("Filter by type", all_types, placeholder="All types")

    exp_max = max((int(p.get("rating_count") or 0) for p in places), default=1000)
    exp_options = [0] + sorted(set(
        int(v) for v in np.geomspace(1, exp_max, num=300)
    ))
    min_reviews = col_min.select_slider(
        "Min reviews",
        options=exp_options,
        value=0,
        format_func=lambda x: f"{x:,}",
        key="exp_min_reviews",
    )

    # Filter
    filtered = places
    if search_query:
        q = search_query.lower()
        filtered = [p for p in filtered if q in (p.get("name") or "").lower()]
    if selected_types:
        selected_set = set(selected_types)
        filtered = [p for p in filtered if selected_set.intersection(p.get("types") or [])]
    filtered = [p for p in filtered if (p.get("rating_count") or 0) >= min_reviews]

    # Sort
    if sort_by == "Reviews":
        filtered = sorted(filtered, key=lambda p: p.get("rating_count") or 0, reverse=True)
    elif sort_by == "Rating":
        filtered = sorted(filtered, key=lambda p: p.get("rating") or 0, reverse=True)
    else:
        filtered = sorted(filtered, key=lambda p: p.get("name") or "")

    # Summary metrics
    if filtered:
        med = sorted(p.get("rating_count") or 0 for p in filtered)[len(filtered) // 2]
        qualifying = sum(1 for p in filtered if (p.get("rating_count") or 0) >= 500)
    else:
        med, qualifying = 0, 0

    c1, c2, c3 = st.columns(3)
    c1.metric("Showing", f"{len(filtered):,} places")
    c2.metric("≥500 reviews", f"{qualifying:,}")
    c3.metric("Median reviews", f"{med:,}")

    # Table
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

        st.dataframe(
            df,
            use_container_width=True,
            hide_index=True,
            height=500,
        )

        # Rating bar chart — bar length = rating, color = popularity tier
        st.markdown("---")
        chart_places = [
            p for p in filtered
            if p.get("rating_count") and p.get("rating")
        ]
        if chart_places:
            # Always sort by reviews desc for the chart regardless of table sort
            top_n = sorted(chart_places, key=lambda p: p.get("rating_count") or 0, reverse=True)[:40]
            # Plotly horizontal bars render bottom-to-top, so reverse to put most popular on top
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
