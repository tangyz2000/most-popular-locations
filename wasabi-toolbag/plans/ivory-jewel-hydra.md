# Frontend Readability Refactoring

## Scope
- `frontend/app.py` — major refactoring
- `frontend/components/map_component/index.html` — structural cleanup

## app.py Changes
- [ ] Add named constants section (US_CENTER, DEFAULT_MAP_HEIGHT, MAX_TYPES_SHOWN, MAX_CHART_PLACES, etc.)
- [ ] Add docstrings to all functions
- [ ] Extract helpers: calculate_zoom, calculate_map_center, _get_table_selection, _render_rating_chart, rgb_to_hex
- [ ] Rename terse variables (rc→review_count, r→radius, q→query_lower)
- [ ] Remove redundant sort in capped (already sorted by render_explorer)
- [ ] Remove leading underscores from local variables
- [ ] Use constants instead of magic numbers throughout
- [ ] Fix tier_label fallback ("< 500" → "< 200")

## index.html Changes
- [ ] Add CSS custom properties for popup theming
- [ ] Add JS constants block at top (DEFAULT_HEIGHT, PLACE_RADIUS, etc.)
- [ ] Break initMap() into focused functions (addMapLayers, setupPopupHandlers, setupResizeHandler)
- [ ] Rename terse vars (hs→highlightSource, ps→placesSource, h→height, el→mapElement, p→properties)
- [ ] Add JSDoc comments to all functions
- [ ] Add explanatory comments for non-obvious patterns
- [ ] Extract updateMapSource() helper for DRY source updates

## Validation
- [ ] Syntax check both files
- [ ] Restart Streamlit and confirm 200 OK
