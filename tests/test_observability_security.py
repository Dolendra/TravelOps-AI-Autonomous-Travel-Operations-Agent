import unittest
import time
from fastapi.testclient import TestClient
from backend.api.main import app, limiter
from backend.database.db import init_db, SessionLocal, Base, engine


class TestObservabilitySecurity(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import os
        os.environ["DATABASE_URL"] = "sqlite:///:memory:"
        init_db()

    def setUp(self):
        self.client = TestClient(app)
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)
        # Reset limiter client records for clean runs
        limiter.client_records.clear()

    def test_metrics_endpoint_format(self):
        response = self.client.get("/metrics")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["content-type"], "text/plain; charset=utf-8")
        
        # Verify key Prometheus metrics lines are present
        content = response.text
        self.assertIn("travelops_active_sessions_total", content)
        self.assertIn("travelops_llm_calls_total", content)
        self.assertIn("travelops_llm_cost_usd_total", content)
        self.assertIn("travelops_tool_execution_failures_total", content)
        self.assertIn("travelops_api_requests_total", content)

    def test_rate_limiter_blocks(self):
        # Configure rate limiter to trip quickly for tests
        original_limit = limiter.requests_limit
        limiter.requests_limit = 5
        
        # Trigger 5 calls (which return 401 because they lack authentication, showing they went past rate limit check)
        for _ in range(5):
            response = self.client.post("/api/sessions", json={"session_id": "test_limiter"})
            self.assertEqual(response.status_code, 401)
            
        # The 6th call should trigger HTTP 429 Too Many Requests
        response = self.client.post("/api/sessions", json={"session_id": "test_limiter"})
        self.assertEqual(response.status_code, 429)
        self.assertIn("Rate limit exceeded", response.json()["detail"])
        
        # Restore limit
        limiter.requests_limit = original_limit

    def test_trace_id_propagation(self):
        # Trigger query
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertIn("X-Trace-ID", response.headers)
        self.assertTrue(response.headers["X-Trace-ID"].startswith("trace_"))


if __name__ == "__main__":
    unittest.main()
