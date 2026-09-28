"""
tests/test_modernization.py
---------------------------
Automated test suite verifying:
- test_dashboard_renders: Modernized dashboard components, buttons, and HUD.
- test_temporal_window_api: GET/POST temporal window values and [2.0s, 10.0s] bounding.
- test_metrics_api: Latency metrics and fault recovery reporting.
- test_command_latency_response: Verified command responses include response, process, and execution latencies.
- Protocol, agent, and state transition test cases.
"""

import os
import sys
import warnings
import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from app import app
from core.state import state_manager, Mode
from core.metrics import metrics_tracker

# Optional compatibility notice warning
warnings.warn("MasterHub modernization test suite initialized with high-precision telemetry.", UserWarning)


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as test_client:
        yield test_client


# 1. Dashboard UI Verification
def test_dashboard_renders(client):
    """Verified dashboard components, buttons, and HUD."""
    response = client.get("/dashboard")
    assert response.status_code == 200
    html = response.get_data(as_text=True)

    # Header & Hamburger
    assert "hamburgerBtn" in html
    assert html.count('class="hamburger-line"') == 3
    assert "themeToggleBtn" in html

    # Sidebar Drawer & Cortex Button
    assert "sidebarDrawer" in html
    assert "sidebarBackdrop" in html
    assert "sidebarCloseBtn" in html
    assert "cortexDashboardBtn" in html
    assert 'href="#bciPanel"' in html
    assert 'id="bciPanel"' in html
    assert "Cortex Dashboard" in html

    # Persistent Left Sidebar Status Matrix
    assert "sidebar-status-matrix" in html
    assert "sideMqttStatus" in html
    assert "sideUartStatus" in html
    assert "sideBciStatus" in html
    assert "sideHealthStatus" in html
    assert "sideActiveFsmMode" in html

    # Performance Metrics HUD
    assert "metricsHud" in html
    assert "hudResponseLatency" in html
    assert "hudProcessLatency" in html
    assert "hudExecutionLatency" in html
    assert "hudFaultRecovery" in html

    # Temporal Window Framing & Observer Card
    assert "temporalWindowCard" in html
    assert "twDisplay" in html
    assert "twGaugeFill" in html
    assert "twPhaseBadge" in html
    assert "twCommandLabel" in html
    assert "twCommandId" in html
    assert "twStatusPill" in html
    assert "twExecuteNowBtn" in html
    assert "twAbortBtn" in html
    assert "twMetaDomain" in html
    assert "twMetaDevice" in html
    assert "twMetaTarget" in html
    assert "twMetaSource" in html
    assert "[ 2s ]" in html
    assert "[ 4s ]" in html
    assert "[ 8s ]" in html

    # UART Target Node Interface (Phase 2)
    assert "uartTargetContainer" in html
    assert 'id="uartNodesGrid"' in html
    assert 'id="deviceButtons"' in html
    assert 'id="commandButtons"' in html

    # PC Agent Node Controller, Register Device Modal, & UART Config Modal
    assert "pcAgentControlCard" in html
    assert "btnRegisterDevice" in html
    assert "btnUartConfig" in html
    assert "registerDeviceModal" in html
    assert "uartConfigModal" in html
    assert "PC_001" in html or "agent_H" in html

    # Real-Time Execution Console & Exporters
    assert "Save JSON" in html
    assert "Save CSV" in html
    assert "Clear" in html


# 2. Temporal Window API Verification
def test_temporal_window_api(client):
    """Verified GET/POST temporal window values and [2.0s, 10.0s] bounding."""
    # GET returns default or current value
    get_res = client.get("/api/config/temporal-window")
    assert get_res.status_code == 200
    get_data = get_res.get_json()
    assert get_data["success"] is True
    assert "temporal_window" in get_data

    # POST valid value
    post_res = client.post("/api/config/temporal-window", json={"temporal_window": 6.5})
    assert post_res.status_code == 200
    post_data = post_res.get_json()
    assert post_data["success"] is True
    assert post_data["temporal_window"] == 6.5

    # Enforce lower bound [2.0s]
    low_res = client.post("/api/config/temporal-window", json={"temporal_window": 1.0})
    assert low_res.status_code == 400
    assert "between 2.0s and 10.0s" in low_res.get_json()["error"]

    # Enforce upper bound [10.0s]
    high_res = client.post("/api/config/temporal-window", json={"temporal_window": 15.0})
    assert high_res.status_code == 400
    assert "between 2.0s and 10.0s" in high_res.get_json()["error"]

    # Boundary edge cases (2.0s and 10.0s exact)
    assert client.post("/api/config/temporal-window", json={"temporal_window": 2.0}).status_code == 200
    assert client.post("/api/config/temporal-window", json={"temporal_window": 10.0}).status_code == 200


