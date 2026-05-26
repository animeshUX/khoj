import { applyFilters } from "./filters.js";

function esc(s) {
  return String(s == null ? '' : s)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

// Friendly labels for the score-breakdown tooltip. Keys come from score.py.
const SCORE_LABELS = { commute: "Commute", safety: "Safety", sa: "SA food", price: "Price" };

function scoreTipHtml(breakdown) {
  const head = `<div class="tip-head">Fit <strong>${breakdown.total}</strong>&nbsp;/&nbsp;100</div>`;
  const foot = `<p class="tip-foot">Weighted blend: 35% commute · 25% safety · 20% SA access · 20% price. Missing data drops that component from the average rather than penalizing — contributions sum to the total.</p>`;
  if (!breakdown.components) return head + foot;
  const rows = Object.entries(breakdown.components).map(([k, c]) =>
    `<tr><th>${SCORE_LABELS[k] || k}</th>` +
    `<td class="num">${c.score}</td>` +
    `<td class="num">+${Math.round(c.contribution)}</td></tr>`
  ).join("");
  return head +
    `<table class="tip-grid">
      <thead><tr><th></th><th class="num">Score</th><th class="num">Adds</th></tr></thead>
      <tbody>${rows}</tbody>
    </table>` + foot;
}

function initScoreTip(root) {
  const tip = document.createElement("div");
  tip.id = "khoj-score-tip";
  tip.setAttribute("role", "tooltip");
  tip.hidden = true;
  document.body.appendChild(tip);

  function showFor(badge) {
    const id = badge.closest(".khoj-row")?.dataset.id;
    const l  = window.KHOJ.listings.find(x => x.id === id);
    if (!l) return;
    // Fall back to a header-only tip when older payloads lack score_breakdown.
    const bd = l.score_breakdown && l.score_breakdown.components
      ? l.score_breakdown
      : { total: Math.round((l.score ?? 0) * 100), components: null };
    tip.innerHTML = scoreTipHtml(bd);
    tip.hidden = false;
    // Measure after content insertion, then place: prefer below-right of the
    // badge; flip vertically / clamp horizontally so it stays on-screen.
    const b = badge.getBoundingClientRect();
    const t = tip.getBoundingClientRect();
    let top  = b.bottom + 8;
    let left = b.right - t.width;
    if (top + t.height > window.innerHeight - 8) top = b.top - t.height - 8;
    if (left < 8) left = 8;
    if (left + t.width > window.innerWidth - 8) left = window.innerWidth - 8 - t.width;
    tip.style.top  = top  + "px";
    tip.style.left = left + "px";
  }
  function hide() { tip.hidden = true; }

  root.addEventListener("mouseover", (e) => {
    const badge = e.target.closest(".khoj-row-score");
    if (badge) showFor(badge);
  });
  root.addEventListener("mouseout", (e) => {
    const badge = e.target.closest(".khoj-row-score");
    if (badge && !badge.contains(e.relatedTarget)) hide();
  });
  // Hide on scroll — fixed-positioned tooltip would otherwise stay pinned.
  root.addEventListener("scroll", hide, { passive: true });
  window.addEventListener("scroll", hide, { passive: true });
}

const SORTS = {
  score:   (a, b) => (b.score ?? 0) - (a.score ?? 0),
  price:   (a, b) => (a.price ?? Infinity) - (b.price ?? Infinity),
  commute: (a, b) => (a.enrichment?.commute?.total_min ?? Infinity)
                   - (b.enrichment?.commute?.total_min ?? Infinity),
  posted:  (a, b) => (b.posted_at ?? "").localeCompare(a.posted_at ?? ""),
};

export function createList(state, mountId = "khoj-list", map = null) {
  const root = document.getElementById(mountId);

  function rowHtml(l) {
    const price = l.price ? `$${l.price}` : "—";
    const beds = l.beds == null ? "?" : (l.beds === 0 ? "Studio" : `${l.beds}BR`);
    const scorePct = l.score == null ? "" : Math.round(l.score * 100);
    const score = scorePct === ""
      ? ""
      : `<span class="khoj-row-score" tabindex="0" aria-label="Fit score ${scorePct} of 100, hover for breakdown">${scorePct}</span>`;
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
    syncInView();
  }

  // Mark list rows whose pin is outside the current map viewport, and tack
  // a "K in view" suffix onto the count. Cheap on every moveend.
  function syncInView() {
    const countEl = document.getElementById("khoj-count");
    const total = window.KHOJ.listings.length;
    const rows = root.querySelectorAll(".khoj-row");
    const visibleCount = rows.length;
    if (!map?.map) {
      if (countEl) countEl.textContent = `${visibleCount} of ${total}`;
      return;
    }
    const bounds = map.map.getBounds();
    let inView = 0;
    for (const row of rows) {
      const marker = map.markerByUrl.get(row.dataset.id);
      if (!marker) { row.classList.remove("out-of-view"); continue; }
      const isIn = bounds.contains(marker.getLatLng());
      row.classList.toggle("out-of-view", !isIn);
      if (isIn) inView++;
    }
    if (countEl) {
      const suffix = inView === visibleCount ? "" : ` · ${inView} in view`;
      countEl.textContent = `${visibleCount} of ${total}${suffix}`;
    }
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

  initScoreTip(root);

  state.subscribe("sort",    render);
  state.subscribe("filters", render);
  state.subscribe("starred", render);
  state.subscribe("hidden",  render);
  state.subscribe("selectedId", (id) => {
    for (const row of root.querySelectorAll(".khoj-row")) {
      row.classList.toggle("is-active", row.dataset.id === id);
    }
  });
  if (map?.map) map.map.on("moveend zoomend", syncInView);
  render();
  return { render };
}
