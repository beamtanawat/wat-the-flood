(function (root, factory) {
  "use strict";

  const api = factory();
  if (typeof module === "object" && module.exports) {
    module.exports = api;
  } else {
    root.WATF_CAMPUS_MAP = api;
    api.initialize(root);
  }
})(typeof globalThis === "object" ? globalThis : this, function () {
  "use strict";

  const DANGER_RISKS = new Set(["HIGH", "CRITICAL"]);
  const RISK_PRIORITY = { CRITICAL: 0, HIGH: 1 };
  const RISK_NAMES = new Set(["NORMAL", "MONITOR", "HIGH", "CRITICAL"]);
  let initialized = false;

  function normalizedStatus(value) {
    const status = String(value || "UNKNOWN").toUpperCase();
    return ["ONLINE", "STALE", "OFFLINE"].includes(status) ? status : "UNKNOWN";
  }

  function resolveNodeState(node, latestState) {
    if (node.mode === "SIM") {
      const measurement = node.fixture || {};
      return {
        ...node,
        measurement,
        deviceStatus: "SIM",
        risk: RISK_NAMES.has(measurement.rule_risk) ? measurement.rule_risk : "UNKNOWN",
        lastKnownRisk: null,
        timestamp: null,
        ageSeconds: null,
      };
    }

    const measurement = latestState && latestState.measurement || null;
    const device = latestState && latestState.device || {};
    const deviceStatus = normalizedStatus(device.status);
    const risk = measurement && RISK_NAMES.has(measurement.rule_risk)
      ? measurement.rule_risk
      : "UNKNOWN";
    return {
      ...node,
      measurement,
      deviceStatus,
      risk,
      lastKnownRisk: deviceStatus !== "ONLINE" && DANGER_RISKS.has(risk) ? risk : null,
      timestamp: device.last_received_at || measurement && measurement.timestamp || null,
      ageSeconds: typeof device.age_seconds === "number" && Number.isFinite(device.age_seconds)
        ? Math.max(0, device.age_seconds)
        : null,
    };
  }

  function buildCampusSummary(states) {
    const summary = {
      total: states.length,
      NORMAL: 0,
      MONITOR: 0,
      HIGH: 0,
      CRITICAL: 0,
      STALE: 0,
      OFFLINE: 0,
      UNKNOWN: 0,
    };
    states.forEach((state) => {
      if (state.mode === "LIVE" && ["STALE", "OFFLINE"].includes(state.deviceStatus)) {
        summary[state.deviceStatus] += 1;
      } else if (RISK_NAMES.has(state.risk)) {
        summary[state.risk] += 1;
      } else {
        summary.UNKNOWN += 1;
      }
    });
    return summary;
  }

  function getActiveAlerts(states) {
    return states
      .filter((state) => DANGER_RISKS.has(state.risk)
        && (state.mode === "SIM" || (state.mode === "LIVE" && state.deviceStatus === "ONLINE")))
      .map((state, index) => ({
        id: state.id,
        name: state.name,
        mode: state.mode,
        risk: state.risk,
        direction: state.measurement && state.measurement.direction || null,
        timestamp: state.timestamp,
        ageSeconds: state.ageSeconds,
        message: state.mode === "SIM" ? "Demo electrical anomaly." : "Electrical anomaly detected.",
        _order: index,
      }))
      .sort((first, second) => {
        const riskOrder = RISK_PRIORITY[first.risk] - RISK_PRIORITY[second.risk];
        if (riskOrder !== 0) {
          return riskOrder;
        }
        const firstTime = first.timestamp ? Date.parse(first.timestamp) : 0;
        const secondTime = second.timestamp ? Date.parse(second.timestamp) : 0;
        return secondTime - firstTime || first._order - second._order;
      })
      .map(({ _order, ...alert }) => alert);
  }

  function subscribeToLatest(target, onLatest) {
    let subscribed = false;
    return function subscribe() {
      if (subscribed || !target || typeof target.addEventListener !== "function") {
        return false;
      }
      target.addEventListener("watf:latest", (event) => onLatest(event.detail));
      subscribed = true;
      return true;
    };
  }

  function showMapFallback(ui) {
    ui.map.dataset.failed = "true";
    ui.fallback.hidden = false;
  }

  function activeAlertLabel(alerts) {
    if (!alerts.length) {
      return "No Active Alerts";
    }
    return `${alerts.length} Active Alert${alerts.length === 1 ? "" : "s"}`;
  }

  function formatAge(seconds) {
    if (typeof seconds !== "number" || !Number.isFinite(seconds)) {
      return "—";
    }
    const age = Math.floor(Math.max(0, seconds));
    if (age < 60) {
      return `${age} sec ago`;
    }
    const minutes = Math.floor(age / 60);
    return `${minutes} min${age % 60 ? ` ${age % 60} sec` : ""} ago`;
  }

  function formatValue(value, digits, suffix) {
    if (typeof value !== "number" || !Number.isFinite(value)) {
      return "—";
    }
    return `${value.toFixed(digits)}${suffix}`;
  }

  function createElement(documentRef, tag, className, text) {
    const element = documentRef.createElement(tag);
    if (className) {
      element.className = className;
    }
    if (text !== undefined) {
      element.textContent = text;
    }
    return element;
  }

  function initialize(windowRef) {
    if (initialized || !windowRef || !windowRef.document || !windowRef.CAMPUS_NODES) {
      return false;
    }
    initialized = true;

    const documentRef = windowRef.document;
    const nodes = windowRef.CAMPUS_NODES;
    const byId = (id) => documentRef.getElementById(id);
    const ui = {
      monitorButton: byId("show-monitor-view"),
      mapButton: byId("show-campus-map-view"),
      monitorView: byId("monitor-view"),
      mapView: byId("campus-map-view"),
      map: byId("campus-map"),
      fallback: byId("campus-map-fallback"),
      selector: byId("campus-node-selector"),
      summary: byId("campus-node-summary"),
      selectedName: byId("campus-selected-name"),
      selectedMode: byId("campus-selected-mode"),
      selectedLocation: byId("campus-selected-location"),
      selectedStatus: byId("campus-selected-status"),
      selectedRisk: byId("campus-selected-risk"),
      selectedMessage: byId("campus-selected-message"),
      selectedDirection: byId("campus-selected-direction"),
      selectedWater: byId("campus-selected-water"),
      selectedConductivity: byId("campus-selected-conductivity"),
      selectedMagnitude: byId("campus-selected-magnitude"),
      selectedAi: byId("campus-selected-ai"),
      selectedUpdated: byId("campus-selected-updated"),
      alertTrigger: byId("campus-active-alerts"),
      alertPanel: byId("campus-alert-panel"),
      alertList: byId("campus-alert-list"),
      alertClose: byId("campus-close-alerts"),
      fitAll: byId("campus-fit-all"),
      leafletScript: byId("leaflet-script"),
    };

    if (Object.values(ui).some((element) => !element)) {
      return false;
    }

    let latestState = { measurement: null, device: { status: "UNKNOWN" } };
    let selectedId = nodes[0].id;
    let mapInstance = null;
    let tileLayer = null;
    let mapAttempted = false;
    let mapViewActive = false;
    let alertsOpen = false;
    let renderedAlertSignature = null;
    const markers = new Map();
    const liveListener = subscribeToLatest(windowRef, (state) => {
      latestState = state || { measurement: null, device: { status: "UNKNOWN" } };
      render();
    });
    liveListener();

    function stateList() {
      return nodes.map((node) => resolveNodeState(node, latestState));
    }

    function selectedState() {
      return stateList().find((state) => state.id === selectedId) || stateList()[0];
    }

    function riskClass(state) {
      if (state.mode === "LIVE" && state.deviceStatus !== "ONLINE") {
        return "offline";
      }
      return state.risk.toLowerCase();
    }

    function markerIcon(state) {
      const selected = state.id === selectedId ? " is-selected" : "";
      const cssRisk = riskClass(state);
      return windowRef.L.divIcon({
        className: "campus-div-icon",
        html: `<span class="campus-marker campus-marker-${cssRisk}${selected}" aria-hidden="true"></span>`,
        iconSize: [24, 24],
        iconAnchor: [12, 12],
      });
    }

    function popupContent(state) {
      const wrapper = createElement(documentRef, "div", "campus-popup");
      wrapper.appendChild(createElement(documentRef, "strong", "", state.name));
      wrapper.appendChild(createElement(documentRef, "span", "campus-popup-mode", state.mode === "SIM" ? "SIM · DEMO NODE" : "LIVE"));
      wrapper.appendChild(createElement(documentRef, "span", "", state.lastKnownRisk
        ? `${state.deviceStatus} · Last known risk: ${state.lastKnownRisk}`
        : state.risk));
      return wrapper;
    }

    function selectNode(id, options) {
      if (!nodes.some((node) => node.id === id)) {
        return;
      }
      selectedId = id;
      render();
      if (options && options.center && mapInstance) {
        const node = nodes.find((entry) => entry.id === id);
        mapInstance.setView([node.latitude, node.longitude], mapInstance.getZoom());
      }
    }

    function renderSelector(states) {
      const selected = selectedId;
      ui.selector.replaceChildren();
      states.forEach((state) => {
        const option = createElement(documentRef, "option", "", `${state.mode} · ${state.name}`);
        option.value = state.id;
        ui.selector.appendChild(option);
      });
      ui.selector.value = selected;
    }

    function renderSummary(states) {
      const summary = buildCampusSummary(states);
      const fragment = documentRef.createDocumentFragment();
      const labels = [
        ["NODES", summary.total], ["NORMAL", summary.NORMAL], ["MONITOR", summary.MONITOR],
        ["HIGH", summary.HIGH], ["CRITICAL", summary.CRITICAL], ["STALE", summary.STALE],
        ["OFFLINE", summary.OFFLINE], ["UNKNOWN", summary.UNKNOWN],
      ];
      labels.forEach(([label, value]) => {
        const item = createElement(documentRef, "div", "campus-summary-item");
        item.appendChild(createElement(documentRef, "span", "", label));
        item.appendChild(createElement(documentRef, "strong", "", String(value)));
        fragment.appendChild(item);
      });
      ui.summary.replaceChildren(fragment);
    }

    function renderSelected(states) {
      const state = states.find((entry) => entry.id === selectedId) || states[0];
      const measurement = state.measurement || {};
      ui.selectedName.textContent = state.name;
      ui.selectedMode.textContent = state.mode === "SIM" ? "SIM · DEMO" : "LIVE";
      ui.selectedMode.dataset.mode = state.mode;
      ui.selectedLocation.textContent = `Mapped POI · KMITL · ${state.locationNote}`;
      ui.selectedRisk.dataset.risk = state.risk;
      ui.selectedRisk.textContent = state.lastKnownRisk
        ? `Last known risk: ${state.lastKnownRisk}`
        : state.risk;

      if (state.mode === "SIM") {
        ui.selectedStatus.textContent = "SIM · SIMULATED DATA";
        ui.selectedMessage.textContent = DANGER_RISKS.has(state.risk)
          ? "Demo electrical anomaly."
          : state.risk === "MONITOR" ? "Demo reading — check sensor values." : "Demo sensor reading.";
        ui.selectedUpdated.textContent = "Last update: demo fixture";
      } else if (state.measurement && state.deviceStatus !== "ONLINE") {
        ui.selectedStatus.textContent = `${state.deviceStatus} · Last known risk: ${state.risk}`;
        ui.selectedMessage.textContent = "Last received data — not a current reading.";
        ui.selectedUpdated.textContent = `Last update: ${formatAge(state.ageSeconds)}`;
      } else if (state.measurement) {
        ui.selectedStatus.textContent = "ONLINE · Current reading";
        ui.selectedMessage.textContent = state.risk === "NORMAL"
          ? "No electrical anomaly detected at monitored point."
          : DANGER_RISKS.has(state.risk) ? "Electrical anomaly detected." : "Check sensor readings.";
        ui.selectedUpdated.textContent = `Last update: ${formatAge(state.ageSeconds)}`;
      } else {
        ui.selectedStatus.textContent = state.deviceStatus === "UNKNOWN"
          ? "Waiting for sensor reading"
          : `${state.deviceStatus} · No reading received`;
        ui.selectedMessage.textContent = "No sensor reading yet.";
        ui.selectedUpdated.textContent = "Last update: —";
      }

      ui.selectedDirection.textContent = measurement.direction || "No clear direction";
      ui.selectedWater.textContent = formatValue(measurement.water_level_cm, 1, " cm");
      ui.selectedConductivity.textContent = formatValue(measurement.conductivity_ms_cm, 2, " mS/cm");
      ui.selectedMagnitude.textContent = formatValue(measurement.gradient_v, 3, " V RMS");
      ui.selectedAi.textContent = measurement.ai_risk
        ? `${measurement.ai_risk}${typeof measurement.ai_confidence === "number" ? ` · ${(measurement.ai_confidence * 100).toFixed(0)}%` : ""}`
        : "Unavailable";
    }

    function renderAlerts(states) {
      const alerts = getActiveAlerts(states);
      ui.alertTrigger.textContent = activeAlertLabel(alerts);
      const level = alerts.some((alert) => alert.risk === "CRITICAL")
        ? "critical"
        : alerts.length ? "high" : "none";
      ui.alertTrigger.dataset.level = level;
      ui.alertTrigger.setAttribute("aria-expanded", String(alertsOpen));
      ui.alertPanel.hidden = !alertsOpen;
      const signature = JSON.stringify(alerts.map(({ id, risk, mode, direction, message }) => [
        id, risk, mode, direction, message,
      ]));
      if (signature === renderedAlertSignature) {
        return;
      }
      renderedAlertSignature = signature;
      ui.alertList.replaceChildren();
      if (!alerts.length) {
        ui.alertList.appendChild(createElement(documentRef, "li", "", "No active alerts."));
        return;
      }
      alerts.forEach((alert) => {
        const item = createElement(documentRef, "li", "campus-alert-item");
        const details = createElement(documentRef, "div", "");
        const modeText = alert.mode === "SIM" ? `${alert.risk} · SIM · DEMO ALERT` : `${alert.risk} · LIVE`;
        const line = createElement(documentRef, "strong", "campus-alert-level", modeText);
        line.dataset.risk = alert.risk;
        details.appendChild(line);
        details.appendChild(createElement(documentRef, "p", "", alert.name));
        details.appendChild(createElement(documentRef, "p", "", alert.message));
        if (alert.direction) {
          details.appendChild(createElement(documentRef, "p", "", `Direction: ${alert.direction}`));
        }
        item.appendChild(details);
        const viewButton = createElement(documentRef, "button", "", "View Sensor");
        viewButton.type = "button";
        viewButton.addEventListener("click", () => {
          alertsOpen = false;
          switchView("campus");
          selectNode(alert.id, { center: true });
          ui.alertTrigger.focus();
        });
        item.appendChild(viewButton);
        ui.alertList.appendChild(item);
      });
    }

    function renderMarkers(states) {
      if (!mapInstance || !windowRef.L) {
        return;
      }
      states.forEach((state) => {
        let marker = markers.get(state.id);
        if (!marker) {
          marker = windowRef.L.marker([state.latitude, state.longitude], {
            icon: markerIcon(state),
            keyboard: true,
            title: `${state.name} · ${state.mode}`,
          }).addTo(mapInstance);
          marker.bindPopup(popupContent(state), {
            maxWidth: 240,
            minWidth: 140,
            autoPanPadding: [16, 16],
          });
          marker.on("click", () => selectNode(state.id));
          markers.set(state.id, marker);
        } else {
          marker.setIcon(markerIcon(state));
          marker.setPopupContent(popupContent(state));
        }
      });
    }

    function render() {
      const states = stateList();
      renderSummary(states);
      renderSelected(states);
      renderAlerts(states);
      renderMarkers(states);
    }

    function fitAll() {
      if (!mapInstance || !windowRef.L) {
        return;
      }
      const bounds = windowRef.L.latLngBounds(nodes.map((node) => [node.latitude, node.longitude]));
      mapInstance.fitBounds(bounds, { padding: [28, 28], maxZoom: 17 });
    }

    function failMap() {
      showMapFallback(ui);
    }

    function ensureMap() {
      if (mapInstance) {
        windowRef.requestAnimationFrame(() => mapInstance.invalidateSize());
        return true;
      }
      if (mapAttempted) {
        return false;
      }
      mapAttempted = true;
      if (!windowRef.L || typeof windowRef.L.map !== "function") {
        failMap();
        return false;
      }
      try {
        mapInstance = windowRef.L.map(ui.map, { zoomControl: true });
        tileLayer = windowRef.L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
          maxZoom: 19,
          attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap contributors</a>',
        });
        tileLayer.on("tileerror", failMap);
        tileLayer.addTo(mapInstance);
        ui.fallback.hidden = true;
        ui.map.dataset.failed = "false";
        renderMarkers(stateList());
        fitAll();
        windowRef.requestAnimationFrame(() => mapInstance && mapInstance.invalidateSize());
        return true;
      } catch (error) {
        mapInstance = null;
        failMap();
        return false;
      }
    }

    function switchView(view) {
      const showCampus = view === "campus";
      mapViewActive = showCampus;
      ui.monitorView.hidden = showCampus;
      ui.mapView.hidden = !showCampus;
      ui.monitorButton.classList.toggle("is-active", !showCampus);
      ui.mapButton.classList.toggle("is-active", showCampus);
      ui.monitorButton.setAttribute("aria-pressed", String(!showCampus));
      ui.mapButton.setAttribute("aria-pressed", String(showCampus));
      if (showCampus) {
        ensureMap();
        render();
        if (mapInstance) {
          windowRef.requestAnimationFrame(() => mapInstance && mapInstance.invalidateSize());
        }
      }
    }

    ui.monitorButton.addEventListener("click", () => switchView("monitor"));
    ui.mapButton.addEventListener("click", () => switchView("campus"));
    ui.selector.addEventListener("change", () => selectNode(ui.selector.value, { center: true }));
    ui.fitAll.addEventListener("click", fitAll);
    ui.alertTrigger.addEventListener("click", () => {
      if (!mapViewActive) {
        switchView("campus");
        alertsOpen = true;
      } else {
        alertsOpen = !alertsOpen;
      }
      renderAlerts(stateList());
      if (alertsOpen) {
        ui.alertClose.focus();
      }
    });
    ui.alertClose.addEventListener("click", () => {
      alertsOpen = false;
      renderAlerts(stateList());
      ui.alertTrigger.focus();
    });
    if (ui.leafletScript) {
      ui.leafletScript.addEventListener("load", () => {
        if (mapViewActive && !mapInstance) {
          mapAttempted = false;
          ensureMap();
        }
      });
      ui.leafletScript.addEventListener("error", () => {
        if (mapViewActive) {
          failMap();
        }
      });
    }

    renderSelector(stateList());
    render();
    return true;
  }

  return Object.freeze({
    resolveNodeState,
    buildCampusSummary,
    getActiveAlerts,
    activeAlertLabel,
    subscribeToLatest,
    showMapFallback,
    initialize,
  });
});
