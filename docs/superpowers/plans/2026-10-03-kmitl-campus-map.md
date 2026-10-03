# KMITL Campus Sensor Map Implementation Plan

> **For agentic workers:** Execute this plan task-by-task with the approved native workflow. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a responsive Leaflet/OpenStreetMap campus map with one backend-backed E12 node and four clearly marked SIM POIs, without changing the existing monitoring contract or behavior.

**Architecture:** Keep both views in the existing Flask page. Add a centralized node/fixture module and a Campus Map controller module. Bridge the existing `dashboard.js` latest response to that controller with a one-way `watf:latest` event; never poll `/api/latest` from the map.

**Tech Stack:** Existing Flask/Jinja page, vanilla JavaScript, Leaflet, OpenStreetMap standard tiles, existing pytest tests and Node syntax/helper checks.

**Spec:** `docs/superpowers/specs/2026-10-03-kmitl-campus-map-design.md`

## Global Constraints

- Do not introduce MQTT.
- Preserve `/api/latest` polling interval, request behavior, API, backend, database, simulator, rule engine, AI, and device-health behavior.
- E12 (`esp32-01`) uses the existing latest measurement and device summary; add no map polling.
- Only LIVE + ONLINE HIGH/CRITICAL readings count as active LIVE alerts; stale/offline last-known risk never counts.
- SIM alerts must say SIM/DEMO; fixture values are not real measurements or hazards.
- Coordinates are approximate mapped POIs, not confirmed sensor-installation positions.
- Preserve existing Monitor rendering, behavior, safety wording, and primary Rule Risk / secondary AI presentation.
- Map/tile failure must not disable navigation, selector, details, alerts, Monitor, or its polling.
- Keep OpenStreetMap attribution visible; avoid horizontal overflow on mobile.

## Review Focus

- Missing/invalid latest payload: E12 remains no-reading/unknown without fabricated data.
- `STALE` or `OFFLINE` with prior HIGH/CRITICAL: show last-known risk and age, exclude from Active Alerts.
- Map library or tile failure: selector/details/alerts and Monitor remain usable.
- Repeated view switching and latest events: no duplicate listeners, handlers, or polling.
- Untrusted content in sensor values/names: render text safely, not as HTML.

---

## File Responsibilities

- Modify `tests/test_dashboard.py`: first add failing markup, registry, pure-state, alert, and bridge contract tests; retain existing tests.
- Modify `templates/index.html`: add compact view navigation, accessible Campus Map markup, selector, map host, summary, detail/alert regions, attribution-ready map host, and deferred assets.
- Modify `static/css/dashboard.css`: add scoped map/navigation styles and responsive layout only.
- Create `static/js/campus-nodes.js`: export five node metadata records and four deterministic SIM fixtures; include coordinate provenance/uncertainty notes.
- Create `static/js/campus-map.js`: expose pure state/summary/alert helpers for Node tests; initialize Leaflet once, listen once for `watf:latest`, render marker/selector/detail/alerts, and isolate map failures.
- Modify `static/js/dashboard.js`: dispatch the minimal one-way latest event after existing rendering completes; do not otherwise change polling or visible Monitor output.

## Task 1: Define Campus Map markup and view navigation

**Files:**
- Test: `tests/test_dashboard.py`
- Modify: `templates/index.html`
- Modify: `static/css/dashboard.css`

**Interfaces:** Navigation toggles existing Monitor and Campus Map sections in-place. Map controller will later bind to IDs/data attributes defined here.

- [x] Add failing tests `test_dashboard_exposes_monitor_and_campus_map_navigation` and `test_campus_map_markup_contains_map_selector_summary_details_alerts_and_fallback`. Assert existing Monitor is present, new view has stable IDs, OpenStreetMap attribution text, safety/POI caveat, and no backend route is referenced.
- [x] Run focused tests; expected RED observed. (`pytest` command unavailable; used project venv.)
- [x] Add semantic navigation buttons and a hidden-by-default Campus Map section in `templates/index.html`. Include stable IDs for map host, selector, counts, selected-node detail, alert count/list/panel, and map fallback. Add Leaflet CSS/JS and project scripts as deferred assets in dependency order.
- [x] Add only scoped `.campus-*` styles to `static/css/dashboard.css`; fit desktop view and stack map/detail on mobile.
- [x] Re-run dashboard tests; 14 passed.

## Task 2: Centralize verified POIs and deterministic SIM fixtures

**Files:**
- Test: `tests/test_dashboard.py`
- Create: `static/js/campus-nodes.js`

**Interfaces:** Export `CAMPUS_NODES` in browser and CommonJS environments. Each record has `id`, `name`, `shortName`, `latitude`, `longitude`, `mode`, `source`, `locationNote`; SIM records additionally have one fixture object. E12 ID is `esp32-01` and source is `backend`.

- [x] Add failing Node-backed test `test_campus_node_registry_has_one_live_and_four_documented_sim_nodes`. Assert exact IDs/names/coordinates from the spec, all source notes, one LIVE backend node, and four SIM fixture nodes.
- [x] Run that test; expected RED observed (module absent).
- [x] Implement the small UMD-style registry in `static/js/campus-nodes.js`; record the research POI table source and mapped-location caveat in source comments. Set deterministic fixture risks: ME Tower NORMAL, Sport Complex MONITOR, Telecom Tower HIGH, A Tower CRITICAL. Mark all four fixtures SIM/DEMO-only; values are illustrative, not threshold-derived.
- [x] Focused test passed; dashboard suite 15 passed.

