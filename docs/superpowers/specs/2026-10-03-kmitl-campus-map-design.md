# KMITL Campus Sensor Map — Design Specification

Date: 2026-10-03
Status: Approved for implementation (including the approved `dashboard.js` event bridge exception).

## Goal

Add a Campus Map view to WAT THE FLOOD that displays the existing E12 device alongside four clearly identified demonstration nodes. Preserve the existing Monitor, backend interfaces, rule and AI behavior, simulator, persistence, polling, and device-health logic.

The map is a prototype visualization of mapped campus points of interest (POIs). Node coordinates are not confirmed sensor-installation positions. SIM readings are demonstrations, not measurements or campus hazards. Preserve the existing prototype and safety disclosures; never claim that a NORMAL result is certified safe.

## Scope and invariants

In scope:

- Compact Monitor / Campus Map navigation in the existing dashboard.
- Leaflet interactive map with OpenStreetMap tiles and visible attribution.
- A centralized, documented five-node registry and frontend-only SIM fixtures.
- Node selection, node details, summary counts, map legend, and campus alerts.
- Isolated map/tile failure behavior.
- Dashboard tests and rendered desktop/mobile verification.

Out of scope: Flask routes, HTTP contracts, database schema, simulator behavior, analysis or risk rules, AI behavior, device-health logic, new thresholds, and multi-device backend support. MQTT is prohibited. Do not redesign the Monitor view beyond the small navigation addition.

## Node registry and mapped POIs

Keep all node identity, display name, coordinates, source note, mode, and data source in one registry. Do not duplicate node metadata across render, alert, and selector functions. Add a source/uncertainty note for every coordinate in the registry or adjacent documentation.

| ID | Display name | Mode/source | Latitude | Longitude | Location evidence |
|---|---|---|---:|---:|---|
| `esp32-01` | E12 Engineering Building | LIVE / `/api/latest` | 13.72764 | 100.77245 | Research POI table names E12 Tower; KMITL brochure identifies E12 Building as a campus landmark. |
| `sim-me-tower` | ME Tower | SIM / fixture | 13.72766 | 100.77348 | Research POI table identifies ME Tower as the ME office. |
| `sim-sport-complex` | Sport Complex | SIM / fixture | 13.73003 | 100.77245 | Research POI table identifies the stadium as the sport complex; KMITL brochure lists Sport Complex. |
| `sim-telecom-tower` | Telecom Tower | SIM / fixture | 13.72744 | 100.77620 | Research POI table identifies Telecom Tower as Telecom Engineering Department. |
| `sim-a-tower` | A Tower | SIM / fixture | 13.72693 | 100.77648 | Research POI table identifies A Tower as a KMITL office. |

The coordinate source is an academic POI-mapping paper. Coordinates are approximate mapped POI points and may not identify building entrances, sensor positions, or current facility boundaries. The KMITL brochure cross-checks campus landmark names, not coordinate precision. Keep this caveat visible in source comments/docs and the map's prototype disclosure. Sources: [POI mapping paper](https://lexitron.nectec.or.th/public/NCIT_2010_Bangkok%20_Thailand/index_files/papers/81-p088.pdf); [KMITL OIA campus brochure](https://oia.kmitl.ac.th/wp-content/uploads/2024/02/OIA-KMITL-fold-brochure.pdf).

## Frontend architecture and data flow

Keep the Monitor and Campus Map as views in the current Flask-served page; switching views must not reload the document or stop existing polling. Preserve Monitor DOM and rendering behavior apart from navigation integration.

- `templates/index.html`: add navigation and the Campus Map view, including map host, summary, selector, details, legend, alerts, and resilient fallback message. Load map code after its dependencies without blocking Monitor startup.
- `static/js/campus-nodes.js`: export the centralized POI registry and explicit demonstration fixtures.
- `static/js/campus-map.js`: own map initialization, marker lifecycle, selection, summary, alert filtering/rendering, and fallback behavior. Consume Monitor's existing latest-reading state through a small explicit interface; do not issue a second `/api/latest` poll.
- `static/js/dashboard.js`: after its existing latest response has updated Monitor's measurement and device-health view, dispatch one `watf:latest` browser event containing only `{measurement, device}` normalized state needed by E12. Keep the current poll interval, fetch path, and rendering behavior unchanged.
- `static/css/dashboard.css`: add scoped styles matching the existing light, restrained dashboard system; do not restyle Monitor components.
- `tests/test_dashboard.py`: add coverage for navigation, map structure, registry, data mapping, selection, counts, alert semantics, and failure isolation while retaining existing assertions.

Use Leaflet and standard OpenStreetMap tiles, with attribution always visible. Fit the map bounds to configured nodes. Initialize on first entry and invalidate map size after the view becomes visible. Preserve zoom on sensor selection when practical; provide a fit-all control. A missing Leaflet script, initialization error, or unavailable tile service must not disable navigation, selection, details, alerts, or Monitor polling. Show the approved fallback text: “Campus map unavailable — sensor monitoring remains active.”

## Node data and presentation

The LIVE E12 node must use exactly the measurement and `device` object returned by the existing `/api/latest` response already consumed by the Monitor. Never create a separate E12 fixture or reinterpret its values. Use the backend-provided device status and freshness result without duplicating health thresholds.

Four SIM nodes use explicit, deterministic frontend fixtures with system-compatible display fields where relevant. Fixtures are visibly demo-only and must not be sent to the backend or simulator. They do not represent deployed equipment or real campus conditions. Risk values are presentation fixtures; do not modify or invoke a new rule engine to derive real-world safety claims. Keep Rule Risk primary and any existing synthetic AI comparison secondary.

