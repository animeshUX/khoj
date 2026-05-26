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
const ROUTE_COLOR = {
  F: '#FF6319', A: '#2850AD', C: '#2850AD', R: '#FCCC0A',
};

function esc(s) {
  return String(s == null ? '' : s)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

function pad(n) { return String(n).padStart(3, '0'); }

function getTileChoice() {
  try { return localStorage.getItem(TILE_KEY) || TILE_DEFAULT; } catch { return TILE_DEFAULT; }
}

export function createMap(state, mountId = 'khoj-map') {
  const CAMPUS = window.CAMPUS;
  const PAYLOAD = JSON.parse(document.getElementById('payload').textContent);

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

  function loadStaticLayers() {
    fetch('data/commute-zone.geojson').then(r => r.ok && r.json()).then(geo => {
      if (!geo || !mapInstance) return;
      L.geoJSON(geo, {
        style: {
          color: '#8C2026', weight: 1.2, opacity: 0.6, dashArray: '6 4',
          fillColor: '#8C2026', fillOpacity: 0.055,
        },
        interactive: false,
      }).addTo(mapInstance).bringToBack();
    }).catch(() => {});

    fetch('data/subway-lines.geojson').then(r => r.ok && r.json()).then(geo => {
      if (!geo || !mapInstance) return;
      L.geoJSON(geo, {
        style: { color: '#1A1612', weight: 1.4, opacity: 0.22 },
        interactive: false,
      }).addTo(mapInstance);
      if (markerLayer) markerLayer.bringToFront();
    }).catch(() => {});

    fetch('data/subway-stations.geojson').then(r => r.ok && r.json()).then(geo => {
      if (!geo || !mapInstance) return;
      L.geoJSON(geo, {
        pointToLayer: (feat, latlng) => {
          const routes = (feat.properties.daytime_routes || '').split(' ').filter(Boolean);
          const color = routes.map(r => ROUTE_COLOR[r]).find(Boolean);
          const isRelevant = !!color;
          return L.circleMarker(latlng, {
            radius: isRelevant ? 3.5 : 2,
            color: '#fff', weight: 0.7,
            fillColor: color || '#93857A',
            fillOpacity: isRelevant ? 0.92 : 0.5,
            interactive: isRelevant,
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
      }).addTo(mapInstance);
      if (markerLayer) markerLayer.bringToFront();
    }).catch(() => {});

    loadToggleableOverlays();
  }

  function loadToggleableOverlays() {
    const control = L.control.layers(null, {}, {
      collapsed: true, position: 'topright', sortLayers: false,
    }).addTo(mapInstance);

    fetch('data/nta-noise.geojson').then(r => r.ok && r.json()).then(geo => {
      if (!geo || !mapInstance) return;
      const dens = geo.features.map(f => f.properties.noise_per_sqmi).sort((a, b) => a - b);
      const p90 = dens[Math.floor(dens.length * 0.9)] || 1;

      const ntaOutlines = L.geoJSON(geo, {
        style: { color: '#1A1612', weight: 0.7, opacity: 0.35, fillOpacity: 0 },
        onEachFeature: (feat, layer) => {
          layer.bindTooltip(esc(feat.properties.name), {
            sticky: true, className: 'station-tooltip', direction: 'top',
          });
        },
      });

      const noiseLayer = L.geoJSON(geo, {
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

      control.addOverlay(ntaOutlines, '🏘 Neighborhood borders');
      control.addOverlay(noiseLayer, '🔊 311 noise (last 90 days)');
    }).catch(() => {});

    fetch('data/parks.geojson').then(r => r.ok && r.json()).then(geo => {
      if (!geo || !mapInstance) return;
      const parksLayer = L.geoJSON(geo, {
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
      control.addOverlay(parksLayer, '🌳 Parks');
    }).catch(() => {});
  }

  function refreshMapMarkers() {
    if (markerLayer) markerLayer.remove();
    markerLayer = L.layerGroup().addTo(mapInstance);
    markerByUrl.clear();

    const starred = state.get('starred') || new Set();
    const hidden  = state.get('hidden')  || new Set();

    PAYLOAD.forEach(l => {
      if (l.lat == null || l.lng == null) return;
      const cls = hidden.has(l.url) ? 'is-hidden'
                : starred.has(l.url) ? 'is-starred'
                : '';
      const marker = L.marker([l.lat, l.lng], {
        icon: L.divIcon({ className: 'khoj-pin ' + cls, iconSize: [14, 14] }),
      });
      const bedTxt = l.bedrooms === 0 ? 'Studio'
                   : (l.bedrooms != null ? l.bedrooms + 'BR' : '?');
      const distTxt = l.distance != null ? l.distance.toFixed(2) + ' mi' : '? mi';
      marker.bindPopup(
        `<b>#${pad(l.n)} ${esc(l.title)}</b><br>` +
        `${l.price != null ? '$' + l.price.toLocaleString() : '$?'} · ${esc(bedTxt)} · ${esc(distTxt)}<br>` +
        `<a href="${esc(l.url)}" target="_blank" rel="noopener">View →</a>`
      );
      marker.on('click', () => {
        state.set('selectedId', l.url);
      });
      marker.addTo(markerLayer);
      markerByUrl.set(l.url, marker);
    });
  }

  // Mount the map
  const el = document.getElementById(mountId);
  if (!el) return { map: null, markerByUrl };

  mapInstance = L.map(mountId, { scrollWheelZoom: false }).setView(CAMPUS, 13);
  applyTile(getTileChoice());
  setupTileSelects();

  drawDistanceRings();
  loadStaticLayers();

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

  // Re-render markers when star/hide state changes
  state.subscribe('starred', () => refreshMapMarkers());
  state.subscribe('hidden',  () => refreshMapMarkers());

  return { map: mapInstance, markerByUrl, refreshMapMarkers };
}
