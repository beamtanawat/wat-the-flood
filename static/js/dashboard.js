(function () {
  "use strict";

  const DATE_TIME_FORMATTER = new Intl.DateTimeFormat("en-GB", {
    day: "numeric",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hourCycle: "h23",
  });
  const TIME_FORMATTER = new Intl.DateTimeFormat("en-GB", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hourCycle: "h23",
  });
  const RISK_MESSAGES = {
    NORMAL: "No electrical anomaly detected at monitored point",
    MONITOR: "Check sensor readings.",
    HIGH: "Electrical anomaly detected.",
    CRITICAL: "Electrical anomaly detected.",
  };
  const DIRECTION_REASON_MESSAGES = {
    LOW_SIGNAL: "No clear signal",
    AMBIGUOUS: "No clear signal",
    DOMINANT_AXIS: "Dominant directional gradient",
  };

  function datePartMap(formatter, date) {
    return Object.fromEntries(
      formatter
        .formatToParts(date)
        .filter((part) => part.type !== "literal")
        .map((part) => [part.type, part.value]),
    );
  }

  function parseTimestamp(timestamp) {
    const date = new Date(timestamp);
    return Number.isNaN(date.getTime()) ? null : date;
  }

  function formatLocalDateTime(timestamp) {
    const date = parseTimestamp(timestamp);
    if (!date) {
      return "—";
    }
    const parts = datePartMap(DATE_TIME_FORMATTER, date);
    return `${parts.day} ${parts.month} ${parts.year} • ${parts.hour}:${parts.minute}:${parts.second}`;
  }

  function formatHistoryTime(timestamp) {
    const date = parseTimestamp(timestamp);
    if (!date) {
      return "—";
    }
    const parts = datePartMap(TIME_FORMATTER, date);
    return `${parts.hour}:${parts.minute}:${parts.second}`;
  }

  function formatAge(value) {
    if (typeof value !== "number" || !Number.isFinite(value)) {
      return "—";
    }
    const seconds = Math.max(0, Math.floor(value));
    if (seconds < 60) {
      return `${seconds} sec ago`;
    }
    const minutes = Math.floor(seconds / 60);
    const remainingSeconds = seconds % 60;
    if (minutes < 60) {
      return remainingSeconds
        ? `${minutes} min ${remainingSeconds} sec ago`
        : `${minutes} min ago`;
    }
    const hours = Math.floor(minutes / 60);
    const remainingMinutes = minutes % 60;
    if (hours < 24) {
      return remainingMinutes ? `${hours} hr ${remainingMinutes} min ago` : `${hours} hr ago`;
    }
    const days = Math.floor(hours / 24);
    return `${days} day${days === 1 ? "" : "s"} ago`;
  }

  function deviceConditionMessage(status, timestamp) {
    if (!timestamp) {
      return "Waiting for sensor readings.";
    }
    if (status === "ONLINE") {
      return "Receiving live data";
    }
    if (status === "STALE") {
      return "Showing last received data.";
    }
    if (status === "OFFLINE") {
      return "Device offline — showing last data.";
    }
    return "Waiting for sensor readings.";
  }

  function riskMessage(risk) {
    return RISK_MESSAGES[risk] || "Electrical anomaly detected.";
  }

  function directionReasonMessage(reason) {
    return DIRECTION_REASON_MESSAGES[reason] || "Direction unavailable";
  }

  function latestEventDetail(data) {
    const measurementFields = [
      "device_id",
      "timestamp",
      "water_level_cm",
      "conductivity_ms_cm",
      "north_rms_v",
      "east_rms_v",
      "south_rms_v",
      "west_rms_v",
      "gradient_v",
      "direction",
      "direction_reason",
      "rule_risk",
      "ai_risk",
      "ai_confidence",
    ];
    const deviceFields = ["device_id", "status", "last_received_at", "age_seconds"];
    const measurement = data && data.measurement;
    const device = data && data.device || {};
    return {
      measurement: measurement
        ? Object.fromEntries(measurementFields
          .filter((field) => Object.prototype.hasOwnProperty.call(measurement, field))
          .map((field) => [field, measurement[field]]))
        : null,
      device: Object.fromEntries(deviceFields
        .filter((field) => Object.prototype.hasOwnProperty.call(device, field))
        .map((field) => [field, device[field]])),
    };
  }

  function dispatchLatestState(target, data, EventConstructor) {
    const CustomEventType = EventConstructor || (typeof CustomEvent === "function" ? CustomEvent : null);
    if (!target || typeof target.dispatchEvent !== "function" || !CustomEventType) {
      return false;
    }
    return target.dispatchEvent(new CustomEventType("watf:latest", {
      detail: latestEventDetail(data),
    }));
  }

  function workspaceSelection(activeName, tabNames) {
    const selectedName = tabNames.includes(activeName) ? activeName : tabNames[0];
    return Object.fromEntries(
      tabNames.map((name) => [
        name,
        {
          selected: name === selectedName,
          tabIndex: name === selectedName ? 0 : -1,
          hidden: name !== selectedName,
        },
      ]),
    );
  }

  function nextWorkspaceTab(currentName, key, tabNames) {
    const currentIndex = Math.max(0, tabNames.indexOf(currentName));
    if (key === "Home") {
      return tabNames[0];
    }
    if (key === "End") {
      return tabNames[tabNames.length - 1];
    }
    if (key === "ArrowRight") {
      return tabNames[(currentIndex + 1) % tabNames.length];
    }
    if (key === "ArrowLeft") {
      return tabNames[(currentIndex - 1 + tabNames.length) % tabNames.length];
    }
    return currentName;
  }

  function createDialogController({ dialog, trigger, closeButton, getActiveElement }) {
    let returnFocus = trigger;
    return {
      open() {
        returnFocus = getActiveElement() || trigger;
        if (typeof dialog.showModal === "function") {
          dialog.showModal();
        } else {
          dialog.setAttribute("open", "");
        }
        closeButton.focus();
      },
      close() {
        if (typeof dialog.close === "function") {
          dialog.close();
        } else {
          dialog.removeAttribute("open");
        }
      },
      restoreFocus() {
        if (returnFocus && typeof returnFocus.focus === "function") {
          returnFocus.focus();
        }
      },
    };
  }

  const exportedFormatters = {
    createDialogController,
    dispatchLatestState,
    deviceConditionMessage,
    directionReasonMessage,
    formatAge,
    formatHistoryTime,
    formatLocalDateTime,
    nextWorkspaceTab,
    riskMessage,
    workspaceSelection,
  };
  if (typeof module === "object" && module.exports) {
    module.exports = exportedFormatters;
  }
  if (typeof document === "undefined") {
    return;
  }

  const LATEST_INTERVAL_MS = 1000;
  const REQUEST_TIMEOUT_MS = 5000;
  const HISTORY_ROW_LIMIT = 100;
  const EVENT_ROW_LIMIT = 100;
  const directionLabels = {
    NORTH: "↑ NORTH",
    EAST: "EAST →",
    SOUTH: "SOUTH ↓",
    WEST: "← WEST",
  };
  const elements = {
    connectionWarning: document.getElementById("connection-warning"),
    deviceId: document.getElementById("device-id"),
    deviceStatus: document.getElementById("device-status"),
    deviceStatusPill: document.getElementById("device-status-pill"),
    lastReceived: document.getElementById("last-received"),
    readingAge: document.getElementById("reading-age"),
    deviceConditionNote: document.getElementById("device-condition-note"),
    riskCard: document.getElementById("risk-card"),
    ruleRisk: document.getElementById("rule-risk"),
    ruleRiskMessage: document.getElementById("rule-risk-message"),
    directionArrow: document.getElementById("direction-arrow"),
    directionReason: document.getElementById("direction-reason"),
    directionReasonValue: document.getElementById("direction-reason-value"),
    gradientV: document.getElementById("gradient-v"),
    waterLevel: document.getElementById("water-level"),
    conductivity: document.getElementById("conductivity"),
    electricalMagnitude: document.getElementById("electrical-magnitude"),
    northRms: document.getElementById("north-rms"),
    eastRms: document.getElementById("east-rms"),
    southRms: document.getElementById("south-rms"),
    westRms: document.getElementById("west-rms"),
    sensorCompass: document.getElementById("sensor-compass"),
    strongestDirection: document.getElementById("strongest-direction"),
    aiStatus: document.getElementById("ai-status"),
    aiRisk: document.getElementById("ai-risk"),
    aiConfidence: document.getElementById("ai-confidence"),
    modelVersion: document.getElementById("model-version"),
    aiAgreement: document.getElementById("ai-agreement"),
    historyEmpty: document.getElementById("history-empty"),
    historyBody: document.getElementById("history-body"),
    olderReadings: document.getElementById("older-readings"),
    returnLatest: document.getElementById("return-latest"),
    gradientChart: document.getElementById("gradient-chart"),
    waterChart: document.getElementById("water-chart"),
    conductivityChart: document.getElementById("conductivity-chart"),
    anomalyList: document.getElementById("anomaly-list"),
    technicalDeviceId: document.getElementById("technical-device-id"),
    rawTimestamp: document.getElementById("raw-timestamp"),
    calibrationVersion: document.getElementById("calibration-version"),
    analysisSource: document.getElementById("analysis-source"),
    ruleVersion: document.getElementById("rule-version"),
    technicalWater: document.getElementById("technical-water"),
    technicalConductivity: document.getElementById("technical-conductivity"),
    technicalNorth: document.getElementById("technical-north"),
    technicalEast: document.getElementById("technical-east"),
    technicalSouth: document.getElementById("technical-south"),
    technicalWest: document.getElementById("technical-west"),
    vxV: document.getElementById("vx-v"),
    vyV: document.getElementById("vy-v"),
    technicalGradient: document.getElementById("technical-gradient"),
    technicalAiStatus: document.getElementById("technical-ai-status"),
    technicalAiConfidence: document.getElementById("technical-ai-confidence"),
    technicalModelVersion: document.getElementById("technical-model-version"),
    workspaceTabs: Array.from(document.querySelectorAll("[data-workspace-tab]")),
    workspacePanels: Array.from(document.querySelectorAll("[data-workspace-panel]")),
    chartMetricTabs: Array.from(document.querySelectorAll("[data-chart-metric]")),
    chartPanels: Array.from(document.querySelectorAll("[data-chart-panel]")),
    technicalDrawer: document.getElementById("technical-drawer"),
    technicalDrawerTrigger: document.getElementById("open-technical-details"),
    technicalDrawerClose: document.getElementById("close-technical-details"),
  };

  let browsingOlder = false;
  let nextBeforeId = null;

  function setText(element, value) {
    element.textContent = value;
  }

  function formatNumber(value, digits) {
    return typeof value === "number" && Number.isFinite(value) ? value.toFixed(digits) : "—";
  }

  function renderDevice(device) {
    const status = String(device.status || "UNKNOWN").toUpperCase();
    const timestamp = device.last_received_at;
    setText(elements.deviceId, device.device_id || "Unknown device");
    setText(elements.technicalDeviceId, device.device_id || "—");
    setText(elements.deviceStatus, status === "UNKNOWN" ? "Waiting" : status);
    elements.deviceStatusPill.dataset.status = status.toLowerCase();
    setText(elements.lastReceived, timestamp ? formatLocalDateTime(timestamp) : "No reading");
    elements.lastReceived.dateTime = timestamp || "";
    elements.lastReceived.title = timestamp || "";
    setText(elements.readingAge, formatAge(device.age_seconds));

    setText(elements.deviceConditionNote, deviceConditionMessage(status, timestamp));
  }

  function resetTechnicalDetails() {
    [
      elements.rawTimestamp,
      elements.calibrationVersion,
      elements.analysisSource,
      elements.ruleVersion,
      elements.directionReasonValue,
      elements.technicalWater,
      elements.technicalConductivity,
      elements.technicalNorth,
      elements.technicalEast,
      elements.technicalSouth,
      elements.technicalWest,
      elements.vxV,
      elements.vyV,
      elements.technicalGradient,
      elements.technicalAiConfidence,
      elements.technicalModelVersion,
    ].forEach((element) => setText(element, "—"));
    setText(elements.technicalAiStatus, "UNAVAILABLE");
  }

  function renderEmpty() {
    elements.riskCard.className = "monitor-card risk-card";
    setText(elements.ruleRisk, "Waiting");
    setText(elements.ruleRiskMessage, "No sensor reading yet");
    setText(elements.directionArrow, "—");
    setText(elements.directionReason, "No clear signal");
    setText(elements.gradientV, "—");
    setText(elements.electricalMagnitude, "—");
    setText(elements.strongestDirection, "—");
    elements.sensorCompass.dataset.strongest = "none";
    elements.sensorCompass.querySelectorAll(".sensor-node").forEach((node) => node.classList.remove("is-strongest"));
    [
      elements.waterLevel,
      elements.conductivity,
      elements.northRms,
      elements.eastRms,
      elements.southRms,
      elements.westRms,
    ].forEach((element) => setText(element, "—"));
    setText(elements.aiRisk, "Unavailable");
    setText(elements.aiConfidence, "—");
    setText(elements.modelVersion, "—");
    setText(elements.aiStatus, "UNAVAILABLE");
    setText(elements.aiAgreement, "No comparison");
    elements.aiAgreement.dataset.result = "unavailable";
    resetTechnicalDetails();
  }

  function renderRisk(measurement) {
    const risk = measurement.rule_risk;
    setText(elements.ruleRisk, risk);
    setText(elements.ruleRiskMessage, riskMessage(risk));
    elements.riskCard.className = `monitor-card risk-card risk-${String(risk).toLowerCase()}`;
    if (risk === "CRITICAL") {
      setText(elements.ruleRiskMessage, `${riskMessage(risk)} Do not approach the monitored area.`);
    }
  }

  function renderDirectionalSensors(measurement) {
    const readings = [
      { name: "NORTH", key: "north", value: measurement.north_rms_v, element: elements.northRms },
      { name: "EAST", key: "east", value: measurement.east_rms_v, element: elements.eastRms },
      { name: "SOUTH", key: "south", value: measurement.south_rms_v, element: elements.southRms },
      { name: "WEST", key: "west", value: measurement.west_rms_v, element: elements.westRms },
    ];
    readings.forEach((reading) => setText(reading.element, formatNumber(reading.value, 3)));
    const validReadings = readings.filter((reading) => typeof reading.value === "number" && Number.isFinite(reading.value));
    if (!validReadings.length) {
      setText(elements.electricalMagnitude, "—");
      setText(elements.strongestDirection, "—");
      return;
    }

    const maximum = Math.max(...validReadings.map((reading) => reading.value));
    const strongest = validReadings.filter((reading) => Math.abs(reading.value - maximum) < 1e-9);
    setText(elements.electricalMagnitude, formatNumber(maximum, 3));
    elements.sensorCompass.querySelectorAll(".sensor-node").forEach((node) => node.classList.remove("is-strongest"));

    if (strongest.length === 1) {
      const reading = strongest[0];
      elements.sensorCompass.dataset.strongest = reading.key;
      elements.sensorCompass.querySelector(`[data-direction="${reading.key}"]`).classList.add("is-strongest");
      setText(elements.strongestDirection, `${reading.name} · ${formatNumber(maximum, 3)} V RMS`);
    } else {
      elements.sensorCompass.dataset.strongest = "balanced";
      setText(elements.strongestDirection, `Balanced · ${formatNumber(maximum, 3)} V RMS`);
    }
  }

  function renderAI(measurement) {
    const status = measurement.ai_status || "UNAVAILABLE";
    const aiRisk = measurement.ai_risk;
    setText(elements.aiStatus, status);
    setText(elements.aiRisk, aiRisk || "Unavailable");
    setText(
      elements.aiConfidence,
      typeof measurement.ai_confidence === "number"
        ? `${(measurement.ai_confidence * 100).toFixed(1)}%`
        : "—",
    );
    setText(elements.modelVersion, measurement.model_version || "—");
    elements.aiRisk.className = aiRisk ? `risk-${aiRisk.toLowerCase()}` : "";

    if (status === "OK" && aiRisk) {
      const agrees = aiRisk === measurement.rule_risk;
      setText(elements.aiAgreement, agrees ? "Agree" : "Differ");
      elements.aiAgreement.dataset.result = agrees ? "agree" : "differ";
    } else {
      setText(elements.aiAgreement, "No comparison");
      elements.aiAgreement.dataset.result = "unavailable";
    }
  }

  function renderTechnicalDetails(measurement) {
    setText(elements.technicalDeviceId, measurement.device_id || "—");
    setText(elements.rawTimestamp, measurement.timestamp || "—");
    setText(elements.calibrationVersion, measurement.calibration_version || "—");
    setText(elements.analysisSource, measurement.analysis_source || "—");
    setText(elements.ruleVersion, measurement.rule_version || "—");
    setText(elements.directionReasonValue, measurement.direction_reason || "—");
    setText(elements.technicalWater, formatNumber(measurement.water_level_cm, 3));
    setText(elements.technicalConductivity, formatNumber(measurement.conductivity_ms_cm, 3));
    setText(elements.technicalNorth, formatNumber(measurement.north_rms_v, 3));
    setText(elements.technicalEast, formatNumber(measurement.east_rms_v, 3));
    setText(elements.technicalSouth, formatNumber(measurement.south_rms_v, 3));
    setText(elements.technicalWest, formatNumber(measurement.west_rms_v, 3));
    setText(elements.vxV, formatNumber(measurement.vx_v, 3));
    setText(elements.vyV, formatNumber(measurement.vy_v, 3));
    setText(elements.technicalGradient, formatNumber(measurement.gradient_v, 3));
    setText(elements.technicalAiStatus, measurement.ai_status || "UNAVAILABLE");
    setText(
      elements.technicalAiConfidence,
      typeof measurement.ai_confidence === "number"
        ? `${(measurement.ai_confidence * 100).toFixed(1)}%`
        : "—",
    );
    setText(elements.technicalModelVersion, measurement.model_version || "—");
  }

  function renderMeasurement(measurement) {
    renderRisk(measurement);
    setText(elements.directionArrow, directionLabels[measurement.direction] || "—");
    setText(elements.directionReason, directionReasonMessage(measurement.direction_reason));
    setText(elements.gradientV, formatNumber(measurement.gradient_v, 3));
    setText(elements.waterLevel, formatNumber(measurement.water_level_cm, 1));
    setText(elements.conductivity, formatNumber(measurement.conductivity_ms_cm, 2));
    renderDirectionalSensors(measurement);
    renderAI(measurement);
    renderTechnicalDetails(measurement);
  }

  function renderLatest(data) {
    renderDevice(data.device || {});
    if (data.measurement) {
      renderMeasurement(data.measurement);
    } else {
      renderEmpty();
    }
    dispatchLatestState(window, data, CustomEvent);
  }

  async function fetchLatest() {
    const controller = new AbortController();
    const timeout = window.setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
    try {
      const response = await fetch("/api/latest", { signal: controller.signal });
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }
      return await response.json();
    } finally {
      window.clearTimeout(timeout);
    }
  }

  async function fetchHistory(beforeId) {
    let url = "/api/history?limit=100";
    if (beforeId !== null && beforeId !== undefined) {
      url += `&before_id=${encodeURIComponent(beforeId)}`;
    }
    const response = await fetch(url);
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }
    return await response.json();
  }

  function addSvgElement(parent, name, attributes) {
    const element = document.createElementNS("http://www.w3.org/2000/svg", name);
    Object.entries(attributes).forEach(([key, value]) => element.setAttribute(key, value));
    parent.appendChild(element);
    return element;
  }

  function chartValueLabel(value) {
    if (value >= 10) {
      return value.toFixed(0);
    }
    if (value >= 1) {
      return value.toFixed(1);
    }
    return value.toFixed(2);
  }

  function renderChart(svg, measurements, field) {
    svg.replaceChildren();
    const xStart = 52;
    const xEnd = 660;
    const yTop = 20;
    const yBottom = 174;

    if (!measurements.length) {
      addSvgElement(svg, "text", { x: 52, y: 104, class: "chart-axis-label" }).textContent = "No data";
      return;
    }

    const values = measurements.map((item) => {
      const value = Number(item[field]);
      return Number.isFinite(value) ? value : 0;
    });
    const actualMaximum = Math.max(...values, 0);
    const scaleMaximum = actualMaximum > 0 ? actualMaximum : 1;
    [0, 0.5, 1].forEach((ratio) => {
      const y = yBottom - (yBottom - yTop) * ratio;
      addSvgElement(svg, "line", { x1: xStart, y1: y, x2: xEnd, y2: y, class: "chart-grid-line" });
      const label = addSvgElement(svg, "text", { x: 44, y: y + 6, "text-anchor": "end", class: "chart-axis-label" });
      label.textContent = chartValueLabel(actualMaximum * ratio);
    });

    const coordinates = values.map((value, index) => ({
      x: values.length === 1 ? (xStart + xEnd) / 2 : xStart + ((xEnd - xStart) * index) / (values.length - 1),
      y: yBottom - ((yBottom - yTop) * value) / scaleMaximum,
      value,
      measurement: measurements[index],
    }));
    addSvgElement(svg, "polyline", {
      points: coordinates.map((point) => `${point.x},${point.y}`).join(" "),
      class: "chart-line",
    });

    const markedPoints = coordinates.length <= 20
      ? coordinates
      : [coordinates[0], coordinates[coordinates.length - 1]];
    markedPoints.forEach((point) => {
      const circle = addSvgElement(svg, "circle", { cx: point.x, cy: point.y, r: 4, class: "chart-point" });
      const title = addSvgElement(circle, "title", {});
      title.textContent = `${formatLocalDateTime(point.measurement.timestamp)} · ${point.value}`;
    });

    const startLabel = addSvgElement(svg, "text", { x: xStart, y: 207, class: "chart-axis-label" });
    startLabel.textContent = formatHistoryTime(measurements[0].timestamp);
    const endLabel = addSvgElement(svg, "text", { x: xEnd, y: 207, "text-anchor": "end", class: "chart-axis-label" });
    endLabel.textContent = formatHistoryTime(measurements[measurements.length - 1].timestamp);
  }

  function riskBadge(value) {
    const badge = document.createElement("span");
    const normalized = value || "UNAVAILABLE";
    badge.className = `risk-badge risk-${String(normalized).toLowerCase()}`;
    badge.textContent = normalized;
    return badge;
  }

  function textCell(value) {
    const cell = document.createElement("td");
    cell.textContent = value;
    return cell;
  }

  function renderHistory(data) {
    const measurements = data.measurements || [];
    nextBeforeId = data.next_before_id;
    elements.historyEmpty.hidden = measurements.length > 0;
    elements.historyBody.replaceChildren();

    measurements.slice(0, HISTORY_ROW_LIMIT).forEach((measurement) => {
      const row = document.createElement("tr");
      const timeCell = document.createElement("td");
      const time = document.createElement("time");
      time.dateTime = measurement.timestamp;
      time.title = formatLocalDateTime(measurement.timestamp);
      time.textContent = formatHistoryTime(measurement.timestamp);
      timeCell.appendChild(time);
      row.appendChild(timeCell);

      const ruleCell = document.createElement("td");
      ruleCell.appendChild(riskBadge(measurement.rule_risk));
      row.appendChild(ruleCell);
      const aiCell = document.createElement("td");
      aiCell.appendChild(riskBadge(measurement.ai_risk || measurement.ai_status));
      row.appendChild(aiCell);
      row.appendChild(textCell(measurement.direction || "—"));
      row.appendChild(textCell(`${formatNumber(measurement.water_level_cm, 1)} cm`));
      row.appendChild(textCell(`${formatNumber(measurement.conductivity_ms_cm, 2)} mS/cm`));
      elements.historyBody.appendChild(row);
    });

    const chronological = [...measurements].reverse();
    renderChart(elements.gradientChart, chronological, "gradient_v");
    renderChart(elements.waterChart, chronological, "water_level_cm");
    renderChart(elements.conductivityChart, chronological, "conductivity_ms_cm");

    const anomalies = measurements
      .filter((measurement) => measurement.rule_risk === "HIGH" || measurement.rule_risk === "CRITICAL")
      .slice(0, EVENT_ROW_LIMIT);
    elements.anomalyList.replaceChildren();
    if (!anomalies.length) {
      const empty = document.createElement("li");
      empty.className = "empty-state";
      empty.textContent = "No elevated readings.";
      elements.anomalyList.appendChild(empty);
    } else {
      anomalies.forEach((measurement) => {
        const item = document.createElement("li");
        item.className = "event-item";
        const eventTime = document.createElement("time");
        eventTime.className = "event-time";
        eventTime.dateTime = measurement.timestamp;
        eventTime.title = formatLocalDateTime(measurement.timestamp);
        eventTime.textContent = formatHistoryTime(measurement.timestamp).slice(0, 5);
        item.appendChild(eventTime);
        item.appendChild(riskBadge(measurement.rule_risk));
        const direction = document.createElement("span");
        direction.className = "event-direction";
        direction.textContent = measurement.direction || "—";
        item.appendChild(direction);
        elements.anomalyList.appendChild(item);
      });
    }

    elements.olderReadings.hidden = !nextBeforeId;
    elements.returnLatest.hidden = !browsingOlder;
  }

  async function loadHistory(beforeId) {
    const data = await fetchHistory(beforeId);
    renderHistory(data);
  }

  async function pollHistory() {
    if (!browsingOlder) {
      try {
        await loadHistory(null);
      } catch (error) {
        elements.historyEmpty.hidden = false;
        elements.historyEmpty.textContent = "History unavailable while backend is disconnected.";
      }
    }
    window.setTimeout(pollHistory, 5000);
  }

  function activateWorkspaceTab(name, moveFocus = false) {
    const tabNames = elements.workspaceTabs.map((tab) => tab.dataset.workspaceTab);
    const selection = workspaceSelection(name, tabNames);
    elements.workspaceTabs.forEach((tab) => {
      const state = selection[tab.dataset.workspaceTab];
      tab.setAttribute("aria-selected", String(state.selected));
      tab.tabIndex = state.tabIndex;
      if (state.selected && moveFocus) {
        tab.focus();
      }
    });
    elements.workspacePanels.forEach((panel) => {
      panel.hidden = selection[panel.dataset.workspacePanel].hidden;
    });
  }

  elements.workspaceTabs.forEach((tab) => {
    tab.addEventListener("click", () => activateWorkspaceTab(tab.dataset.workspaceTab));
    tab.addEventListener("keydown", (event) => {
      if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) {
        return;
      }
      event.preventDefault();
      const tabNames = elements.workspaceTabs.map((item) => item.dataset.workspaceTab);
      activateWorkspaceTab(
        nextWorkspaceTab(tab.dataset.workspaceTab, event.key, tabNames),
        true,
      );
    });
  });

  function activateChartMetric(metric) {
    elements.chartMetricTabs.forEach((button) => {
      const active = button.dataset.chartMetric === metric;
      button.classList.toggle("is-active", active);
      button.setAttribute("aria-pressed", String(active));
    });
    elements.chartPanels.forEach((panel) => {
      panel.hidden = panel.dataset.chartPanel !== metric;
    });
  }

  elements.chartMetricTabs.forEach((button) => {
    button.addEventListener("click", () => activateChartMetric(button.dataset.chartMetric));
  });

  const technicalDrawerController = createDialogController({
    dialog: elements.technicalDrawer,
    trigger: elements.technicalDrawerTrigger,
    closeButton: elements.technicalDrawerClose,
    getActiveElement: () => document.activeElement,
  });
  elements.technicalDrawerTrigger.addEventListener("click", technicalDrawerController.open);
  elements.technicalDrawerClose.addEventListener("click", technicalDrawerController.close);
  elements.technicalDrawer.addEventListener("close", technicalDrawerController.restoreFocus);
  elements.technicalDrawer.addEventListener("click", (event) => {
    if (event.target === elements.technicalDrawer) {
      technicalDrawerController.close();
    }
  });

  elements.olderReadings.addEventListener("click", async () => {
    if (!nextBeforeId) {
      return;
    }
    browsingOlder = true;
    elements.returnLatest.hidden = false;
    try {
      await loadHistory(nextBeforeId);
    } catch (error) {
      elements.historyEmpty.hidden = false;
      elements.historyEmpty.textContent = "History unavailable while backend is disconnected.";
    }
  });

  elements.returnLatest.addEventListener("click", async () => {
    browsingOlder = false;
    try {
      await loadHistory(null);
    } catch (error) {
      elements.historyEmpty.hidden = false;
      elements.historyEmpty.textContent = "History unavailable while backend is disconnected.";
    }
  });

  async function pollLatest() {
    try {
      const data = await fetchLatest();
      renderLatest(data);
      elements.connectionWarning.hidden = true;
    } catch (error) {
      elements.connectionWarning.hidden = false;
      elements.connectionWarning.textContent = "⚠ Latest reading unavailable";
      elements.connectionWarning.title = "Backend connection warning: latest reading unavailable.";
    } finally {
      window.setTimeout(pollLatest, LATEST_INTERVAL_MS);
    }
  }

  pollLatest();
  pollHistory();
})();
