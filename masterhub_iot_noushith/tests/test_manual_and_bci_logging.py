import json
import unittest
from app import create_app
from core.state import state_manager, Mode
from services.bci_logger_service import bci_logger
from services.manual_logger_service import manual_logger


class ManualAndBciSeparatedLoggingTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.client = self.app.test_client()
        state_manager.reset()
        bci_logger.clear_logs()
        manual_logger.clear_logs()

    def test_all_combination_commands_work_for_bci(self):
        # 1. right+push in JIOSAAVN_MODE -> media_volume_up
        state_manager.transition(Mode.JIOSAAVN_MODE)
        res_vol_up = self.client.post(
            "/api/command",
            json={"gesture": "right+push", "params": {"source": "bci", "confidence": 0.95}},
        )
        self.assertEqual(res_vol_up.status_code, 200)
        self.assertEqual(res_vol_up.get_json()["command"], "media_volume_up")

        # 2. right+pull in JIOSAAVN_MODE -> media_volume_down
        res_vol_down = self.client.post(
            "/api/command",
            json={"gesture": "right+pull", "params": {"source": "bci", "confidence": 0.94}},
        )
        self.assertEqual(res_vol_down.status_code, 200)
        self.assertEqual(res_vol_down.get_json()["command"], "media_volume_down")

        # 3. push+right -> Back (from CAR_MODE to EMBEDDED_MODE)
        state_manager.transition(Mode.CAR_MODE)
        res_back = self.client.post(
            "/api/command",
            json={"gesture": "push+right", "params": {"source": "bci", "confidence": 0.92}},
        )
        self.assertEqual(res_back.status_code, 200)
        self.assertEqual(state_manager.mode, Mode.EMBEDDED_MODE)

        # 4. push+left -> Main menu (resets to IDLE)
        res_menu = self.client.post(
            "/api/command",
            json={"gesture": "push+left", "params": {"source": "bci", "confidence": 0.90}},
        )
        self.assertEqual(res_menu.status_code, 200)
        self.assertEqual(state_manager.mode, Mode.IDLE)

        # Verify BCI log file received all 4 events, and Manual log file has 0
        bci_events = bci_logger.get_recent_events(limit=10)
        manual_events = manual_logger.get_recent_events(limit=10)
        self.assertEqual(len(bci_events), 4)
        self.assertEqual(len(manual_events), 0)

    def test_all_combination_commands_work_for_manual_keyboard(self):
        # 1. right+push in JIOSAAVN_MODE -> media_volume_up
        state_manager.transition(Mode.JIOSAAVN_MODE)
        res_vol_up = self.client.post(
            "/api/command",
            json={
                "gesture": "right+push",
                "params": {"source": "manual_keyboard", "input_type": "keyboard_arrow", "keys": "ArrowRight+ArrowUp"},
            },
        )
        self.assertEqual(res_vol_up.status_code, 200)
        self.assertEqual(res_vol_up.get_json()["command"], "media_volume_up")

        # 2. right+pull in JIOSAAVN_MODE -> media_volume_down
        res_vol_down = self.client.post(
            "/api/command",
            json={
                "gesture": "right+pull",
                "params": {"source": "manual_keyboard", "input_type": "keyboard_arrow", "keys": "ArrowRight+ArrowDown"},
            },
        )
        self.assertEqual(res_vol_down.status_code, 200)
        self.assertEqual(res_vol_down.get_json()["command"], "media_volume_down")

        # 3. push+right -> Back (from YOUTUBE_MODE to DESKTOP_MODE)
        state_manager.transition(Mode.YOUTUBE_MODE)
        res_back = self.client.post(
            "/api/command",
            json={
                "gesture": "push+right",
                "params": {"source": "manual_keyboard", "input_type": "keyboard_arrow", "keys": "ArrowUp+ArrowRight"},
            },
        )
        self.assertEqual(res_back.status_code, 200)
        self.assertEqual(state_manager.mode, Mode.DESKTOP_MODE)

        # 4. push+left -> Main menu (resets to IDLE)
        res_menu = self.client.post(
            "/api/command",
            json={
                "gesture": "push+left",
                "params": {"source": "manual_keyboard", "input_type": "keyboard_arrow", "keys": "ArrowUp+ArrowLeft"},
            },
        )
        self.assertEqual(res_menu.status_code, 200)
        self.assertEqual(state_manager.mode, Mode.IDLE)

        # Verify Manual log file received all 4 events, and BCI log file has 0
        bci_events = bci_logger.get_recent_events(limit=10)
        manual_events = manual_logger.get_recent_events(limit=10)
        self.assertEqual(len(bci_events), 0)
        self.assertEqual(len(manual_events), 4)

        # Query /api/manual/logs endpoint
        res = self.client.get("/api/manual/logs")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["success"])
        self.assertEqual(data["total_events"], 4)
        self.assertEqual(data["events"][0]["keys_pressed"], "ArrowRight+ArrowUp")

    def test_temporal_window_combination_and_single_delay(self):
        # Verify temporal window configuration endpoint
        res_tw = self.client.get("/api/config/temporal-window")
        self.assertEqual(res_tw.status_code, 200)
        self.assertEqual(res_tw.get_json()["temporal_window"], 4.0)

        # Set to 4.0s
        res_set = self.client.post("/api/config/temporal-window", json={"temporal_window": 4.0})
        self.assertEqual(res_set.status_code, 200)
        self.assertEqual(res_set.get_json()["temporal_window"], 4.0)

        # Test combination dispatch for BCI and Manual
        state_manager.transition(Mode.JIOSAAVN_MODE)
        res_vol = self.client.post(
            "/api/command",
            json={"gesture": "right+push", "params": {"source": "bci", "confidence": 0.98}},
        )
        self.assertEqual(res_vol.status_code, 200)
        self.assertEqual(res_vol.get_json()["command"], "media_volume_up")

        # Test single command dispatch
        res_single = self.client.post(
            "/api/command",
            json={"gesture": "left", "params": {"source": "manual_keyboard", "input_type": "keyboard_arrow", "keys": "ArrowLeft"}},
        )
        self.assertEqual(res_single.status_code, 200)
        self.assertEqual(res_single.get_json()["command"], "media_play")


if __name__ == "__main__":
    unittest.main()
