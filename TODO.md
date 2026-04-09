# TODO

1. **Chain Detection:** Use Wikidata or other sources to determine a restaurant is a chain or not. Add a filter in frontend to filter them out so that restaurants like Cheesecake Factory will not show up.
2. **TextSearch Improvement:** Right now we perform TextSearch on cities nearby. (1) This has low searching quality because, if I am searching New Orleans with 4000 Meters parameters, we are unable to find places 2 hours drive from New Orleans that has 1K+ reviews because these are really sparse areas, outside of the radius, with no cities nearby. Therefore, we will miss those "hidden gems". (2) Right now we only perform TextSearch using 1 sentence. We can extend the query.
3. **OSM-guided Search:** Use OSM-guided search or sources other than GoogleMap API to reduce Google Map API costs.
4. ~~**Single-page Explorer + Map:** Move Explorer and Map to a single page. Make them interactive. Ex. clicking a location will highlight it on the map.~~ *(completed 2026-04-07)*
5. ~~**Hover Hit Area:** We made the dot to be smaller so when my mouse hover over the dot, it is hard to display the information than larger dots. Fixed by adding an invisible larger hit-area layer.~~ *(completed 2026-04-09)*
6. **Missing Popular Places (e.g. PIER 39):** The Nearby Search API returns max 20 results per call, and places near H3 cell boundaries may be inconsistently included across API runs. PIER 39 (135K reviews, `tourist_attraction`) was confirmed missing from `San Francisco.json` despite the current code returning it when tested directly — the API likely excluded it at generation time due to boundary proximity.
   - **Root cause:** PIER 39's H3 cell center lands in the bay (~1,230m away), just inside the ~1,406m search radius. The API's `locationRestriction` circle has no guaranteed consistency at the boundary.
   - **Why subdivision didn't help:** The cell IS dense and subdivides to res-8 children, but the child cell containing PIER 39 has its center even further into the bay (~1,350m away) with a smaller radius (~531m) — PIER 39 falls outside the child's circle entirely.
   - **Why type sweeps didn't help:** Type sweeps run on leaf cells (non-dense children), using the same cell center + radius. Same boundary problem.
   - **Why TextSearch didn't catch it:** The query `"landmarks and tourist attractions in San Francisco"` may not rank PIER 39 highly enough to appear in the 60-result window, or the API may classify it primarily as `shopping_mall`.
   - **Potential fixes:**
     1. Add a **cross-validation step** — run a broad TextSearch for the city, then flag any place with >50K reviews that's missing from the Nearby Search results.
     2. Add **overlapping search circles** — search each cell with 1.5× the edge length radius instead of 1× to cover boundary gaps.
     3. Add **more TextSearch queries** — e.g. `"most popular places"`, `"top shopping and entertainment"` to catch different primary types.
     4. Add **`shopping_mall`** to `CULTURE_AND_LANDMARK_TYPES` (or create a 4th type sweep group) since PIER 39's `primaryType` is `tourist_attraction` but it also has type `shopping_mall`.
