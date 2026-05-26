// URL-hash encoding for shareable views. Keys we care about: selected listing
// + filter chip values. Tile / layers / sort already persist to localStorage,
// so we keep them out of the URL to avoid polluting paste-able links.

function defaultFilters() {
  return { ...(window.KHOJ?.filter_defaults || {}) };
}

export function parseHash() {
  const h = window.location.hash.replace(/^#/, "");
  if (!h) return null;
  const p = new URLSearchParams(h);
  const out = {};
  if (p.has("sel")) out.selectedId = p.get("sel");
  const hasFilter = ["price", "commute", "food", "star", "hide"].some((k) => p.has(k));
  if (hasFilter) {
    const f = defaultFilters();
    if (p.has("price"))   f.max_price   = Number(p.get("price"))   || null;
    if (p.has("commute")) f.max_commute = Number(p.get("commute")) || null;
    if (p.has("food"))    f.south_asian = p.get("food") === "1";
    if (p.has("star"))    f.only_starred = p.get("star") === "1";
    if (p.has("hide"))    f.hide_hidden  = p.get("hide") !== "0";
    out.filters = f;
  }
  return out;
}

export function writeHash(state) {
  const sel = state.get("selectedId");
  const f   = state.get("filters") || {};
  const d   = defaultFilters();
  const p = new URLSearchParams();
  if (sel) p.set("sel", sel);
  if (f.max_price   != null && f.max_price   !== d.max_price)   p.set("price",   f.max_price);
  if (f.max_commute != null && f.max_commute !== d.max_commute) p.set("commute", f.max_commute);
  if (f.south_asian)  p.set("food", "1");
  if (f.only_starred) p.set("star", "1");
  if (f.hide_hidden === false) p.set("hide", "0");
  const next = p.toString();
  const url  = next ? "#" + next : window.location.pathname + window.location.search;
  // replaceState doesn't fire hashchange — no feedback loop.
  history.replaceState(null, "", url);
}

export function wireHash(state) {
  const initial = parseHash();
  if (initial?.filters)    state.set("filters",    initial.filters);
  if (initial?.selectedId) state.set("selectedId", initial.selectedId);

  state.subscribe("selectedId", () => writeHash(state));
  state.subscribe("filters",    () => writeHash(state));
}
