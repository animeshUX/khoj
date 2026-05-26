import { applyFilters } from "./filters.js";

export function createKeys(state) {
  function visibleIds() {
    const sorted = applyFilters(window.KHOJ.listings, state)
      .sort((a, b) => (b.score ?? 0) - (a.score ?? 0));
    return sorted.map(l => l.id);
  }

  function move(delta) {
    const ids = visibleIds();
    if (!ids.length) return;
    const cur = state.get("selectedId");
    const i = ids.indexOf(cur);
    const next = i < 0 ? ids[0] : ids[(i + delta + ids.length) % ids.length];
    state.set("selectedId", next);
  }

  function toggleSet(key, id) {
    const cur = state.get(key) || [];
    state.set(key, cur.includes(id) ? cur.filter(x => x !== id) : [...cur, id]);
  }

  document.addEventListener("keydown", (e) => {
    if (e.target.matches("input, textarea, select")) return;
    if (e.key === "j") { move(1); e.preventDefault(); }
    else if (e.key === "k") { move(-1); e.preventDefault(); }
    else if (e.key === "s") {
      const id = state.get("selectedId");
      if (id) toggleSet("starred", id);
    }
    else if (e.key === "h") {
      const id = state.get("selectedId");
      if (id) toggleSet("hidden", id);
    }
    else if (e.key === "/") {
      const inp = document.querySelector('#khoj-topbar input[type="number"]');
      if (inp) { inp.focus(); inp.select(); e.preventDefault(); }
    }
  });
}
