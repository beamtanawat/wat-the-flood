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
