import { createState } from "./state.js";
import { createMap } from "./map.js";

const state = createState({
  starred: new Set(),
  hidden: new Set(),
  notes: {},
  filters: { max_price: 1500, max_commute: 30, hide_hidden: true, only_starred: false },
  selectedId: null,
});

createMap(state, "khoj-map");
