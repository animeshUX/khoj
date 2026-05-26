import { createState } from "./state.js";
import { createMap } from "./map.js";
import { createList } from "./list.js";
import { createPanel } from "./panel.js";
import { createOverlays, createSelectionOverlays } from "./overlays.js";

const state = createState({
  filters: window.KHOJ.filter_defaults,
  selectedId: null,
});

const map = createMap(state, "khoj-map");
const overlays = createOverlays(state, map);
createSelectionOverlays(state, map);
createList(state, "khoj-list", map);
createPanel(state, "khoj-panel");

state.subscribe("selectedId", (id) => {
  document.getElementById("khoj-map").classList.toggle("dimmed", !!id);
});

window.KHOJ_overlays = overlays;   // exposed for filter-bar Task 16