def test_temporal_window_api_presets(client):
    """Test quick presets 2s, 4s, 8s."""
    for preset in [2.0, 4.0, 8.0]:
        res = client.post("/api/config/temporal-window", json={"temporal_window": preset})
        assert res.status_code == 200
        assert res.get_json()["temporal_window"] == preset


def test_temporal_window_api_invalid_payload(client):
    """Test invalid payloads to temporal window endpoint."""
    res_empty = client.post("/api/config/temporal-window", json={})
    assert res_empty.status_code == 400

    res_non_num = client.post("/api/config/temporal-window", json={"temporal_window": "invalid"})
    assert res_non_num.status_code == 400


# 3. Performance Metrics API Verification
def test_metrics_api(client):
    """Verified latency metrics and fault recovery reporting."""
    res = client.get("/api/metrics")
    assert res.status_code == 200
    data = res.get_json()
    assert data["success"] is True
    metrics = data["metrics"]

    assert "response_ms" in metrics
    assert "process_ms" in metrics
    assert "execution_ms" in metrics
    assert "fault_recovery" in metrics
    assert "total_commands" in metrics


def test_metrics_api_fault_recovery_optimal(client):
    """Test optimal fault recovery status under successful conditions."""
    metrics_tracker.reset()
    client.post("/api/command", json={"command": "mode_desktop"})
    metrics = client.get("/api/metrics").get_json()["metrics"]
    assert metrics["fault_recovery"] == "100% · OPTIMAL"
    assert metrics["failed_commands"] == 0


def test_metrics_api_fault_recovery_recovered(client):
    """Test self-healing recovery indication after a fault."""
    metrics_tracker.reset()
    # Inject a failure
    client.post("/api/command", json={"command": "unknown_nonexistent_action"})
    # Followed by a success
    client.post("/api/command", json={"command": "mode_idle"})

    metrics = client.get("/api/metrics").get_json()["metrics"]
    assert "RECOVERED" in metrics["fault_recovery"] or "OPTIMAL" in metrics["fault_recovery"]


# 4. Command Latency Verification
def test_command_latency_response(client):
    """Verified command responses include response, process, and execution latencies."""
    res = client.post("/api/command", json={"command": "mode_idle"})
    assert res.status_code == 200
    data = res.get_json()

    assert "response_ms" in data
    assert "process_ms" in data
    assert "execution_ms" in data
    assert isinstance(data["response_ms"], (int, float))
    assert isinstance(data["process_ms"], (int, float))
    assert isinstance(data["execution_ms"], (int, float))


def test_command_latency_response_mode_switch(client):
    """Verified mode switch commands return high-precision latencies."""
    res = client.post("/api/command", json={"command": "mode_media"})
    assert res.status_code == 200
    data = res.get_json()
    assert data["type"] == "mode_switch"
    assert "response_ms" in data
    assert "process_ms" in data
    assert "execution_ms" in data


def test_command_latency_response_invalid_command(client):
    """Verified rejected commands still measure and report latency metrics."""
    res = client.post("/api/command", json={"command": "invalid_command_xyz"})
    assert res.status_code == 422
    data = res.get_json()
    assert "response_ms" in data
    assert "process_ms" in data
    assert "execution_ms" in data


def test_command_latency_response_bad_json(client):
    """Verified bad JSON requests return 400 with latency fields."""
    res = client.post("/api/command", data="not-json", content_type="application/json")
    assert res.status_code == 400
    data = res.get_json()
    assert "response_ms" in data


# 5. Protocol & Agent Status Verification
def test_protocol_iot_status(client):
    """Verified IoT status endpoint protocol info."""
    res = client.get("/api/iot/status")
    assert res.status_code == 200
    data = res.get_json()
    assert data["success"] is True
    assert "mqtt_connected" in data
    assert "online_devices" in data


