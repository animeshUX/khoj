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
    const l = window.KHOJ.listings.find((x) => x.id === id);
    if (!l) { close(); return; }

    const starred = (state.get("starred") || []).includes(id);
    const hidden  = (state.get("hidden")  || []).includes(id);
    const note    = (state.get("notes") || {})[id] || "";

    const beds = l.beds == null ? "?" : (l.beds === 0 ? "Studio" : l.beds + "BR");
    root.innerHTML = `
      <button class="khoj-panel-close" aria-label="Close">✕</button>
      <header>
        <h2>${esc(l.title)}</h2>
        <p class="khoj-panel-meta">
          <span>${l.price ? "$" + esc(l.price) : "—"}</span>
          <span class="sep">·</span>
          <span>${beds}</span>
          <span class="sep">·</span>
          <a href="${esc(l.url)}" target="_blank" rel="noopener">source ↗</a>
        </p>
        ${l.address ? `<p class="khoj-panel-addr">${esc(l.address)}</p>` : ""}
      </header>
      <section class="khoj-panel-actions">
        <button data-action="star" aria-pressed="${starred}">${starred ? "★ Starred" : "☆ Star"}</button>
        <button data-action="hide" aria-pressed="${hidden}">${hidden ? "⊘ Hidden" : "⊘ Hide"}</button>
      </section>
      <section class="khoj-panel-note">
        <label>Note<textarea data-action="note" placeholder="thoughts, follow-ups, contact notes…">${esc(note)}</textarea></label>
      </section>
      <section class="khoj-panel-enrichment" id="khoj-panel-enrich"></section>
    `;
    root.setAttribute("aria-hidden", "false");

    // Populate enrichment block
    const enr = l.enrichment || {};
    const mount = root.querySelector("#khoj-panel-enrich");
    const parts = [];
    if (enr.commute) {
      const lines = (enr.commute.station?.lines || []).map(esc).join("/");
      parts.push(`<div class="enr-block enr-block--wide"><h4>Commute</h4>
    <p><span class="enr-accent">${enr.commute.total_min}m</span> — ${enr.commute.walk_min}m walk to
    ${esc(enr.commute.station?.name ?? "?")}${lines ? ` (${lines})` : ""} → ${enr.commute.rail_min}m rail</p></div>`);
    }
    if (enr.crime) {
      parts.push(`<div class="enr-block"><h4>Safety (12mo)</h4>
    <p>${enr.crime.total_12mo} total · ${enr.crime.felonies} felonies · ${enr.crime.misd} misd · ${enr.crime.viol} viol</p></div>`);
    }
    if (enr.noise) {
      parts.push(`<div class="enr-block"><h4>Noise (12mo)</h4>
    <p>${enr.noise.count_12mo} 311 complaints · top: ${esc(enr.noise.top_category)}</p></div>`);
    }
    if (enr.food?.length) {
      const top = enr.food.slice(0, 3).map(f => `${esc(f.name)} (${f.dist_mi.toFixed(2)}mi)`).join(", ");
      parts.push(`<div class="enr-block enr-block--wide"><h4>Indian food</h4><p>${top}</p></div>`);
    }
    if (enr.grocery?.length) {
      const sa = enr.grocery.filter(g => g.south_asian).slice(0, 3);
      const top = (sa.length ? sa : enr.grocery.slice(0, 3))
        .map(g => `${esc(g.name)} (${g.dist_mi.toFixed(2)}mi)${g.south_asian ? " ★" : ""}`).join(", ");
      parts.push(`<div class="enr-block enr-block--wide"><h4>Grocery</h4><p>${top}</p></div>`);
    }
    mount.innerHTML = parts.join("");

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
    root.setAttribute("role", "dialog");
    root.setAttribute("aria-modal", "false");
    root.querySelector(".khoj-panel-close").focus();
  }

  state.subscribe("selectedId", render);
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") close(); });
  return { render };
}
