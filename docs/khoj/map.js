// Tile providers — all free, no API key.
const TILE_PROVIDERS = {
  streets: {
    label: 'Streets',
    url: 'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
    attribution: '&copy; OpenStreetMap',
    maxZoom: 19,
  },
  minimal: {
    label: 'Minimal',
    url: 'https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}.png',
    attribution: '&copy; OpenStreetMap, &copy; CARTO',
    maxZoom: 20,
    subdomains: 'abcd',
  },
  satellite: {
    label: 'Satellite',
    url: 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
    attribution: 'Tiles &copy; Esri',
    maxZoom: 19,
  },
  transit: {
    label: 'Transit',
    url: 'https://tileserver.memomaps.de/tilegen/{z}/{x}/{y}.png',
    attribution: '&copy; OpenStreetMap, &copy; memomaps.de',
    maxZoom: 18,
  },
};
const TILE_DEFAULT = 'streets';
const TILE_KEY = 'khoj.tile';

const METERS_PER_MILE = 1609.344;
const RING_MILES = [1, 2, 3, 4];

function esc(s) {
  return String(s == null ? '' : s)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

function getTileChoice() {
  try { return localStorage.getItem(TILE_KEY) || TILE_DEFAULT; } catch { return TILE_DEFAULT; }
}

export function createMap(state, mountId = 'khoj-map') {
  const CAMPUS = [window.KHOJ.campus.lat, window.KHOJ.campus.lng];
  const PAYLOAD = window.KHOJ.listings;

  let mapInstance = null;
  let currentTileLayer = null;
  let markerLayer = null;
  const markerByUrl = new Map();

  function applyTile(key) {
    if (!mapInstance) return;
    const cfg = TILE_PROVIDERS[key] || TILE_PROVIDERS[TILE_DEFAULT];
    if (currentTileLayer) currentTileLayer.remove();
    const opts = { attribution: cfg.attribution, maxZoom: cfg.maxZoom };
    if (cfg.subdomains) opts.subdomains = cfg.subdomains;
    currentTileLayer = L.tileLayer(cfg.url, opts).addTo(mapInstance);
  }

  function setupTileSelects() {
    const choice = getTileChoice();
    document.querySelectorAll('[data-tile-select]').forEach(sel => {
      sel.innerHTML = Object.entries(TILE_PROVIDERS).map(([k, p]) =>
        `<option value="${k}"${k === choice ? ' selected' : ''}>${p.label}</option>`).join('');
      sel.addEventListener('change', () => {
        try { localStorage.setItem(TILE_KEY, sel.value); } catch {}
        applyTile(sel.value);
        document.querySelectorAll('[data-tile-select]').forEach(s => {
          if (s !== sel) s.value = sel.value;
        });
      });
    });
  }

  function drawDistanceRings() {
    RING_MILES.forEach(mi => {
      L.circle(CAMPUS, {
        radius: mi * METERS_PER_MILE,
        color: '#8C2026', weight: 1, opacity: 0.32,
        dashArray: '4 6', fill: false, interactive: false,
      }).addTo(mapInstance);
      const dlat = (mi * METERS_PER_MILE) / 111000;
      L.marker([CAMPUS[0] + dlat, CAMPUS[1]], {
        icon: L.divIcon({
          className: 'ring-label',
          html: `${mi} mi`,
          iconSize: [40, 14],
          iconAnchor: [20, 7],
        }),
        interactive: false,
        zIndexOffset: -500,
      }).addTo(mapInstance);
    });
  }

  function refreshMapMarkers() {
    if (markerLayer) markerLayer.remove();
    markerLayer = L.layerGroup().addTo(mapInstance);
    markerByUrl.clear();

    PAYLOAD.forEach(l => {
      if (l.lat == null || l.lng == null) return;
      const score = l.score ?? 0;
      const tier = score < 0.4 ? 'low' : score < 0.7 ? 'mid' : 'high';
      const icon = L.divIcon({
        className: 'khoj-pin',
        html: `<span class="khoj-pin-dot" data-score-tier="${tier}"></span>`,
        iconSize: [18, 18],
      });
      const marker = L.marker([l.lat, l.lng], { icon });
      const bedTxt = l.beds === 0 ? 'Studio'
                   : (l.beds != null ? l.beds + 'BR' : '?');
      marker.bindPopup(
        `<b>${esc(l.title)}</b><br>` +
        `${l.price != null ? '$' + l.price.toLocaleString() : '$?'} · ${esc(bedTxt)}<br>` +
        `<a href="${esc(l.url)}" target="_blank" rel="noopener">View →</a>`
      );
      marker.on('click', () => {
        state.set('selectedId', l.id);
      });
      marker.addTo(markerLayer);
      markerByUrl.set(l.id, marker);
    });
  }

  function syncFlags() {
    const starred = new Set(state.get('starred') || []);
    const hidden  = new Set(state.get('hidden')  || []);
    for (const [id, marker] of markerByUrl.entries()) {
      const el = marker.getElement()?.querySelector('.khoj-pin-dot');
      if (!el) continue;
      el.dataset.starred = starred.has(id);
      el.dataset.hidden  = hidden.has(id);
    }
  }

  // Mount the map
  const el = document.getElementById(mountId);
  if (!el) return { map: null, markerByUrl };

  mapInstance = L.map(mountId, { scrollWheelZoom: false }).setView(CAMPUS, 13);
  applyTile(getTileChoice());
  setupTileSelects();

  drawDistanceRings();

  L.marker(CAMPUS, {
    icon: L.divIcon({ className: 'khoj-pin is-campus', iconSize: [20, 20] }),
    zIndexOffset: 1000,
    interactive: false,
  }).addTo(mapInstance).bindTooltip('NYU Tandon · 370 Jay', {
    permanent: true,
    direction: 'right',
    offset: [14, 0],
    className: 'campus-tooltip',
  });

  refreshMapMarkers();

  const coords = PAYLOAD.filter(l => l.lat != null && l.lng != null).map(l => [l.lat, l.lng]);
  coords.push(CAMPUS);
  if (coords.length > 1) mapInstance.fitBounds(coords, { padding: [40, 40] });

  // Sync star/hide flags onto existing pins (no full redraw needed)
  state.subscribe('starred', syncFlags);
  state.subscribe('hidden',  syncFlags);
  syncFlags();

  return { map: mapInstance, markerByUrl };
}
