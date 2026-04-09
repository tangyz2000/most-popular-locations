# TODO

1. **Chain Detection:** Use Wikidata or other sources to determine a restaurant is a chain or not. Add a filter in frontend to filter them out so that restaurants like Cheesecake Factory will not show up.
2. **TextSearch Improvement:** Right now we perform TextSearch on cities nearby. (1) This has low searching quality because, if I am searching New Orleans with 4000 Meters parameters, we are unable to find places 2 hours drive from New Orleans that has 1K+ reviews because these are really sparse areas, outside of the radius, with no cities nearby. Therefore, we will miss those "hidden gems". (2) Right now we only perform TextSearch using 1 sentence. We can extend the query.
3. **OSM-guided Search:** Use OSM-guided search or sources other than GoogleMap API to reduce Google Map API costs.
4. ~~**Single-page Explorer + Map:** Move Explorer and Map to a single page. Make them interactive. Ex. clicking a location will highlight it on the map.~~ *(completed 2026-04-07)*
5. ~~**Hover Hit Area:** We made the dot to be smaller so when my mouse hover over the dot, it is hard to display the information than larger dots. Fixed by adding an invisible larger hit-area layer.~~ *(completed 2026-04-09)*
