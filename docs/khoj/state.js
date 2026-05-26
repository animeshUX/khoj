const LS_PREFIX = "khoj.";
const PERSISTED = new Set([
  "starred", "hidden", "notes", "filters", "layers", "sort", "tile",
]);

export function createState(initial = {}) {
  const data = { ...initial };
  const listeners = new Map();   // key -> Set<fn>

  for (const key of PERSISTED) {
    try {
      const raw = localStorage.getItem(LS_PREFIX + key);
      if (raw === null) continue;
      try { data[key] = JSON.parse(raw); }
      catch { data[key] = raw; }   /* legacy plain-string value */
    } catch { /* localStorage unavailable */ }
  }

  function get(key) { return data[key]; }

  function set(key, value) {
    data[key] = value;
    if (PERSISTED.has(key)) {
      try { localStorage.setItem(LS_PREFIX + key, JSON.stringify(value)); }
      catch { /* quota or private mode — skip */ }
    }
    const subs = listeners.get(key);
    if (subs) for (const fn of subs) fn(value);
  }

  function subscribe(key, fn) {
    if (!listeners.has(key)) listeners.set(key, new Set());
    listeners.get(key).add(fn);
    return () => listeners.get(key).delete(fn);
  }

  return { get, set, subscribe };
}
