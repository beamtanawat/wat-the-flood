import json
import os
from pathlib import Path
import subprocess


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def run_dashboard_formatters(script):
    environment = os.environ.copy()
    environment["TZ"] = "Asia/Bangkok"
    result = subprocess.run(
        ["node", "-e", script],
        cwd=PROJECT_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def test_dashboard_page_exposes_priority_sections(client):
    response = client.get("/")

    assert response.status_code == 200
    assert response.content_type.startswith("text/html")
    html = response.get_data(as_text=True)
    assert "WAT THE FLOOD" in html
    assert "Flood Electrical Monitor" in html
    assert "University prototype" in html
    assert 'id="rule-risk"' in html
    assert "Risk Level" in html
    assert "AI Analysis" in html
    assert "Live Trends" in html
    assert "Signal direction only" in html
    assert 'id="history-body"' in html
    assert 'id="older-readings"' in html
    assert 'id="return-latest"' in html
    assert 'id="gradient-chart"' in html
    assert 'id="water-chart"' in html
    assert 'id="conductivity-chart"' in html
    assert "water_level_cm" in html
    assert "conductivity_ms_cm" in html
    assert "north_rms_v" in html
    assert ">SAFE<" not in html


def test_dashboard_exposes_monitor_and_campus_map_navigation(client):
    html = client.get("/").get_data(as_text=True)

    assert '<nav class="view-navigation" aria-label="Dashboard views">' in html
    assert 'id="show-monitor-view"' in html
    assert 'id="show-campus-map-view"' in html
    assert 'id="monitor-view"' in html
    assert 'id="campus-map-view"' in html
    assert 'id="monitor-view"' in html[:html.index('id="campus-map-view"')]


def test_campus_map_markup_contains_map_selector_summary_details_alerts_and_fallback(client):
    html = client.get("/").get_data(as_text=True)
    campus_view = html[html.index('id="campus-map-view"'):]

    for element_id in (
        "campus-map",
        "campus-node-selector",
        "campus-node-summary",
        "campus-selected-node",
        "campus-active-alerts",
        "campus-alert-list",
        "campus-map-fallback",
        "campus-fit-all",
    ):
        assert f'id="{element_id}"' in campus_view

    assert "OpenStreetMap" in campus_view
    assert "mapped points of interest" in campus_view
    assert "not confirmed sensor-installation positions" in campus_view
    assert "Campus map unavailable — sensor monitoring remains active." in campus_view
    assert "/api/latest" not in campus_view


def test_campus_node_registry_has_one_live_and_four_documented_sim_nodes():
    values = run_dashboard_formatters(
        """
        const { CAMPUS_NODES } = require('./static/js/campus-nodes.js');
        process.stdout.write(JSON.stringify(CAMPUS_NODES.map((node) => ({
          id: node.id,
          name: node.name,
          latitude: node.latitude,
          longitude: node.longitude,
          mode: node.mode,
          source: node.source,
          locationNote: node.locationNote,
          ruleRisk: node.fixture ? node.fixture.rule_risk : null
        }))));
        """
    )

    assert values == [
        {
            "id": "esp32-01",
            "name": "E12 Engineering Building",
            "latitude": 13.72764,
            "longitude": 100.77245,
            "mode": "LIVE",
            "source": "backend",
            "locationNote": "Approximate mapped POI; not a confirmed sensor-installation position.",
            "ruleRisk": None,
        },
        {
            "id": "sim-me-tower",
            "name": "ME Tower",
            "latitude": 13.72766,
            "longitude": 100.77348,
            "mode": "SIM",
            "source": "simulation",
            "locationNote": "Approximate mapped POI; not a confirmed sensor-installation position.",
            "ruleRisk": "NORMAL",
        },
        {
            "id": "sim-sport-complex",
            "name": "Sport Complex",
            "latitude": 13.73003,
            "longitude": 100.77245,
            "mode": "SIM",
            "source": "simulation",
            "locationNote": "Approximate mapped POI; not a confirmed sensor-installation position.",
            "ruleRisk": "MONITOR",
        },
        {
            "id": "sim-telecom-tower",
            "name": "Telecom Tower",
            "latitude": 13.72744,
            "longitude": 100.7762,
            "mode": "SIM",
            "source": "simulation",
            "locationNote": "Approximate mapped POI; not a confirmed sensor-installation position.",
            "ruleRisk": "HIGH",
        },
        {
            "id": "sim-a-tower",
            "name": "A Tower",
            "latitude": 13.72693,
            "longitude": 100.77648,
            "mode": "SIM",
            "source": "simulation",
            "locationNote": "Approximate mapped POI; not a confirmed sensor-installation position.",
            "ruleRisk": "CRITICAL",
        },
    ]


def test_live_alert_requires_online_freshness():
    values = run_dashboard_formatters(
        """
        const { CAMPUS_NODES } = require('./static/js/campus-nodes.js');
        const { resolveNodeState, getActiveAlerts } = require('./static/js/campus-map.js');
        const live = CAMPUS_NODES[0];
        const stateFor = (status, risk) => resolveNodeState(live, {
          measurement: { device_id: 'esp32-01', rule_risk: risk, direction: 'EAST', timestamp: '2026-10-03T06:00:00Z' },
          device: { device_id: 'esp32-01', status, last_received_at: '2026-10-03T06:00:00Z', age_seconds: 4 }
        });
        const onlineHigh = stateFor('ONLINE', 'HIGH');
        const onlineCritical = stateFor('ONLINE', 'CRITICAL');
        process.stdout.write(JSON.stringify({
          high: getActiveAlerts([onlineHigh]).map((alert) => [alert.id, alert.risk, alert.mode]),
          critical: getActiveAlerts([onlineCritical]).map((alert) => [alert.id, alert.risk, alert.mode])
        }));
        """
    )

    assert values == {
        "high": [["esp32-01", "HIGH", "LIVE"]],
        "critical": [["esp32-01", "CRITICAL", "LIVE"]],
    }


def test_stale_or_offline_live_high_is_last_known_not_active():
    values = run_dashboard_formatters(
        """
        const { CAMPUS_NODES } = require('./static/js/campus-nodes.js');
        const { resolveNodeState, getActiveAlerts } = require('./static/js/campus-map.js');
        const live = CAMPUS_NODES[0];
        const stateFor = (status, risk) => resolveNodeState(live, {
          measurement: { device_id: 'esp32-01', rule_risk: risk, direction: 'WEST' },
          device: { device_id: 'esp32-01', status, last_received_at: '2026-10-03T06:00:00Z', age_seconds: 79.4 }
        });
        const staleHigh = stateFor('STALE', 'HIGH');
        const offlineCritical = stateFor('OFFLINE', 'CRITICAL');
        process.stdout.write(JSON.stringify({
          stale: [staleHigh.deviceStatus, staleHigh.risk, staleHigh.lastKnownRisk, staleHigh.ageSeconds, getActiveAlerts([staleHigh]).length],
          offline: [offlineCritical.deviceStatus, offlineCritical.risk, offlineCritical.lastKnownRisk, offlineCritical.ageSeconds, getActiveAlerts([offlineCritical]).length]
        }));
        """
    )

    assert values == {
        "stale": ["STALE", "HIGH", "HIGH", 79.4, 0],
        "offline": ["OFFLINE", "CRITICAL", "CRITICAL", 79.4, 0],
    }


def test_sim_high_critical_are_demo_alerts_and_normal_monitor_are_not_alerts():
    values = run_dashboard_formatters(
        """
        const { CAMPUS_NODES } = require('./static/js/campus-nodes.js');
        const { resolveNodeState, getActiveAlerts } = require('./static/js/campus-map.js');
        const states = CAMPUS_NODES.slice(1).map((node) => resolveNodeState(node, null));
        process.stdout.write(JSON.stringify(getActiveAlerts(states).map((alert) => [
          alert.id, alert.risk, alert.mode, alert.message
        ])));
        """
    )

    assert values == [
        ["sim-a-tower", "CRITICAL", "SIM", "Demo electrical anomaly."],
        ["sim-telecom-tower", "HIGH", "SIM", "Demo electrical anomaly."],
    ]


def test_summary_counts_current_status_without_counting_stale_risk():
    values = run_dashboard_formatters(
        """
        const { CAMPUS_NODES } = require('./static/js/campus-nodes.js');
        const { resolveNodeState, buildCampusSummary } = require('./static/js/campus-map.js');
        const live = resolveNodeState(CAMPUS_NODES[0], {
          measurement: { device_id: 'esp32-01', rule_risk: 'HIGH' },
          device: { device_id: 'esp32-01', status: 'OFFLINE', last_received_at: '2026-10-03T06:00:00Z', age_seconds: 40 }
        });
        const states = [live, ...CAMPUS_NODES.slice(1).map((node) => resolveNodeState(node, null))];
        const summary = buildCampusSummary(states);
        process.stdout.write(JSON.stringify({
          total: summary.total,
          normal: summary.NORMAL,
          monitor: summary.MONITOR,
          high: summary.HIGH,
          critical: summary.CRITICAL,
          stale: summary.STALE,
          offline: summary.OFFLINE,
          unknown: summary.UNKNOWN
        }));
        """
    )

    assert values == {
        "total": 5,
        "normal": 1,
        "monitor": 1,
        "high": 1,
        "critical": 1,
        "stale": 0,
        "offline": 1,
        "unknown": 0,
    }


def test_dashboard_emits_normalized_latest_event_without_changing_polling():
    values = run_dashboard_formatters(
        """
        const dashboard = require('./static/js/dashboard.js');
        const calls = [];
        class EventDouble {
          constructor(type, options) { this.type = type; this.detail = options.detail; }
        }
        dashboard.dispatchLatestState({ dispatchEvent: (event) => calls.push(event) }, {
          measurement: {
            id: 27,
            device_id: 'esp32-01',
            timestamp: '2026-10-03T06:00:00Z',
            water_level_cm: 5.2,
            conductivity_ms_cm: 0.48,
            north_rms_v: 0.05,
            east_rms_v: 0.8,
            south_rms_v: 0.04,
            west_rms_v: 0.05,
            gradient_v: 0.75,
            direction: 'EAST',
            direction_reason: 'DOMINANT_AXIS',
            rule_risk: 'HIGH',
            ai_risk: 'MONITOR',
            ai_confidence: 0.71,
            calibration_version: 'internal-only'
          },
          device: {
            device_id: 'esp32-01',
            status: 'ONLINE',
            last_received_at: '2026-10-03T06:00:00Z',
            age_seconds: 4,
            internal: 'omit'
          }
        }, EventDouble);
        process.stdout.write(JSON.stringify({
          type: calls[0].type,
          detail: calls[0].detail
        }));
        """
    )

    assert values == {
        "type": "watf:latest",
        "detail": {
            "measurement": {
                "device_id": "esp32-01",
                "timestamp": "2026-10-03T06:00:00Z",
                "water_level_cm": 5.2,
                "conductivity_ms_cm": 0.48,
                "north_rms_v": 0.05,
                "east_rms_v": 0.8,
                "south_rms_v": 0.04,
                "west_rms_v": 0.05,
                "gradient_v": 0.75,
                "direction": "EAST",
                "direction_reason": "DOMINANT_AXIS",
                "rule_risk": "HIGH",
                "ai_risk": "MONITOR",
                "ai_confidence": 0.71,
            },
            "device": {
                "device_id": "esp32-01",
                "status": "ONLINE",
                "last_received_at": "2026-10-03T06:00:00Z",
                "age_seconds": 4,
            },
        },
    }


def test_campus_map_latest_listener_subscribes_once():
    values = run_dashboard_formatters(
        """
        const { subscribeToLatest } = require('./static/js/campus-map.js');
        const listeners = {};
        let registrations = 0;
        const target = {
          addEventListener: (name, listener) => {
            registrations += 1;
            listeners[name] = listener;
          }
        };
        const received = [];
        const subscribe = subscribeToLatest(target, (detail) => received.push(detail));
        const first = subscribe();
        const second = subscribe();
        listeners['watf:latest']({ detail: { measurement: null, device: { status: 'OFFLINE' } } });
        process.stdout.write(JSON.stringify({ first, second, registrations, received }));
        """
    )

    assert values == {
        "first": True,
        "second": False,
        "registrations": 1,
        "received": [{"measurement": None, "device": {"status": "OFFLINE"}}],
    }


def test_campus_map_assets_and_controls_are_wired(client):
    html = client.get("/").get_data(as_text=True)
    campus_javascript = client.get("/static/js/campus-map.js")
    node_javascript = client.get("/static/js/campus-nodes.js")

    assert campus_javascript.status_code == 200
    assert node_javascript.status_code == 200
    assert 'id="campus-node-selector"' in html
    assert 'id="campus-fit-all"' in html
    assert 'id="campus-map-fallback"' in html
    assert 'id="campus-alert-list"' in html
    assert 'id="campus-close-alerts"' in html
    assert "tile.openstreetmap.org" in campus_javascript.get_data(as_text=True)
    assert "L.tileLayer" in campus_javascript.get_data(as_text=True)
    assert "/api/latest" not in campus_javascript.get_data(as_text=True)


def test_live_latest_event_resolves_selected_e12_fields():
    values = run_dashboard_formatters(
        """
        const { CAMPUS_NODES } = require('./static/js/campus-nodes.js');
        const { resolveNodeState } = require('./static/js/campus-map.js');
        const eventDetail = {
          measurement: {
            device_id: 'esp32-01', timestamp: '2026-10-03T06:00:00Z',
            water_level_cm: 5.2, conductivity_ms_cm: 0.48,
            east_rms_v: 0.8, gradient_v: 0.75, direction: 'EAST',
            direction_reason: 'DOMINANT_AXIS', rule_risk: 'HIGH',
            ai_risk: 'MONITOR', ai_confidence: 0.71
          },
          device: {
            device_id: 'esp32-01', status: 'ONLINE',
            last_received_at: '2026-10-03T06:00:00Z', age_seconds: 4
          }
        };
        const state = resolveNodeState(CAMPUS_NODES[0], eventDetail);
        process.stdout.write(JSON.stringify({
          id: state.id, mode: state.mode, status: state.deviceStatus,
          risk: state.risk, water: state.measurement.water_level_cm,
          conductivity: state.measurement.conductivity_ms_cm,
          direction: state.measurement.direction, ai: state.measurement.ai_risk
        }));
        """
    )

    assert values == {
        "id": "esp32-01",
        "mode": "LIVE",
        "status": "ONLINE",
        "risk": "HIGH",
        "water": 5.2,
        "conductivity": 0.48,
        "direction": "EAST",
        "ai": "MONITOR",
    }


def test_map_failure_shows_fallback_without_disabling_monitoring_controls():
    values = run_dashboard_formatters(
        """
        const { showMapFallback } = require('./static/js/campus-map.js');
        const ui = {
          map: { dataset: {} },
          fallback: { hidden: true },
          selector: { disabled: false },
          details: { hidden: false },
          alerts: { hidden: false }
        };
        showMapFallback(ui);
        process.stdout.write(JSON.stringify({
          failed: ui.map.dataset.failed,
          fallbackVisible: !ui.fallback.hidden,
          selectorDisabled: ui.selector.disabled,
          detailsHidden: ui.details.hidden,
          alertsHidden: ui.alerts.hidden
        }));
        """
    )

    assert values == {
        "failed": "true",
        "fallbackVisible": True,
        "selectorDisabled": False,
        "detailsHidden": False,
        "alertsHidden": False,
    }


def test_mobile_map_popups_wrap_and_programmatic_selection_does_not_open_them():
    css = (PROJECT_ROOT / "static/css/dashboard.css").read_text()
    javascript = (PROJECT_ROOT / "static/js/campus-map.js").read_text()

    assert ".campus-popup" in css
    assert "overflow-wrap: anywhere" in css
    assert "maxWidth:" in javascript
    assert "marker.openPopup()" not in javascript


def test_dashboard_uses_plain_labels_and_keeps_diagnostics_in_technical_details(client):
    html = client.get("/").get_data(as_text=True)
    drawer_position = html.index('id="technical-drawer"')

    assert "Device Status" in html
    assert "Last Update" in html
    assert "Signal Level" in html
    assert "Direction Sensors" in html
    assert "Sensor Signal" in html
    assert "Strongest Signal" in html
    assert "Prototype · Not safety-certified" in html
    assert "Synthetic model comparison only" in html
    assert "Strongest measured channel only. This does not confirm the physical source location." in html
    assert html.index("Synthetic model comparison only") > drawer_position
    assert html.index("Strongest measured channel only. This does not confirm the physical source location.") > drawer_position
    assert "Rule risk" not in html
    assert "Synthetic AI comparison" not in html
    assert "Strongest measured direction" not in html


def test_dashboard_simplifies_dynamic_monitoring_messages():
    values = run_dashboard_formatters(
        """
        const dashboard = require('./static/js/dashboard.js');
        process.stdout.write(JSON.stringify({
          monitor: dashboard.riskMessage('MONITOR'),
          lowSignal: dashboard.directionReasonMessage('LOW_SIGNAL'),
          ambiguous: dashboard.directionReasonMessage('AMBIGUOUS')
        }));
        """
    )

    assert values == {
        "monitor": "Check sensor readings.",
        "lowSignal": "No clear signal",
        "ambiguous": "No clear signal",
    }


def test_dashboard_prioritizes_rule_direction_and_compact_measurements(client):
    html = client.get("/").get_data(as_text=True)

    risk_position = html.index('id="risk-card"')
    direction_position = html.index('id="direction-card"')
    measurements_position = html.index('id="key-measurements"')
    workspace_position = html.index('id="monitoring-workspace"')
    assert risk_position < measurements_position
    assert direction_position < measurements_position
    assert measurements_position < workspace_position
    assert 'id="direction-arrow"' in html
    assert 'id="strongest-direction"' in html
    assert 'id="ai-agreement"' in html


def test_dashboard_keeps_raw_fields_inside_technical_drawer(client):
    html = client.get("/").get_data(as_text=True)

    technical_details_position = html.index('id="technical-drawer"')
    for field_name in (
        "water_level_cm",
        "conductivity_ms_cm",
        "north_rms_v",
        "east_rms_v",
        "south_rms_v",
        "west_rms_v",
    ):
        assert html.index(field_name) > technical_details_position

    assert "Technical details" in html
    assert "<th scope=\"col\">AI</th>" in html
    assert 'role="dialog"' in html
    assert 'aria-modal="true"' in html
    assert 'id="open-technical-details"' in html
    assert 'id="close-technical-details"' in html


def test_dashboard_uses_one_shared_analysis_workspace(client):
    html = client.get("/").get_data(as_text=True)

    assert 'id="workspace-tabs" role="tablist"' in html
    assert 'id="workspace-tab-trends"' in html
    assert 'id="workspace-tab-history"' in html
    assert 'id="workspace-tab-events"' in html
    assert 'id="workspace-panel-trends"' in html
    assert 'id="workspace-panel-history"' in html
    assert 'id="workspace-panel-events"' in html
    assert 'aria-selected="true"' in html
    assert 'aria-controls="workspace-panel-history"' in html


def test_dashboard_tab_and_drawer_controllers_preserve_accessibility_state():
    values = run_dashboard_formatters(
        """
        const dashboard = require('./static/js/dashboard.js');
        const selection = dashboard.workspaceSelection(
          'history',
          ['trends', 'history', 'events']
        );
        const calls = [];
        const trigger = { focus: () => calls.push('trigger-focus') };
        const closeButton = { focus: () => calls.push('close-focus') };
        const dialog = {
          showModal: () => calls.push('show'),
          close: () => calls.push('close')
        };
        const controller = dashboard.createDialogController({
          dialog,
          trigger,
          closeButton,
          getActiveElement: () => trigger
        });
        controller.open();
        controller.close();
        controller.restoreFocus();
        process.stdout.write(JSON.stringify({
          selection,
          next: dashboard.nextWorkspaceTab('history', 'ArrowRight', ['trends', 'history', 'events']),
          home: dashboard.nextWorkspaceTab('events', 'Home', ['trends', 'history', 'events']),
          calls
        }));
        """
    )

    assert values == {
        "selection": {
            "trends": {"selected": False, "tabIndex": -1, "hidden": True},
            "history": {"selected": True, "tabIndex": 0, "hidden": False},
            "events": {"selected": False, "tabIndex": -1, "hidden": True},
        },
        "next": "events",
        "home": "trends",
        "calls": ["show", "close-focus", "close", "trigger-focus"],
    }


def test_dashboard_formats_utc_timestamps_and_age_for_local_display():
    values = run_dashboard_formatters(
        """
        const formatters = require('./static/js/dashboard.js');
        process.stdout.write(JSON.stringify({
          full: formatters.formatLocalDateTime('2026-10-03T06:39:13.978Z'),
          time: formatters.formatHistoryTime('2026-10-03T06:39:13.978Z'),
          shortAge: formatters.formatAge(4.2),
          minuteAge: formatters.formatAge(79.4)
        }));
        """
    )

    assert values == {
        "full": "3 Oct 2026 • 13:39:13",
        "time": "13:39:13",
        "shortAge": "4 sec ago",
        "minuteAge": "1 min 19 sec ago",
    }


def test_dashboard_distinguishes_no_reading_from_stale_reading():
    values = run_dashboard_formatters(
        """
        const dashboard = require('./static/js/dashboard.js');
        process.stdout.write(JSON.stringify({
          empty: dashboard.deviceConditionMessage('OFFLINE', null),
          stale: dashboard.deviceConditionMessage('STALE', '2026-10-03T06:39:13.978Z'),
          live: dashboard.deviceConditionMessage('ONLINE', '2026-10-03T06:39:13.978Z'),
          offline: dashboard.deviceConditionMessage('OFFLINE', '2026-10-03T06:39:13.978Z')
        }));
        """
    )

    assert values == {
        "empty": "Waiting for sensor readings.",
        "stale": "Showing last received data.",
        "live": "Receiving live data",
        "offline": "Device offline — showing last data.",
    }


def test_dashboard_assets_are_local_and_available(client):
    css = client.get("/static/css/dashboard.css")
    javascript = client.get("/static/js/dashboard.js")

    assert css.status_code == 200
    assert css.content_type.startswith("text/css")
    assert javascript.status_code == 200
    assert javascript.content_type.startswith("text/javascript")
    assert "https://" not in css.get_data(as_text=True)
    assert "https://" not in javascript.get_data(as_text=True)


def test_dashboard_javascript_handles_live_refresh_and_connection_failure(client):
    javascript = client.get("/static/js/dashboard.js").get_data(as_text=True)

    assert "AbortController" in javascript
    assert "setTimeout(pollLatest" in javascript
    assert "Backend connection warning" in javascript
    assert "No electrical anomaly detected at monitored point" in javascript
    assert "Do not approach the monitored area" in javascript
    assert "deviceConditionMessage" in javascript


def test_dashboard_javascript_uses_bounded_history_and_separate_units(client):
    javascript = client.get("/static/js/dashboard.js").get_data(as_text=True)

    assert "/api/history?limit=100" in javascript
    assert "renderHistory" in javascript
    assert "renderChart" in javascript
    assert "browsingOlder" in javascript
    assert "return-latest" in javascript
    assert "HIGH" in javascript and "CRITICAL" in javascript