## Task 3: Test and implement node-state, summary, and alert rules

**Files:**
- Test: `tests/test_dashboard.py`
- Create: `static/js/campus-map.js`

**Interfaces:** Export pure functions `resolveNodeState(node, latestState)`, `buildCampusSummary(states)`, and `getActiveAlerts(states)` for browser and CommonJS use. `latestState` shape is `{measurement: object|null, device: {device_id, status, last_received_at, age_seconds}}`. `resolveNodeState` preserves fixture/LIVE source distinction; `getActiveAlerts` returns only LIVE+ONLINE HIGH/CRITICAL and SIM fixture HIGH/CRITICAL.

- [x] Add failing tests for LIVE freshness, stale/offline last-known risk, SIM alert labeling, and summary counts. Cover ONLINE HIGH/CRITICAL, STALE/OFFLINE after each risk, NORMAL/MONITOR, and CRITICAL-before-HIGH ordering.
- [x] Run focused tests; expected RED observed (module absent).
- [x] Implement pure helpers in `campus-map.js`. Use backend status as-is; expose `lastKnownRisk` for stale/offline E12 and never include that state in active alerts.
- [x] Re-run focused tests and full dashboard file; 19 passed.

## Task 4: Add one-way latest event bridge and verify its contract

**Files:**
- Test: `tests/test_dashboard.py`
- Modify: `static/js/dashboard.js`
- Modify: `static/js/campus-map.js`

**Interfaces:** After `renderLatest(data)` finishes current device and measurement rendering, dispatch `window` `CustomEvent("watf:latest", {detail: {measurement, device}})`. `device` contains only `device_id`, `status`, `last_received_at`, `age_seconds`. Campus controller's single listener consumes the event; no API call is made from map code.

- [x] Add failing test `test_dashboard_emits_normalized_latest_event_without_changing_polling` for the event name and whitelisted normalized detail fields.
- [x] Run focused test; expected RED observed (missing dispatch helper).
- [x] Add `dispatchLatestState` in `dashboard.js`, called once after existing device/measurement rendering in `renderLatest`. Existing fetch and timer code remains unchanged.
- [x] Add and test `subscribeToLatest` as an idempotent listener helper for the Campus Map controller.
- [x] Re-run bridge/listener tests and full dashboard file; 21 passed.

## Task 5: Implement Leaflet map, selection, details, and alert interactions

**Files:**
- Test: `tests/test_dashboard.py`
- Modify: `static/js/campus-map.js`
- Modify: `templates/index.html`

**Interfaces:** Campus Map initializer binds existing map markup and registry once. Marker and selector selection share `selectNode(id, {center})`; alert action calls the same function after switching view. Map invalid state sets fallback message but leaves non-map controls active.

- [x] Add failing tests for map assets/controls, LIVE event wiring without a second poll, fallback isolation, and mobile popup wrapping/selection behavior.
- [x] Run focused tests and confirm failures.
- [x] Implement single map initialization with OSM standard tile URL and attribution, bounds fit, Leaflet markers styled by risk/device state, selected marker ring, selector options with LIVE/SIM labels, marker popups, detail panel, summary, and alert UI. LIVE details use only bridge data. Mark SIM values and alerts unmistakably.
- [x] Implement Monitor/Campus Map switching without reload; initialize map once and call `invalidateSize()` after Campus Map becomes visible. Preserve zoom when selecting nodes; expose fit-all.
- [x] Add graceful fallback for missing `L`, initialization exceptions, and tile-layer failure. Keep selector/details/alerts usable if the map surface fails.
- [x] Re-run focused tests and confirm interaction/state coverage; 25 dashboard tests pass.

## Task 6: Verify complete behavior, safety, and responsive rendering

**Files:** All six implementation/test files above; no backend files.

- [x] Run `./.venv/bin/python -m pytest tests/test_dashboard.py -q` (25 passed).
- [x] Run full suite: `./.venv/bin/python -m pytest -q` (106 passed).
- [x] Run `node --check static/js/dashboard.js`, `node --check static/js/campus-nodes.js`, and `node --check static/js/campus-map.js`.
- [x] Run `git diff --check` and verify no backend/API/database/simulator/AI/rule/device-health files changed; verify no MQTT references were added.
- [x] Run Flask and visually verify map + Monitor in browser at 1366×768, 1440×900, 1920×1080, and 390×844. Desktop document dimensions matched viewport; mobile had no horizontal overflow. OSM attribution, selector/marker interaction, alerts, map fallback helper, and browser console checked.
- [x] Exercise E12 with the existing simulator through HTTP for NORMAL, all four directions, HIGH_CONDUCTIVITY, HIGH_WATER, SOURCE_RIGHT/HIGH, and CRITICAL. Every POST returned 201. Verify ONLINE NORMAL, MONITOR, HIGH, CRITICAL, STALE, and OFFLINE; stale/offline last-known risk/age remains visible and E12 is excluded from Active Alerts.
- [x] Check browser console (no warnings/errors) and repeat Monitor/Campus Map switching; listener idempotence and unchanged one-second polling are covered by tests/code and live server request log.
- [x] Confirm all four SIM nodes are labeled SIM/DEMO in selector, marker popup, details, and alerts.
