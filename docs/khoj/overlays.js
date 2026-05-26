function esc(s) {
  return String(s == null ? '' : s)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

const ROUTE_COLOR = {
  F: '#FF6319', A: '#2850AD', C: '#2850AD', R: '#FCCC0A',
};
// Yellow routes (N/Q/R/W) use black text per MTA signage; everyone else uses white.
const ROUTE_TEXT_FILL = { R: '#000', N: '#000', Q: '#000', W: '#000' };

function bulletSvg(letter, color) {
  const txt = ROUTE_TEXT_FILL[letter] || '#fff';
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" width="20" height="20" aria-hidden="true">
    <circle cx="10" cy="10" r="9.25" fill="${color}" stroke="#fff" stroke-width="1.2"/>
    <text x="10" y="14" text-anchor="middle" fill="${txt}" font-family="Helvetica,Arial,sans-serif" font-weight="700" font-size="11">${letter}</text>
  </svg>`;
}

const POI_ICONS = {
  food:    { color: '#7A5C1E', d: 'M8.1 13.34l2.83-2.83L3.91 3.5c-1.56 1.56-1.56 4.09 0 5.66l4.19 4.18zm6.78-1.81c1.53.71 3.68.21 5.27-1.38 1.91-1.91 2.28-4.65.81-6.12-1.46-1.46-4.2-1.1-6.12.81-1.59 1.59-2.09 3.74-1.38 5.27L3.7 19.87l1.41 1.41L12 14.41l6.88 6.88 1.41-1.41L13.41 13l1.47-1.47z' },
  grocery: { color: '#3a5a40', d: 'M18 6h-2c0-2.21-1.79-4-4-4S8 3.79 8 6H6c-1.1 0-2 .9-2 2v12c0 1.1.9 2 2 2h12c1.1 0 2-.9 2-2V8c0-1.1-.9-2-2-2zm-6-2c1.1 0 2 .9 2 2h-4c0-1.1.9-2 2-2zm6 16H6V8h2v2c0 .55.45 1 1 1s1-.45 1-1V8h4v2c0 .55.45 1 1 1s1-.45 1-1V8h2v12z' },
};

function poiSvg(kind) {
  const { color, d } = POI_ICONS[kind];
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="22" height="22" aria-hidden="true">
    <circle cx="12" cy="12" r="11" fill="${color}" stroke="#fff" stroke-width="1.4"/>
    <g transform="translate(4.8 4.8) scale(0.6)"><path d="${d}" fill="#fff"/></g>
  </svg>`;
}

const REGISTRY = {
  noise: {
    path: './data/nta-noise.geojson',
    build(geo) {
      const dens = geo.features.map(f => f.properties.noise_per_sqmi).sort((a, b) => a - b);
      const p90 = dens[Math.floor(dens.length * 0.9)] || 1;
      return L.geoJSON(geo, {
        style: (feat) => {
          const d = feat.properties.noise_per_sqmi || 0;
          const ratio = Math.min(d / p90, 1);
          return {
            color: '#8C2026', weight: 0.4, opacity: 0.35,
            fillColor: '#8C2026', fillOpacity: 0.04 + ratio * 0.42,
          };
        },
        onEachFeature: (feat, layer) => {
          const p = feat.properties;
          layer.bindTooltip(
            `<b>${esc(p.name)}</b><br>${esc(p.borough)}<br>` +
            `${(p.noise_90d || 0).toLocaleString()} noise complaints / 90d<br>` +
            `${(p.noise_per_sqmi || 0).toLocaleString()} per sq mi`,
            { sticky: true, className: 'station-tooltip', direction: 'top' }
          );
        },
      });
    },
  },
  crime: {
    path: './data/crime.geojson',
    build(geo) {
      // Quintile breaks on felonies-per-sq-mi. Raw counts collapse the visual
      // (most precincts are above any single threshold), and they're biased by
      // precinct area. Density quintiles give an ordinal "lower / higher than
      // the rest of NYC" signal that's actually legible at a glance.
      const densities = geo.features
        .map(f => f.properties?.felonies_per_sqmi || 0)
        .sort((a, b) => a - b);
      const q = (p) => densities[Math.floor(densities.length * p)] || 0;
      const breaks = [q(0.2), q(0.4), q(0.6), q(0.8)];
      const FILL_OPACITY = [0.10, 0.22, 0.36, 0.52, 0.68];
      function bin(d) {
        for (let i = 0; i < breaks.length; i++) if (d <= breaks[i]) return i;
        return 4;
      }
      return L.geoJSON(geo, {
        style: (f) => {
          const d = f.properties?.felonies_per_sqmi || 0;
          return {
            color: '#8C2026', weight: 0.6, opacity: 0.45,
            fillColor: '#8C2026', fillOpacity: FILL_OPACITY[bin(d)],
          };
        },
        onEachFeature: (feat, layer) => {
          const p = feat.properties || {};
          const d = p.felonies_per_sqmi || 0;
          layer.bindTooltip(
            `<b>${esc(p.precinct)} Pct</b> &middot; Q${bin(d) + 1}<br>` +
            `${(p.felonies || 0).toLocaleString()} felonies / 12mo<br>` +
            `${d.toLocaleString()} per sq mi  <span class="enr-mute">(${(p.area_sqmi || 0).toFixed(1)} sq mi)</span>`,
            { sticky: true, className: 'station-tooltip', direction: 'top' }
          );
        },
      });
    },
  },
  parks: {
    path: './data/parks.geojson',
    build(geo) {
      return L.geoJSON(geo, {
        style: {
          color: '#3F5F3F', weight: 0.4, opacity: 0.55,
          fillColor: '#7BAA7B', fillOpacity: 0.42,
        },
        onEachFeature: (feat, layer) => {
          const p = feat.properties;
          if (p.name) {
            layer.bindTooltip(
              `<b>${esc(p.name)}</b><br>${(p.acres || 0).toFixed(1)} acres`,
              { sticky: true, className: 'station-tooltip', direction: 'top' }
            );
          }
        },
      });
    },
  },
  subway_lines: {
    path: './data/subway-lines.geojson',
    build(geo) {
      return L.geoJSON(geo, {
        style: { color: '#1A1612', weight: 1.4, opacity: 0.22 },
        interactive: false,
      });
    },
  },
  subway_stations: {
    path: './data/subway-stations.geojson',
    build(geo) {
      return L.geoJSON(geo, {
        pointToLayer: (feat, latlng) => {
          const routes = (feat.properties.daytime_routes || '').split(' ').filter(Boolean);
          const primary = routes.find(r => ROUTE_COLOR[r]);
          if (primary) {
            return L.marker(latlng, {
              icon: L.divIcon({
                className: 'khoj-subway-bullet',
                html: bulletSvg(primary, ROUTE_COLOR[primary]),
                iconSize: [20, 20],
                iconAnchor: [10, 10],
              }),
            });
          }
          // Non-relevant station: small muted dot, non-interactive.
          return L.circleMarker(latlng, {
            radius: 2, color: '#fff', weight: 0.6,
            fillColor: '#93857A', fillOpacity: 0.5,
            interactive: false,
          });
        },
        onEachFeature: (feat, layer) => {
          if (layer.bindTooltip) {
            layer.bindTooltip(
              `<b>${esc(feat.properties.stop_name || '')}</b><br>${esc(feat.properties.daytime_routes || '—')}`,
              { direction: 'top', className: 'station-tooltip' }
            );
          }
        },
      });
    },
  },
  commute_zone: {
    path: './data/commute-zone.geojson',
    build(geo) {
      return L.geoJSON(geo, {
        style: {
          color: '#8C2026', weight: 1.2, opacity: 0.6, dashArray: '6 4',
          fillColor: '#8C2026', fillOpacity: 0.055,
        },
        interactive: false,
      });
    },
  },
};

export function createOverlays(state, mapApi) {
  const leafletMap = mapApi.map;
  const layers = {};   // name -> L.GeoJSON
  const loaded = {};   // name -> Promise<L.GeoJSON>

  async function load(name) {
    if (loaded[name]) return loaded[name];
    loaded[name] = fetch(REGISTRY[name].path)
      .then(r => {
        if (!r.ok) throw new Error(`${REGISTRY[name].path}: HTTP ${r.status}`);
        return r.json();
      })
      .then(geo => {
        const layer = REGISTRY[name].build(geo);
        layers[name] = layer;
        return layer;
      })
      .catch(err => { delete loaded[name]; throw err; });
    return loaded[name];
  }

  async function show(name) {
    const layer = await load(name);
    if (!leafletMap.hasLayer(layer)) {
      layer.addTo(leafletMap);
      if (name === 'commute_zone') layer.bringToBack();
    }
  }

  function hide(name) {
    if (layers[name] && leafletMap.hasLayer(layers[name])) leafletMap.removeLayer(layers[name]);
  }

  async function toggle(name, on) { on ? await show(name) : hide(name); }

  // Restore persisted layer state on init
  const initial = state.get('layers') || { subway_lines: true, subway_stations: true, commute_zone: true };
  state.set('layers', initial);
  for (const [name, on] of Object.entries(initial)) if (on) show(name);

  return { toggle, show, hide };
}

export function createSelectionOverlays(state, mapApi) {
  const leafletMap = mapApi.map;
  let pathLayer = null;
  let pathLabel = null;
  let poiLayer = null;

  function clear() {
    if (pathLayer) { leafletMap.removeLayer(pathLayer); pathLayer = null; }
    if (pathLabel) { leafletMap.removeLayer(pathLabel); pathLabel = null; }
    if (poiLayer)  { leafletMap.removeLayer(poiLayer);  poiLayer  = null; }
  }

  function show(id) {
    clear();
    if (!id) return;
    const l = window.KHOJ.listings.find(x => x.id === id);
    if (!l) return;
    const enr = l.enrichment || {};

    // Commute path: listing -> station -> Tandon
    const st = enr.commute?.station;
    if (st) {
      const pts = [[l.lat, l.lng], [st.lat, st.lng],
                   [window.KHOJ.campus.lat, window.KHOJ.campus.lng]];
      pathLayer = L.polyline(pts, { color: "#8C2026", weight: 2, dashArray: "6 4", opacity: 0.7 }).addTo(leafletMap);
      pathLabel = L.tooltip({ permanent: true, direction: "center", className: "khoj-path-label" })
        .setLatLng([(l.lat + st.lat) / 2, (l.lng + st.lng) / 2])
        .setContent(`${enr.commute.walk_min}m walk`)
        .addTo(leafletMap);
    }

    // POI markers
    const pois = [
      ...(enr.food    || []).map(p => ({ ...p, kind: "food"    })),
      ...(enr.grocery || []).map(p => ({ ...p, kind: "grocery" })),
    ];
    poiLayer = L.layerGroup(
      pois.filter(p => p.lat != null).map(p =>
        L.marker([p.lat, p.lng], {
          icon: L.divIcon({
            className: `khoj-poi khoj-poi--${p.kind}`,
            html: poiSvg(p.kind),
            iconSize: [22, 22],
            iconAnchor: [11, 11],
          }),
        }).bindTooltip(`${esc(p.name)} (${p.dist_mi?.toFixed(2)}mi)`)),
    ).addTo(leafletMap);
  }

  state.subscribe("selectedId", show);
  return { clear };
}
