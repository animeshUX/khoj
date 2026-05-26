function esc(s) {
  return String(s == null ? '' : s)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

const ROUTE_COLOR = {
  F: '#FF6319', A: '#2850AD', C: '#2850AD', R: '#FCCC0A',
};

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
      return L.geoJSON(geo, {
        style: (f) => ({
          color: '#8C2026',
          fillOpacity: Math.min(0.5, (f.properties?.felonies || 0) / 400),
          weight: 1,
        }),
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

export function createOverlays(state, map) {
  const layers = {};   // name -> L.GeoJSON
  const loaded = {};   // name -> Promise<L.GeoJSON>

  async function load(name) {
    if (loaded[name]) return loaded[name];
    loaded[name] = fetch(REGISTRY[name].path)
      .then(r => r.json())
      .then(geo => {
        const layer = REGISTRY[name].build(geo);
        layers[name] = layer;
        return layer;
      });
    return loaded[name];
  }

  async function show(name) {
    const layer = await load(name);
    if (!map.map.hasLayer(layer)) {
      layer.addTo(map.map);
      if (name === 'commute_zone') layer.bringToBack();
    }
  }

  function hide(name) {
    if (layers[name] && map.map.hasLayer(layers[name])) map.map.removeLayer(layers[name]);
  }

  async function toggle(name, on) { on ? await show(name) : hide(name); }

  // Restore persisted layer state on init
  const initial = state.get('layers') || { subway_lines: true, subway_stations: true, commute_zone: true };
  state.set('layers', initial);
  for (const [name, on] of Object.entries(initial)) if (on) show(name);

  return { toggle, show, hide };
}
