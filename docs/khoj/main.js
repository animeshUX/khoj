import { createState } from "./state.js";
import { createMap } from "./map.js";
import { createList } from "./list.js";

const state = createState({
  starred: new Set(),
  hidden: new Set(),
  notes: {},
  filters: { max_price: 1500, max_commute: 30, hide_hidden: true, only_starred: false },
  selectedId: null,
});

const map = createMap(state, "khoj-map");
createList(state, "khoj-list", map);