def test_protocol_embedded_status(client):
    """Verified Embedded status endpoint mobility info."""
    res = client.get("/api/embedded/status")
    assert res.status_code == 200
    data = res.get_json()
    assert data["success"] is True
    assert "robot_car" in data
    assert "wheelchair" in data


def test_agent_state_fsm_transitions(client):
    """Verified state manager FSM transitions and state snapshot."""
    client.post("/api/command", json={"command": "mode_iot"})
    state_res = client.get("/api/state")
    assert state_res.status_code == 200
    state_data = state_res.get_json()
    assert state_data["state"]["mode"] == "IOT_MODE"


# 6. PC Agent & Device Registry API Verification
def test_device_registry_list_api(client):
    """Verify /api/devices returns registered nodes and default targets including PC_001."""
    res = client.get("/api/devices")
    assert res.status_code == 200
    data = res.get_json()
    assert data["success"] is True
    assert "active_target" in data
    devices = {d["device_id"]: d for d in data["devices"]}
    assert "Local Host" in devices
    assert "PC_001" in devices
    assert devices["PC_001"]["transport"] == "mqtt"
    assert not {"PC_002", "PC_003"}.intersection(devices)


def test_device_registration_and_target_api(client):
    """Verify registering a new PC Agent node and setting active target."""
    # Register new PC node
    reg_res = client.post("/api/devices/register", json={
        "device_id": "PC_TEST_99",
        "name": "Lab Test Node",
        "transport": "mqtt",
        "capabilities": ["desktop", "ai_ml"],
    })
    assert reg_res.status_code == 201
    reg_data = reg_res.get_json()
    assert reg_data["success"] is True
    assert reg_data["device"]["device_id"] == "PC_TEST_99"
    assert reg_data["device"]["name"] == "Lab Test Node"

    # Set active target
    target_res = client.post("/api/devices/target", json={"target": "PC_TEST_99"})
    assert target_res.status_code == 200
    assert target_res.get_json()["active_target"] == "PC_TEST_99"

    # Unregister the test device
    del_res = client.delete("/api/devices/PC_TEST_99")
    assert del_res.status_code == 200
    assert del_res.get_json()["success"] is True


def test_pc_agent_remote_command_routing(client):
    """Verify routing a command to a remote PC node generates a MasterHub envelope."""
    from unittest.mock import patch

    with patch("services.mqtt_service.mqtt_service.publish_json", return_value=True) as mock_pub:
        res = client.post("/api/command", json={
            "command": "notepad_open",
            "target": "PC_003"
        })
        assert res.status_code == 200
        data = res.get_json()
        assert data["domain"] == "desktop"
        assert mock_pub.called
        call_args = mock_pub.call_args
        envelope = call_args[0][0]
        topic = call_args[1].get("topic")
        assert topic == "masterhub/devices/PC_003/command"
        assert envelope["protocol"] == "masterhub"
        assert envelope["version"] == "1.0"
        assert envelope["message_type"] == "command"
        assert envelope["target"] == "PC_003"
        assert envelope["action"] == "open_notepad"


def test_pc_agent_remote_media_routing(client):
    """Verify routing AI/ML media commands to a remote PC node generates a MasterHub envelope."""
    from unittest.mock import patch

    with patch("services.mqtt_service.mqtt_service.publish_json", return_value=True) as mock_pub:
        res = client.post("/api/command", json={
            "command": "media_next",
            "target": "PC_001"
        })
        assert res.status_code == 200
        data = res.get_json()
        assert data["domain"] == "ai_ml"
        assert mock_pub.called
        call_args = mock_pub.call_args
        envelope = call_args[0][0]
        topic = call_args[1].get("topic")
        assert topic == "masterhub/devices/PC_001/command"
        assert envelope["protocol"] == "masterhub"
        assert envelope["version"] == "1.0"
        assert envelope["message_type"] == "command"
        assert envelope["target"] == "PC_001"
        assert envelope["domain"] == "ai_ml"
        assert envelope["action"] == "next_track"


