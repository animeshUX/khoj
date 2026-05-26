import { TILE_PROVIDERS, TILE_DEFAULT } from "./map.js";

export function createFilters(state, mountId = "khoj-topbar") {
  const root = document.getElementById(mountId);
  const f = state.get("filters") || {};
  const tile = state.get("tile") || TILE_DEFAULT;
  const tileOpts = Object.entries(TILE_PROVIDERS).map(([k, p]) =>
    `<option value="${k}"${k === tile ? " selected" : ""}>${p.label}</option>`).join("");

  root.innerHTML = `
    <span class="khoj-brand">Khoj</span>
    <label class="khoj-chip">Price ≤ $<input data-f="max_price" type="number" value="${f.max_price ?? 1500}" min="500" max="5000" step="50"></label>
    <label class="khoj-chip">Commute ≤ <input data-f="max_commute" type="number" value="${f.max_commute ?? 30}" min="5" max="90" step="5">m</label>
    <label class="khoj-chip"><input data-f="south_asian" type="checkbox" ${f.south_asian ? "checked" : ""}> SA food ≤1mi</label>
    <label class="khoj-chip"><input data-f="only_starred" type="checkbox" ${f.only_starred ? "checked" : ""}> ☆ only</label>
    <label class="khoj-chip"><input data-f="hide_hidden"  type="checkbox" ${f.hide_hidden  ? "checked" : ""}> Hide rejected</label>
    <select data-tile class="khoj-sort" aria-label="Base map">${tileOpts}</select>
    <select data-f="sort" class="khoj-sort">
      <option value="score">Sort: score</option>
      <option value="price">Sort: price</option>
      <option value="commute">Sort: commute</option>
      <option value="posted">Sort: posted</option>
    </select>
    <span class="khoj-count" id="khoj-count"></span>
  `;

  const sortSel = root.querySelector('[data-f="sort"]');
  sortSel.value = state.get("sort") || "score";
  sortSel.addEventListener("change", () => state.set("sort", sortSel.value));

  const tileSel = root.querySelector('[data-tile]');
  tileSel.addEventListener("change", () => state.set("tile", tileSel.value));
  state.subscribe("tile", (v) => { if (tileSel.value !== v) tileSel.value = v; });

  root.addEventListener("change", (e) => {
    const t = e.target;
    if (!t.dataset.f || t.dataset.f === "sort") return;
    const cur = { ...(state.get("filters") || {}) };
    const v = t.type === "checkbox" ? t.checked : (t.value === "" ? null : Number(t.value));
    cur[t.dataset.f] = v;
    state.set("filters", cur);
  });
}

export function applyFilters(listings, state) {
  const f = state.get("filters") || {};
  const starred = new Set(state.get("starred") || []);
  const hidden  = new Set(state.get("hidden")  || []);
  return listings.filter(l => {
    if (f.hide_hidden  && hidden.has(l.id)) return false;
    if (f.only_starred && !starred.has(l.id)) return false;
    if (f.max_price && l.price != null && l.price > f.max_price) return false;
    if (f.max_commute) {
      const c = l.enrichment?.commute?.total_min;
      if (c != null && c > f.max_commute) return false;
    }
    if (f.south_asian) {
      const sa = (l.enrichment?.grocery || []).some(g => g.south_asian);
      const food = (l.enrichment?.food || []).some(g => (g.dist_mi ?? 99) <= 1.0);
      if (!sa && !food) return false;
    }
    return true;
  });
}
