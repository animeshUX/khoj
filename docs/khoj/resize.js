// Drag-to-resize handles for the list rail and detail panel.
//
// Widths live as CSS custom properties on documentElement so the handles
// (siblings of #khoj-list / #khoj-panel inside #khoj-app) can position
// themselves from the same values. The panel handle stays in #khoj-app
// rather than inside #khoj-panel because panel.js rewrites the panel's
// innerHTML on every render, which would wipe a child handle.

const LS_KEY = "khoj.layout";
const DEFAULTS = { listW: 400, panelW: 560 };
const LIST_MIN = 260, LIST_MAX = 640;
const PANEL_MIN = 380, PANEL_MAX = 820;

function loadLayout() {
  // Pull current CSS values so the drag math starts from whatever the
  // stylesheet (incl. media-query overrides) is actually rendering.
  const css = getComputedStyle(document.documentElement);
  const fromCss = {
    listW:  parseInt(css.getPropertyValue("--list-w"))  || DEFAULTS.listW,
    panelW: parseInt(css.getPropertyValue("--panel-w")) || DEFAULTS.panelW,
  };
  try {
    const raw = localStorage.getItem(LS_KEY);
    if (raw) return { layout: { ...fromCss, ...JSON.parse(raw) }, hasStored: true };
  } catch {}
  return { layout: fromCss, hasStored: false };
}

function saveLayout(layout) {
  try { localStorage.setItem(LS_KEY, JSON.stringify(layout)); } catch {}
}

const clamp = (v, lo, hi) => Math.max(lo, Math.min(hi, v));

function setVars(layout) {
  const root = document.documentElement.style;
  root.setProperty("--list-w",  layout.listW  + "px");
  root.setProperty("--panel-w", layout.panelW + "px");
}

function makeHandle(kind) {
  const el = document.createElement("div");
  el.className = `khoj-resize-handle khoj-resize-handle--${kind}`;
  el.setAttribute("role", "separator");
  el.setAttribute("aria-orientation", "vertical");
  el.setAttribute("aria-label",
    kind === "list" ? "Resize list rail" : "Resize detail panel");
  el.tabIndex = 0;
  return el;
}

export function createResizers(state) {
  const app = document.getElementById("khoj-app");
  const panel = document.getElementById("khoj-panel");
  if (!app || !panel) return;

  const { layout, hasStored } = loadLayout();
  // Only force the vars when the user has a stored choice — otherwise let
  // the stylesheet's defaults (including media-query overrides) apply.
  if (hasStored) setVars(layout);

  // Mobile uses a drawer + full-screen panel; resize doesn't apply.
  const mobileMq = window.matchMedia("(max-width: 768px)");
  if (mobileMq.matches) return;

  const lh = makeHandle("list");
  const ph = makeHandle("panel");
  app.appendChild(lh);
  app.appendChild(ph);

  // Hide the panel handle when no listing is selected (panel is off-screen).
  function syncPanelHandle(id) { ph.hidden = !id; }
  syncPanelHandle(state.get("selectedId"));
  state.subscribe("selectedId", syncPanelHandle);

  function attach(handle, computeWidth, key, min, max) {
    function apply(w) {
      layout[key] = w;
      setVars(layout);
      saveLayout(layout);
    }

    handle.addEventListener("pointerdown", (e) => {
      e.preventDefault();
      handle.setPointerCapture(e.pointerId);
      handle.classList.add("is-dragging");
      document.body.classList.add("is-resizing");

      const onMove = (ev) => apply(clamp(computeWidth(ev.clientX), min, max));
      const onUp = () => {
        try { handle.releasePointerCapture(e.pointerId); } catch {}
        handle.classList.remove("is-dragging");
        document.body.classList.remove("is-resizing");
        handle.removeEventListener("pointermove", onMove);
        handle.removeEventListener("pointerup", onUp);
        handle.removeEventListener("pointercancel", onUp);
      };
      handle.addEventListener("pointermove", onMove);
      handle.addEventListener("pointerup", onUp);
      handle.addEventListener("pointercancel", onUp);
    });

    // Keyboard nudges: ←/→ for accessibility. Shift = bigger step.
    handle.addEventListener("keydown", (e) => {
      if (e.key !== "ArrowLeft" && e.key !== "ArrowRight") return;
      e.preventDefault();
      const step = (e.shiftKey ? 32 : 8) * (e.key === "ArrowLeft" ? -1 : 1);
      // Panel handle inverts: dragging left grows the panel.
      const delta = key === "panelW" ? -step : step;
      apply(clamp(layout[key] + delta, min, max));
    });
  }

  attach(lh, (x) => x - app.getBoundingClientRect().left,         "listW",  LIST_MIN,  LIST_MAX);
  attach(ph, (x) => app.getBoundingClientRect().right - x,        "panelW", PANEL_MIN, PANEL_MAX);
}