Every node must be marked LIVE or SIM in the selector, marker popup, and selected-node panel. Marker color represents displayed risk/device state, not LIVE/SIM identity. Use the existing restrained risk palette, selected-node ring, accessible marker names, and concise legend. Avoid animation that obscures status.

The selected-node panel shows name, mapped location, mode, device status, Rule Risk, direction, water level, conductivity, electrical magnitude, last update, and AI comparison only when available. Preserve deterministic signal direction as distinct from risk. When E12 has no measurement, show unavailable values rather than fabricated ones. When it is STALE or OFFLINE, describe measurement values as last received and include elapsed time; do not imply they are current.

## Freshness, risk, and alert semantics

Use `device.status` from `/api/latest` as the sole LIVE-node freshness authority. Preserve the backend's existing status semantics. The campus map must not add thresholds or silently convert a stale reading into a current state.

| Node/state | Campus summary and selected view | Active Alerts |
|---|---|---|
| LIVE + ONLINE + HIGH | HIGH, current reading | Count as active alert |
| LIVE + ONLINE + CRITICAL | CRITICAL, current reading | Count as active alert |
| LIVE + STALE/OFFLINE + last HIGH | Gray/offline; show `OFFLINE · Last known risk: HIGH` (or STALE as appropriate) and `Last update: … ago` | Do not count |
| LIVE + STALE/OFFLINE + last CRITICAL | Gray/offline; show `OFFLINE · Last known risk: CRITICAL` (or STALE as appropriate) and `Last update: … ago` | Do not count |
| LIVE + no reading | Offline/unknown; no measurement values | Do not count |
| SIM + HIGH/CRITICAL fixture | Clearly marked SIM / DEMO in every alert surface | Count as demo alert, not a physical campus alert |
| NORMAL or MONITOR | Display state without danger alert | Do not count |

Active alert count includes only current LIVE+ONLINE HIGH/CRITICAL readings and configured SIM HIGH/CRITICAL demo fixtures. Show SIM items as `HIGH · SIM` / `CRITICAL · SIM` and use “Demo electrical anomaly.” LIVE alert text may say “Electrical anomaly detected.” Do not describe either as a certified safety conclusion. Sort CRITICAL before HIGH, then newest/current update. `View Sensor` closes the alert surface, switches to Campus Map if needed, selects the node, and centers/highlights its marker. Offline/stale last-known conditions may appear in the selected panel or a separate last-known section, never in Active Alerts.

## Summary and interaction

Provide compact counts for total nodes and the represented current states, including NORMAL, MONITOR, HIGH, CRITICAL, STALE/OFFLINE, and UNKNOWN as applicable. Counts update after each E12 latest response and reflect SIM fixture state. Active Alerts is a distinct count governed by the freshness rules above.

Selecting a node by marker or selector updates the same selected-node panel and marker highlight. Selector labels include LIVE/SIM. Marker popups repeat node name and mode; SIM popups explicitly say simulated data. Alert actions use registry IDs rather than duplicated coordinates or names.

## Accessibility and responsive behavior

Navigation and selector are keyboard operable with visible focus. Use semantic headings, status text that does not rely on color, accessible marker descriptions, and announced alert-count changes. Alert panel must be usable on mobile and dismissible without losing context.

At desktop targets 1366×768, 1440×900, and 1920×1080, keep the Campus Map view within one viewport where practical, without page-level vertical scrolling. The map should occupy roughly 70–75% of the main region and selected details 25–30%; internal scrolling is acceptable in the details/alerts panel. At 390×844, vertical scrolling is allowed, horizontal overflow is not, and map controls/markers/selector remain touch-usable.

## Verification and acceptance

Tests are written before implementation. Add/update dashboard tests for:

- Monitor remains available and existing Monitor tests pass; Campus Map navigation and map host exist.
- Leaflet/map initialization wiring and an isolated fallback path.
- Exactly five registry entries; E12 is LIVE and maps to `esp32-01`; four named nodes are SIM and have source notes.
- E12 uses the existing latest response rather than a duplicate poll or fabricated data.
- Marker/state mapping, selection via marker and selector, selected details, summary counts, and active alert count.
- LIVE ONLINE HIGH/CRITICAL count as alerts; LIVE STALE/OFFLINE last-known HIGH/CRITICAL do not; status text includes last known risk and age.
- SIM HIGH/CRITICAL alerts are labeled SIM/DEMO; NORMAL/MONITOR never create danger alerts; priority ordering and View Sensor behavior.
- Map initialization/tile failure leaves Monitor, selector, details, and alert interactions usable.

Then run the complete Python test suite, JavaScript syntax validation, and `git diff --check`. Run the Flask app in a browser and visually verify the empty/no-reading state, E12 NORMAL/HIGH/CRITICAL while ONLINE, STALE/OFFLINE after a prior HIGH/CRITICAL reading, all SIM fixture states, and map-failure fallback. Check desktop at all three specified sizes and mobile at 390×844; inspect browser console and horizontal/page overflow. Use the existing simulator only to exercise E12 via its existing HTTP contract. Do not change simulator behavior.

Acceptance requires existing Monitor behavior and polling to remain intact, all five nodes to be selectable and correctly labeled, only current LIVE ONLINE hazards plus SIM demo fixtures to count as alerts, stale/offline E12 hazards to appear only as last-known conditions, and map failure not to disrupt monitoring. No backend/API/database/AI/rule/simulator/device-health changes; no MQTT; no unsupported safety claims.
