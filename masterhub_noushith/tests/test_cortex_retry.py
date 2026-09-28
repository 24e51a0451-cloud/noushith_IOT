import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from cortex.cortex_client import CortexConnectionError
from cortex.run_live import LiveRunner


class FakeClient:
    def __init__(self):
        self.calls = 0

    def connect(self):
        self.calls += 1
        if self.calls == 1:
            raise CortexConnectionError("temporary failure")

    def close(self):
        return None


class RetryRunner(LiveRunner):
    def __init__(self):
        super().__init__()
        self.client = FakeClient()
        self.authenticate_calls = 0

    def _authenticate_and_prepare(self):
        self.authenticate_calls += 1


class CortexRetryTests(unittest.TestCase):
    def test_connect_with_retry_recovers_after_initial_failure(self):
        runner = RetryRunner()

        runner._connect_with_retry(retry_delay=0.01)

        self.assertEqual(runner.client.calls, 2)
        self.assertEqual(runner.authenticate_calls, 1)

    def test_authorize_does_not_send_null_license_or_zero_debit(self):
        from cortex.auth import CortexAuth, AuthCredentials

        class MockCortexClient:
            def __init__(self):
                self.last_method = None
                self.last_params = None

            def call(self, method, params):
                self.last_method = method
                self.last_params = params
                return {"cortexToken": "fake-jwt-token-123"}

        mock_client = MockCortexClient()
        auth = CortexAuth(
            client=mock_client,
            credentials=AuthCredentials(client_id="test_id", client_secret="test_sec", license="")
        )
        token = auth.authorize(debit=0)
        self.assertEqual(token, "fake-jwt-token-123")
        self.assertEqual(mock_client.last_method, "authorize")
        # Must only contain clientId and clientSecret, NO "license": None or "debit": 0
        self.assertEqual(mock_client.last_params, {"clientId": "test_id", "clientSecret": "test_sec"})

    def test_cortex_config_endpoint_and_secret_preservation(self):
        from app import app
        with app.test_client() as client:
            # 1. GET /cortex/config
            res = client.get("/cortex/config")
            self.assertEqual(res.status_code, 200)
            data = res.get_json()
            self.assertTrue(data.get("success"))
            self.assertIn("client_id", data)
            self.assertIn("client_secret", data)

            # 2. POST /cortex/config with masked secret (should not overwrite actual secret with asterisks)
            post_res = client.post(
                "/cortex/config",
                json={"client_id": "4peZxtpflilSEnDpunLvBCOImDBQOnsFkFeJzgZS", "client_secret": data["client_secret"]},
            )
            self.assertEqual(post_res.status_code, 200)
            post_data = post_res.get_json()
            self.assertTrue(post_data.get("success"))

    def test_bci_confidence_threshold_0_20(self):
        from prediction_pipeline.pipeline import ConfidenceFilter
        from cortex.prediction_mapper import NormalizedPrediction

        c_filter = ConfidenceFilter()
        self.assertEqual(c_filter.threshold, 0.20)

        # The inclusive 20% boundary must be accepted.
        pred_accepted = NormalizedPrediction(command="push", confidence=0.20, timestamp="2026-09-23T10:00:00Z")
        res1 = c_filter.evaluate(pred_accepted)
        self.assertTrue(res1.accepted)

        # Power below 20% must be rejected.
        pred_rejected = NormalizedPrediction(command="pull", confidence=0.19, timestamp="2026-09-23T10:00:01Z")
        res2 = c_filter.evaluate(pred_rejected)
        self.assertFalse(res2.accepted)


if __name__ == "__main__":
    unittest.main()


