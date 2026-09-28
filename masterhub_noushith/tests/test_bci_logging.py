import json
import unittest
from app import create_app
from cortex.dashboard import _command_logs, _lock, reset as reset_cortex_dashboard
from core.state import state_manager


class BciConsoleLoggingTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.client = self.app.test_client()
        state_manager.reset()
        reset_cortex_dashboard()

    def test_bci_mental_command_logs_to_activity_feed(self):
        # Dispatch a mental command via POST /api/command
        res = self.client.post(
            "/api/command",
            json={
                "gesture": "push",
                "params": {"confidence": 0.96, "source": "bci"},
            },
        )
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data.get("success"))

        # Fetch activity logs
        log_res = self.client.get("/api/activity-logs")
        self.assertEqual(log_res.status_code, 200)
        log_data = log_res.get_json()
        self.assertTrue(log_data.get("success"))
        self.assertGreater(len(log_data.get("logs", [])), 0)

        entry = log_data["logs"][-1]
        self.assertEqual(entry["type"], "BCI")
        self.assertEqual(entry["gesture"], "push")
        self.assertIn("96.0%", entry["confidence"])
        self.assertEqual(entry["status"], "SUCCESS")

    def test_activity_logs_incremental_since_id(self):
        # Send two commands
        self.client.post("/api/command", json={"command": "mode_idle"})
        log_res1 = self.client.get("/api/activity-logs")
        logs1 = log_res1.get_json()["logs"]
        first_id = logs1[-1]["id"]

        self.client.post("/api/command", json={"gesture": "right", "params": {"confidence": 0.88}})
        log_res2 = self.client.get(f"/api/activity-logs?since_id={first_id}")
        logs2 = log_res2.get_json()["logs"]
        self.assertEqual(len(logs2), 1)
        self.assertGreater(logs2[0]["id"], first_id)
        self.assertEqual(logs2[0]["gesture"], "right")

    def test_clear_activity_logs(self):
        self.client.post("/api/command", json={"command": "mode_idle"})
        clear_res = self.client.post("/api/activity-logs/clear")
        self.assertEqual(clear_res.status_code, 200)

        log_res = self.client.get("/api/activity-logs")
        self.assertEqual(len(log_res.get_json()["logs"]), 0)

    def test_bci_command_stored_in_dedicated_log_file(self):
        from services.bci_logger_service import bci_logger
        bci_logger.clear_logs()

        # Simulate headset connection event
        bci_logger.log_headset_connected(
            headset_id="EPOCX-ABC12345",
            session_id="session-xyz-789",
            battery=95.0,
            signal=1.0,
        )

        # Dispatch a BCI mental command
        res = self.client.post(
            "/api/command",
            json={
                "gesture": "left",
                "params": {"confidence": 0.92, "source": "bci"},
            },
        )
        self.assertEqual(res.status_code, 200)

        # Query /api/bci/logs
        bci_res = self.client.get("/api/bci/logs")
        self.assertEqual(bci_res.status_code, 200)
        bci_data = bci_res.get_json()
        self.assertTrue(bci_data["success"])
        self.assertGreaterEqual(bci_data["total_events"], 2)

        events = bci_data["events"]
        conn_event = events[0]
        self.assertEqual(conn_event["event"], "HEADSET_CONNECTED")
        self.assertEqual(conn_event["headset_id"], "EPOCX-ABC12345")

        cmd_event = events[1]
        self.assertEqual(cmd_event["event"], "MENTAL_COMMAND")
        self.assertEqual(cmd_event["gesture"], "left")
        self.assertTrue(cmd_event["accepted"])

        # Test export
        export_res = self.client.get("/api/bci/logs/export")
        self.assertEqual(export_res.status_code, 200)
        export_data = export_res.get_json()
        self.assertTrue(export_data["success"])
        self.assertGreaterEqual(export_data["total_records"], 2)


if __name__ == "__main__":
    unittest.main()
