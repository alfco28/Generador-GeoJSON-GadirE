    'use strict';
    // -----------------------------------------------------------------------
    // Layer configuration. Internal keys are English, but the exported file
    // names stay 'campus.kml' and 'edificios.kml' (and Document names
    // 'Campus'/'Edificios') so the output is a drop-in replacement for the
    // files the generator (generador_map_data.py) reads with geopandas.
    // -----------------------------------------------------------------------
    const LAYERS = {
      buildings: { kmlFile: 'edificios.kml', docName: 'Edificios',
                   style: { color: '#e11d48', fillColor: '#e11d48', fillOpacity: 0.30, weight: 2 },
                   codePad: 2,   // codes are 1-based: '01', '02', … (like edificio_codes)
                   defaultName: 'Building' },
      campus:    { kmlFile: 'campus.kml', docName: 'Campus',
                   style: { color: '#2563eb', fillColor: '#2563eb', fillOpacity: 0.18, weight: 3 },
                   codePad: 1,   // codes are 0-based: '0', '1', … (like campus_codes)
                   defaultName: 'Campus' },
    };
    const LAYERTYPES = Object.keys(LAYERS);
    const STORAGE_KEY = 'kml-editor-v2';
    const OVERLAP_AREA_EPSILON = 0.01; // m²; below this, shared walls do not count
    const HISTORY_LIMIT = 50;

    // ------------------------------ Map ------------------------------
    const map = L.map('map').setView([36.5295, -6.2919], 14);
    L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxZoom: 19,
      attribution: '&copy; OpenStreetMap',
    }).addTo(map);

    // Two polygon layers: shown overlaid, or each on its own via the layer
    // control. A "View" heading is injected so the checkboxes above are
    // self-explanatory.
    const layerGroups = {
      buildings: L.layerGroup().addTo(map),
      campus: L.layerGroup().addTo(map),
    };
    const viewControl = L.control.layers(null, {
      'Campuses': layerGroups.campus,
      'Buildings': layerGroups.buildings,
    }, { position: 'topright', collapsed: false }).addTo(map);
    const viewList = viewControl.getContainer().querySelector('.leaflet-control-layers-list');
    const viewTitle = document.createElement('div');
    viewTitle.className = 'layers-title';
    viewTitle.textContent = 'View';
    viewList.prepend(viewTitle);

    // ------------------------------ Drawing tools ------------------------------
    map.pm.addControls({
      position: 'topleft',
      drawMarker: false, drawCircleMarker: false, drawPolyline: false,
      drawRectangle: false, drawCircle: false, drawText: false,
      cutPolygon: false, rotateMode: false, dragMode: false,
      editMode: true, removalMode: true,
      snappingOption: true, // magnet button: toggles snapping when it gets in the way
    });
    map.pm.setLang('en');

    // Snapping configuration, checked against the Geoman 2.20.0 source:
    //  - snappable/snapDistance(20 px)/snapVertex/snapSegment: the hint
    //    marker snaps to vertices and edges of every layer; this is also
    //    what makes "click the first vertex to finish" work (a click within
    //    20 px of the first vertex marker completes the shape).
    //  - allowSelfIntersection: false forbids the classic "four-corner
    //    candy" while drawing (the outline turns red and the click is
    //    ignored), so invalid rings cannot even be drawn.
    //  - Holding Alt temporarily disables snapping (documented), and the
    //    magnet toolbar button (snappingOption) switches it off entirely.
    map.pm.setGlobalOptions({
      snappable: true, snapDistance: 20,
      snapSegment: true, snapVertex: true,
      allowSelfIntersection: false,
      continueDrawing: false,
      finishOnEnter: true,      // Enter also finishes the current drawing
      exitModeOnEscape: true,    // Escape leaves the active mode
    });

    // Which layer receives the next drawn polygon.
    let activeType = 'buildings';
    const segBuildings = document.getElementById('segBuildings');
    const segCampuses = document.getElementById('segCampuses');
    segBuildings.onclick = () => { activeType = 'buildings'; markSegment(); stopHiddenDraw(true); };
    segCampuses.onclick = () => { activeType = 'campus'; markSegment(); stopHiddenDraw(true); };
    function markSegment() {
      segBuildings.classList.toggle('active', activeType === 'buildings');
      segCampuses.classList.toggle('active', activeType === 'campus');
    }

    // ------------------------------ Layer visibility ------------------------------
    // Drawing into a hidden layer is blocked: a polygon that turns invisible
    // the instant it is finished is confusing. The "View" control (top right)
    // toggles the overlay layer groups, so it drives this guard too.
    function layerIsVisible(type) {
      return map.hasLayer(layerGroups[type]);
    }

    function drawingActive() {
      return map.pm.Draw.Polygon.enabled();
    }

    // Stops the draw mode if the active layer is hidden. With notify=true the
    // user gets an explanation (draw button pressed); silently when the layer
    // has just been unticked (he knows what he just did).
    function stopHiddenDraw(notify) {
      if (!drawingActive() || layerIsVisible(activeType)) return;
      map.pm.Draw.Polygon.disable();
      if (notify) {
        alert(`The ${activeType === 'buildings' ? 'Buildings' : 'Campuses'} layer is hidden. ` +
              'Tick it in the "View" control (top right) to draw on it.');
      }
    }

    // Fires whenever the polygon draw mode is toggled on or off.
    map.on('pm:globaldrawmodetoggled', (e) => {
      if (e.enabled && e.shape === 'Polygon') stopHiddenDraw(true);
    });
    // Fires when a layer control checkbox is unticked.
    map.on('overlayremove', (e) => {
      if (e.layer === layerGroups[activeType]) stopHiddenDraw(false);
    });

    // ------------------------------ Geometry validation ------------------------------
    // Rule: every polygon must be a simple ring (its outline may not cross
    // itself — no "four-corner candy" shapes). Convexity is NOT required:
    // L-shaped or star-shaped buildings are perfectly valid. Geoman already
    // blocks self-intersections live while drawing (allowSelfIntersection:
    // false), so a new drawing can only fail here through an import or an
    // exotic edge case; isSimpleRing is the final gate.
    function ringFromLayer(layer) {
      return layer.getLatLngs()[0].map(ll => ({ lat: ll.lat, lng: ll.lng }));
    }

    // Signed turn direction at vertex b for the path a -> b -> c (degree units).
    function crossAt(a, b, c) {
      return (b.lng - a.lng) * (c.lat - b.lat) - (b.lat - a.lat) * (c.lng - b.lng);
    }

    // Simple ring: no two non-adjacent edges properly cross each other.
    // (Collinear overlaps of two edges are a rare degenerate case and are
    // not detected; Geoman already blocks self-intersections while drawing.)
    function isSimpleRing(pts) {
      const n = pts.length;
      function segsIntersect(p1, p2, p3, p4) {
        const d1 = crossAt(p3, p4, p1), d2 = crossAt(p3, p4, p2);
        const d3 = crossAt(p1, p2, p3), d4 = crossAt(p1, p2, p4);
        return ((d1 > 0 && d2 < 0) || (d1 < 0 && d2 > 0)) &&
               ((d3 > 0 && d4 < 0) || (d3 < 0 && d4 > 0));
      }
      for (let i = 0; i < n; i++) {
        for (let j = i + 2; j < n; j++) {
          if (i === 0 && j === n - 1) continue; // first and last edges share a vertex
          if (segsIntersect(pts[i], pts[(i + 1) % n], pts[j], pts[(j + 1) % n])) return false;
        }
      }
      return true;
    }

    // ------------------------------ State ------------------------------
    const polygons = { buildings: [], campus: [] }; // [{ layer, name }] in display order
    const overlapIdx = { buildings: new Set(), campus: new Set() };

    function codeOf(type, index) {
      const pad = LAYERS[type].codePad;
      return String(index + (pad === 2 ? 1 : 0)).padStart(pad, '0');
    }

    function uniqueDefaultName(type) {
      const used = new Set(polygons[type].map(p => p.name));
      let n = 1;
      while (used.has(`${LAYERS[type].defaultName} ${n}`)) n++;
      return `${LAYERS[type].defaultName} ${n}`;
    }

    function registerPolygon(layer, type, name) {
      layer.setStyle(LAYERS[type].style);
      layer.feature = { type: 'Feature', properties: { name: name || '' } };
      layer.pm.enable({ allowSelfIntersection: false, snappable: true }); // draggable vertices
      // Hovering a polygon shows its name; clicking it highlights its row
      // in the sidebar (see highlightInList).
      layer.bindTooltip(name || '…', { sticky: true, direction: 'top' });
      layer.on('click', () => highlightInList(type, layer));
      const entry = { layer, name: name || '', geo: null }; // geo: cached GeoJSON for overlaps
      // pm:edit is a LAYER event (a map-level pm:edit does not exist). It
      // fires in bursts while vertices are dragged, so the (expensive)
      // re-render is debounced and the geometry cache is invalidated here.
      layer.on('pm:edit', () => {
        entry.geo = null;        // geometry changed: drop the cached GeoJSON
        scheduleRender();
        scheduleCommit();
      });
      polygons[type].push(entry);
    }

    function setName(type, i, name) {
      polygons[type][i].name = name;
      polygons[type][i].layer.feature.properties.name = name;
      polygons[type][i].layer.setTooltipContent(name || '…'); // keep the hover tooltip in sync
      scheduleSave();
    }

    function deletePolygon(type, i) {
      // Remove from the layer GROUP, not just the map: map.removeLayer does
      // nothing when the group is hidden (the polygon is not on the map), and
      // even with the group visible it leaves the layer inside the group —
      // re-ticking "View" would then resurrect deleted polygons as ghosts.
      layerGroups[type].removeLayer(polygons[type][i].layer);
      polygons[type].splice(i, 1);
      renderAll();
      commitHistory();
    }

    // ------------------------------ Overlaps ------------------------------
    // Two buildings may not overlap; two campuses may not overlap.
    // A building inside a campus is fine (that is even the expected situation).
    // Cached GeoJSON per entry: re-serialising every polygon on every overlap
    // check is O(n) work we can skip while the geometry has not changed.
    function geoOf(entry) {
      return entry.geo || (entry.geo = entry.layer.toGeoJSON());
    }

    function computeOverlaps(type) {
      const list = polygons[type];
      const overlapping = new Set();
      for (let i = 0; i < list.length; i++) {
        for (let j = i + 1; j < list.length; j++) {
          let inter = null;
          try {
            inter = turf.intersect(geoOf(list[i]), geoOf(list[j]));
          } catch (e) { inter = null; }
          if (inter !== null && turf.area(inter) > OVERLAP_AREA_EPSILON) {
            overlapping.add(i);
            overlapping.add(j);
          }
        }
      }
      overlapIdx[type] = overlapping;
      // Make overlaps visible on the map too (dashed outline).
      list.forEach((p, i) => p.layer.setStyle({ dashArray: overlapping.has(i) ? '6 4' : null }));
    }

    // ------------------------------ Issues / badges ------------------------------
    function issuesFor(type) {
      const count = {};
      polygons[type].forEach(p => { count[p.name] = (count[p.name] || 0) + 1; });
      const issues = new Map();
      polygons[type].forEach((p, i) => {
        const list = [];
        if (!p.name) list.push('No name');
        if (p.name && count[p.name] > 1) list.push('Duplicate name');
        if (overlapIdx[type].has(i)) list.push('Overlapping');
        const ring = ringFromLayer(p.layer);
        if (!isSimpleRing(ring)) list.push('Self-crossing');
        if (list.length) issues.set(i, list);
      });
      return issues;
    }

    // ------------------------------ Sidebar ------------------------------
    const $lists = {
      buildings: document.getElementById('listBuildings'),
      campus: document.getElementById('listCampuses'),
    };
    const $counts = {
      buildings: document.getElementById('nBuildings'),
      campus: document.getElementById('nCampuses'),
    };

    function renderList(type) {
      const $ul = $lists[type];
      $ul.innerHTML = '';
      $counts[type].textContent = `(${polygons[type].length})`;

      if (!polygons[type].length) {
        const empty = document.createElement('div');
        empty.className = 'empty';
        empty.textContent = 'No polygons yet.';
        $ul.appendChild(empty);
        return;
      }

      polygons[type].forEach((p, i) => {
        const div = document.createElement('div');
        div.className = 'item';
        const row = document.createElement('div');
        row.className = 'row';

        // Drag handle: only the grip starts the drag, so the text input
        // keeps working normally. Pointer Events make it work with mouse,
        // touch and pen alike.
        const grip = document.createElement('span');
        grip.className = 'grip';
        grip.textContent = '⠿';
        grip.title = 'Drag to reorder';
        row.appendChild(grip);

        // Numeric code derived from the current position in the list.
        const code = document.createElement('span');
        code.className = 'code';
        code.title = 'Code from list order';
        code.textContent = codeOf(type, i);
        row.appendChild(code);

        const swatch = document.createElement('span');
        swatch.className = 'swatch';
        swatch.style.background = LAYERS[type].style.color;
        row.appendChild(swatch);

        const inp = document.createElement('input');
        inp.type = 'text';
        inp.value = p.name;
        inp.placeholder = type === 'campus' ? 'Campus name…' : 'Building name…';
        inp.oninput = () => {
          setName(type, i, inp.value);
          refreshBadges(type);           // cheap: no DOM rebuild while typing
        };
        inp.onchange = () => commitHistory(); // one history entry per finished rename
        row.appendChild(inp);

        const meta = document.createElement('span');
        meta.className = 'meta';
        meta.textContent = p.layer.getLatLngs()[0].length + ' verts';
        row.appendChild(meta);

        const zoom = document.createElement('button');
        zoom.className = 'mini'; zoom.title = 'Zoom to'; zoom.textContent = '⌖';
        zoom.onclick = () => map.fitBounds(p.layer.getBounds(), { padding: [30, 30] });
        row.appendChild(zoom);

        const del = document.createElement('button');
        del.className = 'mini del'; del.title = 'Delete'; del.textContent = '✕';
        del.onclick = () => deletePolygon(type, i);
        row.appendChild(del);

        div.appendChild(row);

        const badges = document.createElement('div');
        badges.className = 'badges';
        div.appendChild(badges);

        // Hovering a row emphasises its polygon on the map (thicker outline).
        div.addEventListener('mouseenter', () => p.layer.setStyle({ weight: 5 }));
        div.addEventListener('mouseleave', () =>
          p.layer.setStyle({ weight: LAYERS[type].style.weight }));

        attachDragHandlers(div, grip, type, i);
        $ul.appendChild(div);
      });
      refreshBadges(type);
    }

    // Drag-and-drop reordering with Pointer Events: mouse, touch and pen all
    // behave the same (the HTML5 drag-and-drop API is mouse-only). The code
    // of every polygon is its position in the list, so dropping an item
    // somewhere else renumbers everything.
    let ptrDrag = null; // { type, from, div, id, target }

    function dropTargetAt(type, y) {
      // Which item row is under the pointer, and above/below its midline?
      const items = $lists[type].children;
      for (let i = 0; i < items.length; i++) {
        const r = items[i].getBoundingClientRect();
        if (y >= r.top - 6 && y <= r.bottom + 6) {
          return { i, before: y < r.top + r.height / 2 };
        }
      }
      return null;
    }

    function attachDragHandlers(div, grip, type, i) {
      grip.addEventListener('pointerdown', (e) => {
        if (e.pointerType === 'mouse' && e.button !== 0) return;
        e.preventDefault();              // keep focus and click out of the drag
        grip.setPointerCapture(e.pointerId); // all move/up events come to us
        ptrDrag = { type, from: i, div, id: e.pointerId, target: null };
        div.classList.add('dragging');
      });
      grip.addEventListener('pointermove', (e) => {
        if (!ptrDrag || ptrDrag.id !== e.pointerId) return;
        const target = dropTargetAt(type, e.clientY);
        const same = ptrDrag.target && target &&
          ptrDrag.target.i === target.i && ptrDrag.target.before === target.before;
        if (same || (!ptrDrag.target && !target)) return;
        clearDropMarks();
        ptrDrag.target = target;
        if (target) {
          const el = $lists[type].children[target.i];
          el.classList.add(target.before ? 'drop-above' : 'drop-below');
        }
      });
      const finish = (e) => {
        if (!ptrDrag || (e && e.pointerId !== ptrDrag.id)) return;
        const d = ptrDrag;
        ptrDrag = null;
        clearDropMarks();
        d.div.classList.remove('dragging');
        if (!d.target) return;          // a plain click on the grip: no-op
        applyReorder(d.type, d.from, d.target);
      };
      grip.addEventListener('pointerup', finish);
      grip.addEventListener('pointercancel', finish);
    }

    // Same splice math as the old HTML5 drop handler (unit-tested).
    function applyReorder(type, from, target) {
      if (from === target.i) return;   // dropping onto its own slot: no-op
      let insertAt = target.before ? target.i : target.i + 1;
      const [entry] = polygons[type].splice(from, 1);
      if (from < insertAt) insertAt--;
      polygons[type].splice(insertAt, 0, entry);
      renderAll();
      commitHistory();
    }

    function clearDropMarks() {
      document.querySelectorAll('.item.drop-above, .item.drop-below')
        .forEach(el => el.classList.remove('drop-above', 'drop-below'));
    }

    function refreshBadges(type) {
      const issues = issuesFor(type);
      $lists[type].querySelectorAll('.item').forEach((div, i) => {
        div.querySelector('.badges').innerHTML =
          (issues.get(i) || []).map(t => `<span class="badge red">${t}</span>`).join('');
        div.querySelector('input').classList.toggle('invalid', issues.has(i));
      });
    }

    function renderAll() {
      LAYERTYPES.forEach(type => computeOverlaps(type));
      renderList('buildings');
      renderList('campus');
      scheduleSave();
    }

    // Clicking a polygon on the map flashes and scrolls to its row.
    function highlightInList(type, layer) {
      if (map.pm.globalDrawModeEnabled()) return; // drawing in progress: ignore
      const i = polygons[type].findIndex(p => p.layer === layer);
      if (i < 0) return;
      const div = $lists[type].children[i];
      if (!div || !div.classList.contains('item')) return;
      div.classList.remove('flash');
      void div.offsetWidth;                     // restart the CSS transition
      div.classList.add('flash');
      clearTimeout(div._flashTimer);
      div._flashTimer = setTimeout(() => div.classList.remove('flash'), 1400);
      div.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
    }

    // ------------------------------ KML generation ------------------------------
    // Same layout as a Google My Maps export (StyleMap, tessellate, one
    // 'lon,lat,0' coordinate per line, closed rings), with coordinates
    // rounded to 6 decimals (≈ 11 cm), like the generator does on output.
    const MYMAPS_STYLE = `    <Style id="poly-000000-1200-77-nodesc-normal">
      <LineStyle>
        <color>ff000000</color>
        <width>1.2</width>
      </LineStyle>
      <PolyStyle>
        <color>4d000000</color>
        <fill>1</fill>
        <outline>1</outline>
      </PolyStyle>
      <BalloonStyle>
        <text><![CDATA[<h3>$[name]</h3>]]></text>
      </BalloonStyle>
    </Style>
    <Style id="poly-000000-1200-77-nodesc-highlight">
      <LineStyle>
        <color>ff000000</color>
        <width>1.8</width>
      </LineStyle>
      <PolyStyle>
        <color>4d000000</color>
        <fill>1</fill>
        <outline>1</outline>
      </PolyStyle>
      <BalloonStyle>
        <text><![CDATA[<h3>$[name]</h3>]]></text>
      </BalloonStyle>
    </Style>
    <StyleMap id="poly-000000-1200-77-nodesc">
      <Pair>
        <key>normal</key>
        <styleUrl>#poly-000000-1200-77-nodesc-normal</styleUrl>
      </Pair>
      <Pair>
        <key>highlight</key>
        <styleUrl>#poly-000000-1200-77-nodesc-highlight</styleUrl>
      </Pair>
    </StyleMap>`;

    const fmt6 = (v) => String(Math.round(v * 1e6) / 1e6);

    function placemarkKml(entry) {
      // toGeoJSON() gives [lon, lat] coordinates with the ring already closed,
      // exactly like a My Maps export.
      const ring = entry.layer.toGeoJSON().geometry.coordinates[0];
      const coords = ring.map(([lon, lat]) => `              ${fmt6(lon)},${fmt6(lat)},0`).join('\n');
      return `    <Placemark>
      <name>${escXml(entry.name)}</name>
      <styleUrl>#poly-000000-1200-77-nodesc</styleUrl>
      <Polygon>
        <outerBoundaryIs>
          <LinearRing>
            <tessellate>1</tessellate>
            <coordinates>
${coords}
            </coordinates>
          </LinearRing>
        </outerBoundaryIs>
      </Polygon>
    </Placemark>`;
    }

    function generateKml(type) {
      return `<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <name>${LAYERS[type].docName}</name>
${MYMAPS_STYLE}
${polygons[type].map(placemarkKml).join('\n')}
  </Document>
</kml>
`;
    }

    function escXml(s) {
      return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;')
                      .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
    }

    // Python dictionary of the codes in the current order, ready to paste into
    // the generator (campus_codes / edificio_codes style).
    function pythonCodes(type) {
      const dictName = type === 'campus' ? 'campus_codes' : 'edificio_codes';
      const lines = polygons[type].map((p, i) =>
        `    "${p.name.replace(/\\/g, '\\\\').replace(/"/g, '\\"')}": "${codeOf(type, i)}",`);
      return `${dictName} = {\n${lines.join('\n')}\n}\n`;
    }

    // ------------------------------ Download ------------------------------
    function download(fileName, text) {
      const blob = new Blob([text], { type: 'application/vnd.google-earth.kml+xml' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = fileName;
      a.click();
      // Revoke later: doing it right after click() can cancel the download
      // in some browsers before it grabs the blob.
      setTimeout(() => URL.revokeObjectURL(url), 5000);
    }

    // Issues are reported, but the user decides whether to export anyway.
    function confirmIssues(type) {
      const issues = issuesFor(type);
      if (!issues.size) return true;
      const summary = [...issues.values()].map(l => l.join(' + ')).join('; ');
      return confirm(`There are ${issues.size} polygons with problems:\n${summary}\n\nDownload anyway?`);
    }

    const $preview = document.getElementById('preview');
    $preview.onclick = () => { $preview.style.display = 'none'; };

    document.querySelectorAll('.actions button').forEach(btn => {
      btn.onclick = () => {
        const type = btn.dataset.layer;
        switch (btn.dataset.action) {
          case 'download':
            if (confirmIssues(type)) download(LAYERS[type].kmlFile, generateKml(type));
            break;
          case 'import':
            importFrom(type);
            break;
          case 'pycodes':
            copyPythonCodes(type, btn);
            break;
        }
      };
    });

    function copyPythonCodes(type, btn) {
      const snippet = pythonCodes(type);
      const old = btn.textContent;
      const done = (ok) => {
        if (ok) { btn.textContent = 'Copied!'; }
        else {  // fallback: show the snippet in the preview area
          $preview.textContent = snippet;
          $preview.style.display = 'block';
          btn.textContent = 'Shown below';
        }
        setTimeout(() => { btn.textContent = old; }, 1800);
      };
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(snippet)
          .then(() => done(true))
          .catch(() => done(false));
      } else done(false);
    }

    // ------------------------------ Import ------------------------------
    // Import an existing KML (e.g. the current generator files) to edit it
    // here: move vertices, rename, reorder, and export again. Multi-polygon
    // Placemarks are split into one entry per polygon (flagged if duplicated).
    const fileInput = document.getElementById('fileInput');
    let importType = 'buildings';
    function importFrom(type) { importType = type; fileInput.value = ''; fileInput.click(); }
    fileInput.onchange = () => {
      const f = fileInput.files[0];
      if (!f) return;
      const reader = new FileReader();
      reader.onload = () => importKml(String(reader.result), importType);
      reader.readAsText(f);
    };

    function importKml(text, type) {
      const doc = new DOMParser().parseFromString(text, 'application/xml');
      if (doc.querySelector('parsererror')) { alert('The file is not valid KML.'); return; }
      const imported = [];
      doc.querySelectorAll('Placemark').forEach(pm => {
        const name = (pm.querySelector('name')?.textContent.trim() || '');
        pm.querySelectorAll('Polygon').forEach(poly => {
          const coordsEl = poly.querySelector('outerBoundaryIs LinearRing coordinates');
          if (!coordsEl) return;
          const latlngs = coordsEl.textContent.trim().split(/\s+/).map(pair => {
            const [lon, lat] = pair.split(',').map(Number);
            if (!Number.isFinite(lat) || !Number.isFinite(lon)) return null; // bad pair
            return [lat, lon];
          }).filter(Boolean);
          if (latlngs.length < 4) return;
          // KML rings repeat the first coordinate at the end; Leaflet closes
          // rings on its own, so drop the duplicate to avoid a phantom vertex.
          const first = latlngs[0], last = latlngs[latlngs.length - 1];
          if (latlngs.length > 4 && first[0] === last[0] && first[1] === last[1]) latlngs.pop();
          const layer = L.polygon(latlngs);
          layerGroups[type].addLayer(layer);
          registerPolygon(layer, type, name);
          imported.push(layer);
        });
      });
      renderAll();
      commitHistory();
      if (imported.length) {
        const bounds = imported.map(l => l.getBounds()).reduce((a, b) => a.extend(b));
        map.fitBounds(bounds, { padding: [30, 30] });
      }
      alert(`${imported.length} polygon(s) imported into ${type === 'campus' ? 'Campuses' : 'Buildings'}.`);
    }

    // ------------------------------ Persistence ------------------------------
    // Saving serialises every polygon to GeoJSON, so bursts of small changes
    // (keystrokes in the name box, vertex drags) go through a short debounce
    // instead of hitting localStorage on every event.
    let saveTimer = null;
    function scheduleSave() {
      clearTimeout(saveTimer);
      saveTimer = setTimeout(saveState, 300);
    }

    function saveState() {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(serializeState()));
    }

    function serializeState() {
      const data = {};
      LAYERTYPES.forEach(type => {
        data[type] = polygons[type].map(p => p.layer.toGeoJSON());
      });
      return data;
    }

    function clearAll() {
      LAYERTYPES.forEach(type => {
        // Group-level removal too: otherwise undo/redo would resurrect the
        // polygons of a hidden layer when "View" ticks it back on (ghosts).
        polygons[type].forEach(p => layerGroups[type].removeLayer(p.layer));
        polygons[type] = [];
        overlapIdx[type] = new Set();
      });
    }

    function addFromData(data) {
      LAYERTYPES.forEach(type => {
        (data[type] || []).forEach(feat => {
          const name = (feat.properties && feat.properties.name) || '';
          L.geoJSON(feat).eachLayer(layer => {
            layerGroups[type].addLayer(layer);
            registerPolygon(layer, type, name);
          });
        });
      });
    }

    // ------------------------------ Undo / Redo (Ctrl/Cmd+Z, Ctrl/Cmd+Shift+Z) ------------------------------
    // History of serialized snapshots with the standard pointer model: a new
    // change truncates any undone future; undos walk backwards through it
    // and redo walks the future back on.
    let undoStack = [];
    let histIdx = -1;
    let commitTimer = null;
    let renderTimer = null;

    function commitHistory() {
      clearTimeout(commitTimer);
      commitTimer = null;
      undoStack = undoStack.slice(0, histIdx + 1);
      undoStack.push(JSON.stringify(serializeState()));
      if (undoStack.length > HISTORY_LIMIT) undoStack.shift();
      histIdx = undoStack.length - 1;
      saveState(); // commit points also persist, so a crash loses nothing
    }

    // Vertex drags fire pm:edit in bursts; coalesce them into one entry.
    function scheduleCommit() {
      clearTimeout(commitTimer);
      commitTimer = setTimeout(commitHistory, 350);
    }

    // Same for the (expensive) full re-render: overlap checks are O(n²) turf
    // calls, so bursts of pm:edit render once, after the drag settles.
    function scheduleRender() {
      clearTimeout(renderTimer);
      renderTimer = setTimeout(renderAll, 150);
    }

    function restoreHistory() {
      clearAll();
      addFromData(JSON.parse(undoStack[histIdx]));
      renderAll();
    }

    function undo() {
      if (histIdx <= 0) return;
      histIdx--;
      restoreHistory();
    }

    function redo() {
      if (histIdx >= undoStack.length - 1) return;
      histIdx++;
      restoreHistory();
    }

    document.addEventListener('keydown', (e) => {
      if (!(e.ctrlKey || e.metaKey)) return;
      if (e.key.toLowerCase() !== 'z') return; // Shift still gives 'Z'/'z'
      const el = document.activeElement;
      if (el && (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA')) return; // native text undo
      e.preventDefault();
      if (e.shiftKey) redo();
      else undo();
    });

    // ------------------------------ Events ------------------------------
    // --- Pin the first vertex to an existing polygon's vertex -------------------
    // Geoman snaps its hint marker on mousemove, so a click placed without a
    // fresh mouse move (or a tap on a touch screen) can land a few pixels
    // away from an existing vertex — the new polygon then starts "almost"
    // on that corner, and edges never match exactly. When the FIRST vertex
    // of a drawing is created we pin it onto the nearest existing vertex
    // when one is close enough (same 20 px radius Geoman's magnet uses).
    const FIRST_VERTEX_PIN_PX = 20;

    // Nearest vertex of any registered polygon, in screen pixels.
    function nearestExistingVertex(latlng) {
      let best = null, bestDist = FIRST_VERTEX_PIN_PX;
      const target = map.latLngToContainerPoint(latlng);
      LAYERTYPES.forEach(type => {
        polygons[type].forEach(p => {
          p.layer.getLatLngs()[0].forEach(v => {
            const d = map.latLngToContainerPoint(v).distanceTo(target);
            if (d < bestDist) { bestDist = d; best = v; }
          });
        });
      });
      // A copy, so the draft never aliases another layer's LatLng objects.
      return best ? L.latLng(best.lat, best.lng) : null;
    }

    map.on('pm:drawstart', (e) => {
      if (e.shape !== 'Polygon') return;
      const draft = e.workingLayer;
      // pm:vertexadded is a LAYER event (like pm:edit — there is no map-level
      // vertexadded), so it is attached to each draft here, on pm:drawstart.
      draft.on('pm:vertexadded', (ev) => {
        if (draft.getLatLngs().length !== 1) return; // only the very first vertex
        const pin = nearestExistingVertex(ev.latlng);
        if (!pin) return;
        draft.setLatLngs([pin]);     // move the draft outline
        ev.marker.setLatLng(pin);    // move the drawn vertex marker
        // Keep Geoman's internal bookkeeping in sync (it drives
        // _removeLastVertex for the draft while drawing).
        const info = draft._latlngInfo;
        if (info && info[0]) info[0].latlng = pin;
      });
    });

    // A finished drawing must be a simple ring (no self-crossing outline);
    // otherwise it is discarded completely (not saved, not kept on the map).
    // Geoman's allowSelfIntersection:false already blocks the classic
    // "four-corner candy" live while drawing, so this is a safety net.
    map.on('pm:create', (e) => {
      const type = activeType;
      if (!isSimpleRing(ringFromLayer(e.layer))) {
        map.removeLayer(e.layer);
        alert('The polygon has not been saved: its outline crosses itself. Please draw it again.');
        return;
      }
      layerGroups[type].addLayer(e.layer);
      registerPolygon(e.layer, type, uniqueDefaultName(type));
      renderAll();
      commitHistory();
    });

    // Geoman fires the removal event on the map, not on the layer.
    map.on('pm:remove', (e) => {
      LAYERTYPES.forEach(type => {
        polygons[type] = polygons[type].filter(p => p.layer !== e.layer);
        // Geoman only detaches the layer from the map; drop it from the
        // group as well, or it comes back when "View" re-adds the group.
        layerGroups[type].removeLayer(e.layer);
      });
      renderAll();
      commitHistory();
    });

    // ------------------------------ Startup ------------------------------
    (function start() {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (raw) {
        try { addFromData(JSON.parse(raw)); } catch (e) { /* changed format: start fresh */ }
      }
      renderAll();
      commitHistory();
    })();