def test_pc_agent_uart_remote_command_routing(client):
    """Verify routing a desktop command to a UART-connected PC node dispatches over USB Serial."""
    # Register a UART node
    client.post("/api/devices/register", json={
        "device_id": "PC_UART_NODE",
        "name": "UART Serial Target",
        "transport": "uart",
        "capabilities": ["desktop"],
    })

    # Connect simulated USB serial
    client.post("/api/usb/connect", json={"port": "SIMULATED", "baudrate": 115200})

    res = client.post("/api/command", json={
        "command": "notepad_open",
        "target": "PC_UART_NODE"
    })
    assert res.status_code == 200
    data = res.get_json()
    assert data["domain"] == "desktop"
    assert data.get("transport") == "usb"
    assert data.get("target") == "PC_UART_NODE"

    # Clean up
    client.delete("/api/devices/PC_UART_NODE")
    client.post("/api/usb/disconnect")


def test_usb_endpoints(client):
    """Verify USB serial COM port scanning, connection, and disconnection endpoints."""
    # List ports
    ports_res = client.get("/api/usb/ports")
    assert ports_res.status_code == 200
    ports_data = ports_res.get_json()
    assert ports_data["success"] is True
    assert "ports" in ports_data

    # Status
    status_res = client.get("/api/usb/status")
    assert status_res.status_code == 200
    assert "connected" in status_res.get_json()

    # Connect to simulated port
    conn_res = client.post("/api/usb/connect", json={"port": "SIMULATED", "baudrate": 115200})
    assert conn_res.status_code == 200
    conn_data = conn_res.get_json()
    assert conn_data["success"] is True
    assert conn_data["connected"] is True
    assert conn_data["port"] == "SIMULATED"

    # Verify status reflects connected
    stat_after = client.get("/api/usb/status").get_json()
    assert stat_after["connected"] is True
    assert stat_after["port"] == "SIMULATED"

    # Disconnect
    disc_res = client.post("/api/usb/disconnect")
    assert disc_res.status_code == 200
    assert disc_res.get_json()["success"] is True

    # Status reflects disconnected
    stat_final = client.get("/api/usb/status").get_json()
    assert stat_final["connected"] is False


def test_gmail_routing(client):
    """Verify Gmail commands and aliases are recognized and routed to desktop domain."""
    from unittest.mock import patch

    with patch("actions.desktop.gmail.open_gmail", return_value={"success": True, "action": "open_gmail"}), \
         patch("actions.desktop.gmail.compose_gmail", return_value={"success": True, "action": "compose_gmail"}), \
         patch("actions.desktop.gmail.search_gmail", return_value={"success": True, "action": "search_gmail"}), \
         patch("actions.desktop.gmail.send_gmail", return_value={"success": True, "action": "send_gmail"}):

        for cmd in ["open_gmail", "gmail_open", "compose_gmail", "gmail_compose", "search_gmail", "gmail_search", "send_gmail", "gmail_send"]:
            res = client.post("/api/command", json={"command": cmd, "target": "Local Host"})
            assert res.status_code == 200
            data = res.get_json()
            assert data["domain"] == "desktop"


def test_embedded_360_end_to_end(client):
    """Verify embedded 360 degree actions for robot car and wheelchair dispatch with 2000ms duration."""
    from unittest.mock import patch

    with patch("services.mqtt_service.mqtt_service.publish", return_value=True):
        # Car 360
        res_car_l = client.post("/api/command", json={"command": "car_left360"})
        assert res_car_l.status_code == 200
        data_car_l = res_car_l.get_json()
        assert data_car_l["domain"] == "embedded"
        assert data_car_l["payload"] == "LIFTCARLEFT360"
        assert data_car_l["duration_ms"] == 2000

        res_car_r = client.post("/api/command", json={"command": "car_right360"})
        assert res_car_r.status_code == 200
        data_car_r = res_car_r.get_json()
        assert data_car_r["payload"] == "LIFTCARRIGHT360"
        assert data_car_r["duration_ms"] == 2000

        # Chair 360
        res_chair_l = client.post("/api/command", json={"command": "chair_left360"})
        assert res_chair_l.status_code == 200
        data_chair_l = res_chair_l.get_json()
        assert data_chair_l["domain"] == "embedded"
        assert data_chair_l["payload"] == "CHAIRLEFT360"
        assert data_chair_l["duration_ms"] == 2000

        res_chair_r = client.post("/api/command", json={"command": "chair_right360"})
        assert res_chair_r.status_code == 200
        data_chair_r = res_chair_r.get_json()
        assert data_chair_r["payload"] == "CHAIRRIGHT360"
        assert data_chair_r["duration_ms"] == 2000


