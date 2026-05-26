import { createState } from "./state.js";
import { createMap } from "./map.js";
import { createList } from "./list.js";
import { createPanel } from "./panel.js";

const state = createState({
  filters: { max_price: 1500, max_commute: 30, hide_hidden: true, only_starred: false },
  selectedId: null,
});

const map = createMap(state, "khoj-map");
createList(state, "khoj-list", map);
createPanel(state, "khoj-panel");

state.subscribe("selectedId", (id) => {
  document.getElementById("khoj-map").classList.toggle("dimmed", !!id);
});
