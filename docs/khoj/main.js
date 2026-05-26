import { createState } from "./state.js";
import { createMap } from "./map.js";
import { createList } from "./list.js";
import { createPanel } from "./panel.js";
import { createOverlays, createSelectionOverlays } from "./overlays.js";
import { createFilters } from "./filters.js";
import { createKeys } from "./keys.js";
import { createResizers } from "./resize.js";
import { wireHash } from "./hash.js";

const state = createState({
  filters: window.KHOJ.filter_defaults,
  selectedId: null,
});

createFilters(state, "khoj-topbar");
const map = createMap(state, "khoj-map");
const overlays = createOverlays(state, map);
createSelectionOverlays(state, map);
map.mountLayersControl(state, overlays).addTo(map.map);
createList(state, "khoj-list", map);
createPanel(state, "khoj-panel");
createKeys(state);
createResizers(state);
wireHash(state);

state.subscribe("selectedId", (id) => {
  const mapEl = document.getElementById("khoj-map");
  mapEl.classList.toggle("dimmed", !!id);
  if (!id) return;
  // Pan so the selected pin sits in the visible-map area, not behind the panel.
  // Mobile: panel is full-screen — panning is moot.
  if (window.innerWidth < 768) return;
  const marker = map.markerByUrl.get(id);
  if (!marker) return;
  const panel = document.getElementById("khoj-panel");
  const panelOpen = panel?.getAttribute("aria-hidden") === "false";
  const panelWidth = panelOpen ? panel.getBoundingClientRect().width : 0;
  const mapWidth = map.map.getSize().x;
  const point = map.map.latLngToContainerPoint(marker.getLatLng());
  const targetX = (mapWidth - panelWidth) / 2;
  const dx = point.x - targetX;
  if (Math.abs(dx) > 20) map.map.panBy([dx, 0], { animate: true });
});
