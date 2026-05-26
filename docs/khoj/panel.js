const PAYLOAD = JSON.parse(document.getElementById('payload').textContent);

function esc(s) {
  return String(s == null ? '' : s)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

export function createPanel(state, mountId = "khoj-panel") {
  const root = document.getElementById(mountId);

  function close() { state.set("selectedId", null); }

  function render(id) {
    if (!id) {
      root.setAttribute("aria-hidden", "true");
      root.innerHTML = "";
      return;
    }
    const l = PAYLOAD.find((x) => x.url === id);
    if (!l) { close(); return; }

    const starred = (state.get("starred") || []).includes(id);
    const hidden  = (state.get("hidden")  || []).includes(id);
    const note    = (state.get("notes") || {})[id] || "";

    root.innerHTML = `
      <button class="khoj-panel-close" aria-label="Close">✕</button>
      <header>
        <h2>${esc(l.title)}</h2>
        <p class="khoj-panel-meta">
          ${l.price ? "$" + l.price : "—"} · ${l.bedrooms == null ? "?" : (l.bedrooms === 0 ? "Studio" : l.bedrooms + "BR")}
          · <a href="${esc(l.url)}" target="_blank" rel="noopener">source ↗</a>
        </p>
        <p class="khoj-panel-addr">${esc(l.address ?? "")}</p>
      </header>
      <section class="khoj-panel-actions">
        <button data-action="star">${starred ? "★ Starred" : "☆ Star"}</button>
        <button data-action="hide">${hidden ? "⊘ Hidden" : "⊘ Hide"}</button>
      </section>
      <section class="khoj-panel-note">
        <label>Note<textarea data-action="note">${esc(note)}</textarea></label>
      </section>
      <section class="khoj-panel-enrichment" id="khoj-panel-enrich"></section>
    `;
    root.setAttribute("aria-hidden", "false");

    root.querySelector(".khoj-panel-close").addEventListener("click", close);
    root.querySelector("[data-action=star]").addEventListener("click", () => {
      const cur = state.get("starred") || [];
      state.set("starred", cur.includes(id) ? cur.filter(x => x !== id) : [...cur, id]);
      render(id);
    });
    root.querySelector("[data-action=hide]").addEventListener("click", () => {
      const cur = state.get("hidden") || [];
      state.set("hidden", cur.includes(id) ? cur.filter(x => x !== id) : [...cur, id]);
      render(id);
    });
    root.querySelector("[data-action=note]").addEventListener("input", (e) => {
      const cur = { ...(state.get("notes") || {}) };
      cur[id] = e.target.value;
      state.set("notes", cur);
    });
  }

  state.subscribe("selectedId", render);
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") close(); });
  return { render };
}
