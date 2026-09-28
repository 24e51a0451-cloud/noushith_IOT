import os
import sys
import unittest
from unittest.mock import patch

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from actions.embedded.handler import embedded_handler
from core.input_processor import input_processor
from core.router import router
from core.state import state_manager, Mode


class EmbeddedMappingRegressionTests(unittest.TestCase):
    def setUp(self):
        input_processor.reload()
        router.reload()
        state_manager.reset()

    def test_car_mode_uses_normalized_command(self):
        normalized = input_processor.normalize({"gesture": "push", "mode": "CAR_MODE"})

        self.assertEqual(normalized, "car_forward")

        route = router.route(normalized)
        self.assertEqual(route.domain, "embedded")
        self.assertEqual(route.action, "car_forward")

    def test_embedded_handler_translates_normalized_command_to_payload(self):
        with patch("actions.embedded.handler.mqtt_service.publish", return_value=True) as mock_publish:
            result = embedded_handler.execute("car_forward")

        self.assertTrue(result["success"])
        self.assertEqual(result["payload"], "LIFTCARFORWARD")
        mock_publish.assert_called_once()

    def test_car_360_degrees_execution_and_duration(self):
        with patch("actions.embedded.handler.mqtt_service.publish", return_value=True) as mock_pub:
            res_left = embedded_handler.execute("car_left360")
            self.assertTrue(res_left["success"])
            self.assertEqual(res_left["payload"], "LIFTCARLEFT360")
            self.assertEqual(res_left["duration_ms"], 2000)

            res_right = embedded_handler.execute("car_right360")
            self.assertTrue(res_right["success"])
            self.assertEqual(res_right["payload"], "LIFTCARRIGHT360")
            self.assertEqual(res_right["duration_ms"], 2000)

    def test_wheelchair_360_degrees_execution_and_duration(self):
        with patch("actions.embedded.handler.mqtt_service.publish", return_value=True) as mock_pub:
            res_left = embedded_handler.execute("chair_left360")
            self.assertTrue(res_left["success"])
            self.assertEqual(res_left["payload"], "CHAIRLEFT360")
            self.assertEqual(res_left["duration_ms"], 2000)

            res_right = embedded_handler.execute("chair_right360")
            self.assertTrue(res_right["success"])
            self.assertEqual(res_right["payload"], "CHAIRRIGHT360")
            self.assertEqual(res_right["duration_ms"], 2000)

    def test_embedded_360_routing_and_validation(self):
        for cmd in ["car_left360", "car_right360", "chair_left360", "chair_right360"]:
            route = router.route(cmd)
            self.assertEqual(route.domain, "embedded")
            self.assertEqual(route.action, cmd)

    def test_embedded_360_gesture_normalization(self):
        self.assertEqual(
            input_processor.normalize({"gesture": "360_left", "mode": "CAR_MODE"}),
            "car_left360"
        )
        self.assertEqual(
            input_processor.normalize({"gesture": "360_right", "mode": "CHAIR_MODE"}),
            "chair_right360"
        )


if __name__ == "__main__":
    unittest.main()
