import { createState } from "./state.js";
import { createMap } from "./map.js";
import { createList } from "./list.js";
import { createPanel } from "./panel.js";

const state = createState({
  filters: window.KHOJ.filter_defaults,
  selectedId: null,
});

const map = createMap(state, "khoj-map");
createList(state, "khoj-list", map);
createPanel(state, "khoj-panel");

state.subscribe("selectedId", (id) => {
  document.getElementById("khoj-map").classList.toggle("dimmed", !!id);
});
