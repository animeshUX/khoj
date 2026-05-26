
(function () {
  const PAYLOAD = JSON.parse(document.getElementById('payload').textContent);
  const MEDIANS = window.MEDIANS;
  const CAMPUS  = window.CAMPUS;
  const PREFIX = 'khoj.';
  const state = {
    starred: new Set(JSON.parse(localStorage.getItem(PREFIX + 'starred') || '[]')),
    hidden:  new Set(JSON.parse(localStorage.getItem(PREFIX + 'hidden')  || '[]')),
    notes:   JSON.parse(localStorage.getItem(PREFIX + 'notes') || '{}'),
    tab: 'inbox',
    bed: 'all',
    price: 'all',
    sort: 'score',
  };

  function persist() {
    localStorage.setItem(PREFIX + 'starred', JSON.stringify([...state.starred]));
    localStorage.setItem(PREFIX + 'hidden',  JSON.stringify([...state.hidden]));
    localStorage.setItem(PREFIX + 'notes',   JSON.stringify(state.notes));
  }

  function esc(s) {
    return String(s == null ? '' : s)
      .replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')
      .replace(/"/g,'&quot;').replace(/'/g,'&#39;');
  }

  function pad(n) { return String(n).padStart(3, '0'); }

  function applyFilters(list) {
    return list.filter(l => {
      if (state.bed !== 'all' && String(l.bedrooms) !== state.bed) return false;
      if (state.price === 'under1200' && (!l.price || l.price >= 1200)) return false;
      if (state.price === '1200to1500' && (!l.price || l.price < 1200 || l.price > 1500)) return false;
      return true;
    });
  }

  const SORTERS = {
    score:    (a, b) => (b.score || 0) - (a.score || 0),
    price:    (a, b) => (a.price || 9e9) - (b.price || 9e9),
    distance: (a, b) => (a.distance || 9e9) - (b.distance || 9e9),
    posted:   (a, b) => (b.posted || '0').localeCompare(a.posted || '0'),
  };

  function freshnessFor(posted) {
    if (!posted) return null;
    const [y, m, day] = posted.split('-').map(Number);
    const d = new Date(y, m - 1, day);
    const ageDays = (Date.now() - d.getTime()) / 86400000;
    if (ageDays < 1.2) return 'fresh';
    return null;
  }

  function priceAnomaly(price, bedrooms) {
    const median = MEDIANS[String(bedrooms)];
    if (!median || !price) return '';
    const ratio = price / median;
    if (ratio < 0.88) return `<span class="anomaly-low">↓ ${Math.round((1 - ratio) * 100)}% under median</span>`;
    if (ratio > 1.12) return `<span class="anomaly-high">↑ ${Math.round((ratio - 1) * 100)}% over median</span>`;
    return '';
  }

  function entryHTML(l) {
    const starred = state.starred.has(l.url);
    const hidden = state.hidden.has(l.url);
    const note = state.notes[l.url];
    const isExternal = !!l.source;       // non-Craigslist submissions
    const bedLabel = l.bedrooms === 0 ? 'Studio' : (l.bedrooms != null ? l.bedrooms + ' BR' : '?');
    const walking = l.walkMin ? `${l.walkMin} min walk` : '';
    const distance = l.distance != null ? `${l.distance.toFixed(2)} mi` : '?';
    const fresh = freshnessFor(l.posted);
    const numClass = 'entry-num ' + (l.score >= 40 ? 'score-high' : l.score >= 20 ? 'score-mid' : '');
    // Eyebrow label under the serial number: source domain for external,
    // Fresh/Score for Craigslist scrapes.
    const numMetaLabel = isExternal ? l.source : (fresh ? 'Fresh' : 'Score ' + l.score);
    const tags = (l.tags || []).map(t => `<span class="tag">${esc(t)}</span>`).join('');
    const anomaly = priceAnomaly(l.price, l.bedrooms);
    const ctaLabel = isExternal ? `View on ${esc(l.source)} →` : 'View on Craigslist →';
    const datePrefix = isExternal ? 'submitted ' : 'posted ';

    return `
      <li class="entry${hidden ? ' is-hidden' : ''}${starred ? ' is-starred' : ''}${isExternal ? ' is-external' : ''}" data-url="${esc(l.url)}">
        <div class="${numClass}">
          ${pad(l.n)}
          <div class="entry-num-meta${fresh && !isExternal ? ' fresh' : ''}${isExternal ? ' external' : ''}">${esc(numMetaLabel)}</div>
        </div>
        <div class="entry-body">
          <div class="entry-meta">
            <span class="price">${l.price != null ? '$' + l.price.toLocaleString() : '$?'}</span>
            ${esc(bedLabel)}
            <span class="sep">·</span>${esc(distance)}${walking ? ' (' + esc(walking) + ')' : ''}
            <span class="sep">·</span>${esc(l.neighborhood || 'Brooklyn')}
            <span class="sep">·</span>${datePrefix}${esc(l.postedRel || '?')}
            ${anomaly ? '<span class="sep">·</span>' + anomaly : ''}
          </div>
          <h2 class="entry-title"><a href="${esc(l.url)}" target="_blank" rel="noopener">${esc(l.title)}</a></h2>
          ${l.description ? `<p class="entry-desc">${esc(l.description)}</p>` : ''}
          ${tags ? `<div class="entry-tags">${tags}</div>` : ''}
          ${note ? `<div class="note-display">${esc(note)}</div>` : ''}
          <div class="entry-actions">
            <a class="act act-primary" href="${esc(l.url)}" target="_blank" rel="noopener">${ctaLabel}</a>
            <button class="act act-star${starred ? ' starred' : ''}" data-act="star">★ ${starred ? 'Starred' : 'Star'}</button>
            <button class="act" data-act="hide">${hidden ? 'Restore' : 'Hide'}</button>
            <button class="act" data-act="note">${note ? '✎ Edit Note' : '✎ Note'}</button>
          </div>
          <div class="note-area">
            <textarea placeholder="What stood out about this listing?">${esc(note || '')}</textarea>
            <div class="note-area-actions">
              <button class="act act-primary" data-act="save-note">Save</button>
              <button class="act" data-act="cancel-note">Cancel</button>
              ${note ? '<button class="act" data-act="delete-note">Delete</button>' : ''}
            </div>
          </div>
        </div>
      </li>
    `;
  }

  function render() {
    // Tab state
    document.querySelectorAll('.tab').forEach(t => t.classList.toggle('active', t.dataset.tab === state.tab));
    document.querySelectorAll('.view').forEach(v => v.classList.toggle('active', v.id === 'view-' + state.tab));

    // Header counts
    const visible = PAYLOAD.filter(l => !state.hidden.has(l.url)).length;
    document.getElementById('inbox-count').textContent = visible;
    document.getElementById('short-count').textContent = state.starred.size;
    document.getElementById('shortlist-stat').textContent = state.starred.size;

    if (state.tab === 'inbox') {
      const list = applyFilters(PAYLOAD.filter(l => !state.hidden.has(l.url)));
      list.sort(SORTERS[state.sort] || SORTERS.score);
      document.getElementById('listings').innerHTML =
        list.length ? list.map(entryHTML).join('')
                    : '<p class="empty">No listings match the current filters.</p>';
    } else if (state.tab === 'shortlist') {
      const list = applyFilters(PAYLOAD.filter(l => state.starred.has(l.url)));
      list.sort(SORTERS[state.sort] || SORTERS.score);
      const el = document.getElementById('shortlist-listings');
      const empty = document.getElementById('shortlist-empty');
      if (list.length === 0) {
        el.innerHTML = '';
        empty.style.display = 'block';
      } else {
        el.innerHTML = list.map(entryHTML).join('');
        empty.style.display = 'none';
      }
    }
    // Keep the live map's markers in sync with star/hide state on every render
    refreshMapMarkers();
  }

  // ------- Map -----------------------------------------------------------
  // Two possible mount points:
  //   #map-side : persistent right-rail panel, mounted on page load (desktop only)
  //   #map      : full-width view under the Map tab (mobile/back-compat)
  // We mount whichever element is in the DOM and visible. markerByUrl is shared
  // so hover/click highlighting Just Works regardless of which mount is live.
  let mapInstance = null;
  let mountedAt = null;            // 'map-side' | 'map'
  const markerByUrl = new Map();   // url → Leaflet marker

  // Tile providers — all free, no API key. Picked for utility navigating NYC:
  // Streets for orientation, Minimal so pins pop, Satellite for what the block
  // actually looks like, Transit because the train is how you'll actually get
  // to campus. Selection persists in localStorage so it survives refreshes.
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
  let currentTileLayer = null;

  function getTileChoice() {
    try { return localStorage.getItem(TILE_KEY) || TILE_DEFAULT; } catch { return TILE_DEFAULT; }
  }
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

  function mountMap(targetId) {
    if (mapInstance && mountedAt === targetId) { refreshMapMarkers(); return; }
    if (mapInstance) { mapInstance.remove(); markerByUrl.clear(); currentTileLayer = null; }
    const el = document.getElementById(targetId);
    if (!el) return;
    mountedAt = targetId;
    mapInstance = L.map(targetId, { scrollWheelZoom: false }).setView(CAMPUS, 13);
    applyTile(getTileChoice());

    drawDistanceRings();
    loadStaticLayers();  // commute zone + subway lines + stations (async, non-blocking)

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
  }

  // ------- Static layers: rings, commute zone, subway lines + stations --
  const METERS_PER_MILE = 1609.344;
  const RING_MILES = [1, 2, 3, 4];
  // MTA service colors. We only color the lines that hit Jay St-MetroTech.
  const ROUTE_COLOR = {
    F: '#FF6319', A: '#2850AD', C: '#2850AD', R: '#FCCC0A',
  };

  function drawDistanceRings() {
    RING_MILES.forEach(mi => {
      L.circle(CAMPUS, {
        radius: mi * METERS_PER_MILE,
        color: '#8C2026', weight: 1, opacity: 0.32,
        dashArray: '4 6', fill: false, interactive: false,
      }).addTo(mapInstance);
      // Label at 12 o'clock (north) on the ring
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
    // Order matters: zone first (bottom), then lines, then stations.
    // After all layers add, bring listing markers to front.
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
          // Find first colored route this station serves; otherwise muted gray
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

  // Layers the user can flip on/off via L.control.layers — they're NOT added to
  // the map by default; the control just registers them so the brother can pick.
  function loadToggleableOverlays() {
    // Create control upfront so async layers can register as they arrive
    const control = L.control.layers(null, {}, {
      collapsed: true, position: 'topright', sortLayers: false,
    }).addTo(mapInstance);

    // --- Neighborhoods + 90-day 311 noise complaints ---
    fetch('data/nta-noise.geojson').then(r => r.ok && r.json()).then(geo => {
      if (!geo || !mapInstance) return;

      // Compute the upper bound of noise density for color scaling. We use
      // 90th percentile (not max) so a few outliers don't blow out the gradient.
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

    // --- Parks ---
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

  let markerLayer = null;
  function refreshMapMarkers() {
    if (!mapInstance) return;
    if (markerLayer) markerLayer.remove();
    markerLayer = L.layerGroup().addTo(mapInstance);
    markerByUrl.clear();
    PAYLOAD.forEach(l => {
      if (l.lat == null || l.lng == null) return;
      const cls = state.hidden.has(l.url) ? 'is-hidden'
                : state.starred.has(l.url) ? 'is-starred'
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
      marker.on('click', () => focusEntry(l.url, { scroll: true }));
      marker.addTo(markerLayer);
      markerByUrl.set(l.url, marker);
    });
  }

  // ------- Linked entry ↔ pin highlight ---------------------------------
  let activeUrl = null;
  function setActive(url, opts) {
    opts = opts || {};
    if (activeUrl === url) return;
    // clear previous
    if (activeUrl) {
      document.querySelectorAll('.entry.is-active').forEach(e => e.classList.remove('is-active'));
      const prev = markerByUrl.get(activeUrl);
      if (prev) {
        const cls = prev.getElement && prev.getElement();
        if (cls) cls.classList.remove('is-active');
      }
    }
    activeUrl = url;
    if (!url) return;
    document.querySelectorAll(`.entry[data-url="${cssEscape(url)}"]`).forEach(e => e.classList.add('is-active'));
    const m = markerByUrl.get(url);
    if (m) {
      const el = m.getElement && m.getElement();
      if (el) el.classList.add('is-active');
      if (opts.pan && mapInstance) mapInstance.panTo(m.getLatLng(), { animate: true });
      if (opts.openPopup) m.openPopup();
    }
  }

  function focusEntry(url, opts) {
    opts = opts || {};
    setActive(url, { pan: true, openPopup: true });
    if (opts.scroll) {
      const el = document.querySelector(`.entry[data-url="${cssEscape(url)}"]`);
      if (el) el.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
  }

  function cssEscape(s) {
    return String(s).replace(/(["\\])/g, '\\$1');
  }

  // ------- Event wiring --------------------------------------------------
  document.querySelectorAll('.tab').forEach(tab => {
    tab.addEventListener('click', () => { state.tab = tab.dataset.tab; render(); });
  });

  document.querySelectorAll('.chip-group').forEach(group => {
    const filterName = group.dataset.filter;
    group.querySelectorAll('.chip').forEach(chip => {
      chip.addEventListener('click', () => {
        group.querySelectorAll('.chip').forEach(c => c.classList.remove('active'));
        chip.classList.add('active');
        state[filterName] = chip.dataset.val;
        render();
      });
    });
  });

  document.getElementById('sort').addEventListener('change', e => {
    state.sort = e.target.value;
    render();
  });

  document.addEventListener('click', e => {
    const btn = e.target.closest('[data-act]');
    if (btn) {
      const entry = btn.closest('.entry');
      if (!entry) return;
      const url = entry.dataset.url;
      const act = btn.dataset.act;
      const toggle = (set) => set.has(url) ? set.delete(url) : set.add(url);
      if (act === 'star') {
        toggle(state.starred); persist(); render();
      } else if (act === 'hide') {
        toggle(state.hidden); persist(); render();
      } else if (act === 'note') {
        entry.querySelector('.note-area').classList.toggle('open');
      } else if (act === 'save-note') {
        const txt = entry.querySelector('textarea').value.trim();
        if (txt) state.notes[url] = txt; else delete state.notes[url];
        persist(); render();
      } else if (act === 'cancel-note') {
        entry.querySelector('.note-area').classList.remove('open');
      } else if (act === 'delete-note') {
        delete state.notes[url];
        persist(); render();
      }
      return;
    }
    // Click anywhere else inside an entry: highlight + pan the map to that listing.
    // (Clicks on action buttons are handled above and return early so this won't fire.)
    const entry = e.target.closest('.entry');
    if (entry && entry.dataset.url) {
      setActive(entry.dataset.url, { pan: true });
    }
  });

  // Hover an entry → highlight its pin (no pan, no popup — that's reserved for click).
  document.addEventListener('mouseover', e => {
    const entry = e.target.closest('.entry');
    if (entry && entry.dataset.url) setActive(entry.dataset.url);
  });

  // ------- Initial paint + map mount ------------------------------------
  render();
  // Desktop: sticky right-rail map (#map-side). Mobile: inline map below the
  // list (#map-mobile). Whichever is visible wins; the other is display:none.
  const sidePanel = document.getElementById('map-panel');
  if (sidePanel && getComputedStyle(sidePanel).display !== 'none') {
    mountMap('map-side');
  } else if (document.getElementById('map-mobile')) {
    mountMap('map-mobile');
  }
  setupTileSelects();
})();
