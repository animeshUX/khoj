const PAYLOAD = JSON.parse(document.getElementById('payload').textContent);

const SORTS = {
  score:   (a, b) => (b.score ?? 0) - (a.score ?? 0),
  price:   (a, b) => (a.price ?? Infinity) - (b.price ?? Infinity),
  commute: (a, b) => 0,
  posted:  (a, b) => (b.posted ?? "").localeCompare(a.posted ?? ""),
};

export function createList(state, mountId = "khoj-list", map = null) {
  const root = document.getElementById(mountId);

  function rowHtml(l) {
    const price = l.price ? `$${l.price}` : "—";
    const beds = l.bedrooms == null ? "?" : (l.bedrooms === 0 ? "Studio" : `${l.bedrooms}BR`);
    const score = l.score == null ? "" : `<span class="khoj-row-score">${l.score}</span>`;
    return `<article class="khoj-row" data-id="${l.url}" tabindex="0"
              aria-label="${l.title}, ${price}">
      ${score}
      <h3>${l.title}</h3>
      <p class="khoj-row-meta">${price} · ${beds}</p>
      <p class="khoj-row-hood">${l.neighborhood ?? ""}</p>
    </article>`;
  }

  function render() {
    const sortKey = state.get("sort") || "score";
    const sorted = [...PAYLOAD].sort(SORTS[sortKey] || SORTS.score);
    root.innerHTML = sorted.map(rowHtml).join("");
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

  state.subscribe("sort", render);
  render();
  return { render };
}