# 7. Cortex Dashboard & Telemetry Verification
def test_cortex_dashboard_renders(client):
    """Verify Cortex Classic dashboard renders connection settings, trained profiles, and command console."""
    res = client.get("/cortex/")
    assert res.status_code == 200
    html = res.get_data(as_text=True)

    # Header & Basic Elements
    assert "Cortex Classic" in html
    assert 'id="online"' in html
    assert 'id="connect"' in html
    assert 'id="disconnect"' in html

    # Connection Settings & API Keys Panel
    assert "settingsPanel" in html
    assert "cortexClientId" in html
    assert "cortexClientSecret" in html
    assert "cortexProfileSelect" in html
    assert "saveCredsBtn" in html
    assert "queryProfilesBtn" in html

    # Command & Acknowledgement Console
    assert "consoleBody" in html
    assert "Save JSON" in html
    assert "Save CSV" in html
    assert "Clear" in html


def test_cortex_credentials_api(client):
    """Verify Cortex credentials GET/POST endpoints."""
    # GET credentials (masked)
    get_res = client.get("/cortex/config")
    assert get_res.status_code == 200
    data = get_res.get_json()
    assert data["success"] is True
    assert "client_id" in data
    assert "client_secret" in data
    assert "has_credentials" in data

    # POST new credentials
    post_res = client.post("/cortex/config", json={
        "client_id": "TEST_CLIENT_ID_123",
        "client_secret": "TEST_SECRET_KEY_XYZ_456",
        "profile": "TestUser_Profile",
    })
    assert post_res.status_code == 200
    post_data = post_res.get_json()
    assert post_data["success"] is True
    assert post_data["client_id"] == "TEST_CLIENT_ID_123"
    assert post_data["current_profile"] == "TestUser_Profile"

    # Verify logs received the CONFIG update event
    logs_res = client.get("/cortex/logs")
    assert logs_res.status_code == 200
    logs_data = logs_res.get_json()
    assert logs_data["success"] is True
    assert any(log["type"] == "CONFIG" for log in logs_data["logs"])


def test_cortex_profiles_and_command_logs(client):
    """Verify Cortex profiles listing/loading and command activity logs with timestamps and ACK."""
    # List profiles
    prof_res = client.get("/cortex/profiles")
    assert prof_res.status_code == 200
    assert prof_res.get_json()["success"] is True

    # Load profile
    load_res = client.post("/cortex/profiles/load", json={"profile": "TestUser_Profile"})
    assert load_res.status_code == 200
    assert load_res.get_json()["success"] is True
    assert load_res.get_json()["profile"] == "TestUser_Profile"

    # Simulate command telemetry log event
    from cortex.dashboard import log_command_event
    log_command_event(
        event_type="COMMAND",
        gesture="PUSH",
        confidence="92.4%",
        command="light_on",
        domain="iot",
        acknowledgement="ACK_RECEIVED · 200 OK (38.2ms)",
        status="SUCCESS",
        detail="Dispatched in IOT_MODE",
    )

    # Fetch logs
    logs_res = client.get("/cortex/logs")
    assert logs_res.status_code == 200
    logs = logs_res.get_json()["logs"]
    assert len(logs) > 0

    latest_cmd = next((l for l in logs if l["command"] == "light_on"), None)
    assert latest_cmd is not None
    assert latest_cmd["gesture"] == "PUSH"
    assert latest_cmd["confidence"] == "92.4%"
    assert latest_cmd["acknowledgement"] == "ACK_RECEIVED · 200 OK (38.2ms)"
    assert "timestamp" in latest_cmd
    assert "time" in latest_cmd

    # Clear logs
    clear_res = client.post("/cortex/logs/clear")
    assert clear_res.status_code == 200
    assert client.get("/cortex/logs").get_json()["total"] == 0

