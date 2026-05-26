import { applyFilters } from "./filters.js";

function esc(s) {
  return String(s == null ? '' : s)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

const SORTS = {
  score:   (a, b) => (b.score ?? 0) - (a.score ?? 0),
  price:   (a, b) => (a.price ?? Infinity) - (b.price ?? Infinity),
  commute: (a, b) => 0,
  posted:  (a, b) => (b.posted_at ?? "").localeCompare(a.posted_at ?? ""),
};

export function createList(state, mountId = "khoj-list", map = null) {
  const root = document.getElementById(mountId);

  function rowHtml(l) {
    const price = l.price ? `$${l.price}` : "—";
    const beds = l.beds == null ? "?" : (l.beds === 0 ? "Studio" : `${l.beds}BR`);
    const scorePct = l.score == null ? "" : Math.round(l.score * 100);
    const score = scorePct === "" ? "" : `<span class="khoj-row-score">${scorePct}</span>`;
    return `<article class="khoj-row" data-id="${esc(l.id)}" tabindex="0"
              aria-label="${esc(l.title)}, ${price}">
      ${score}
      <h3>${esc(l.title)}</h3>
      <p class="khoj-row-meta">${price} · ${beds}</p>
      <p class="khoj-row-hood">${esc(l.neighborhood ?? "")}</p>
    </article>`;
  }

  function render() {
    const sortKey = state.get("sort") || "score";
    const visible = applyFilters(window.KHOJ.listings, state);
    const sorted = visible.sort(SORTS[sortKey] || SORTS.score);
    if (sorted.length === 0) {
      root.innerHTML = `<div class="khoj-empty">
        <p>0 of ${window.KHOJ.listings.length} match</p>
        <button id="khoj-reset">Reset filters</button>
      </div>`;
      root.querySelector("#khoj-reset").addEventListener("click", () => {
        state.set("filters", window.KHOJ.filter_defaults);
      });
      document.getElementById("khoj-count").textContent = `0 of ${window.KHOJ.listings.length}`;
      return;
    }
    root.innerHTML = sorted.map(rowHtml).join("");
    const countEl = document.getElementById("khoj-count");
    if (countEl) countEl.textContent = `${sorted.length} of ${window.KHOJ.listings.length}`;
  }

  root.addEventListener("click", (e) => {
    const row = e.target.closest(".khoj-row");
    if (row) state.set("selectedId", row.dataset.id);
  });

  root.addEventListener("mouseover", (e) => {
    const row = e.target.closest(".khoj-row");
    if (!row || !map) return;
    const marker = map.markerByUrl.get(row.dataset.id);
    if (marker) marker.getElement()?.classList.add("khoj-pin--hover");
  });

  root.addEventListener("mouseout", (e) => {
    const row = e.target.closest(".khoj-row");
    if (!row || !map) return;
    const marker = map.markerByUrl.get(row.dataset.id);
    if (marker) marker.getElement()?.classList.remove("khoj-pin--hover");
  });

  state.subscribe("sort",    render);
  state.subscribe("filters", render);
  state.subscribe("starred", render);
  state.subscribe("hidden",  render);
  render();
  return { render };
}
