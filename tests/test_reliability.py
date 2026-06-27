import unittest
import time
from unittest.mock import patch, MagicMock
from backend.services.reliability import (
    CircuitBreaker, CircuitBreakerOpenException, ExponentialBackoff,
    get_idempotent_result, save_idempotent_result
)
from backend.database.db import SessionLocal, init_db, engine, Base
from backend.database.models import CacheModel


class TestReliabilityPatterns(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Configure in-memory database
        import os
        os.environ["DATABASE_URL"] = "sqlite:///:memory:"
        init_db()

    def setUp(self):
        self.db = SessionLocal()
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)

    def tearDown(self):
        self.db.close()

    def test_circuit_breaker_transitions(self):
        cb = CircuitBreaker("test_breaker", failure_threshold=2, recovery_timeout=0.2)
        
        # Initial state should be CLOSED
        self.assertEqual(cb.state, "CLOSED")

        calls = []
        def failing_call():
            calls.append(1)
            raise Exception("Failure")

        def successful_call():
            calls.append(2)
            return "Success"

        # Failure 1
        with self.assertRaises(Exception):
            cb.call(failing_call)
        self.assertEqual(cb.state, "CLOSED")
        self.assertEqual(cb.failure_count, 1)

        # Failure 2 - trips circuit
        with self.assertRaises(Exception):
            cb.call(failing_call)
        self.assertEqual(cb.state, "OPEN")
        self.assertEqual(cb.failure_count, 2)

        # Immediate next call should fail-fast without executing the function
        calls.clear()
        with self.assertRaises(CircuitBreakerOpenException):
            cb.call(successful_call)
        self.assertEqual(len(calls), 0)

        # Wait for recovery timeout
        time.sleep(0.25)

        # First call after recovery transitions to HALF_OPEN and executes the call
        result = cb.call(successful_call)
        self.assertEqual(result, "Success")
        self.assertEqual(cb.state, "CLOSED")  # Transitions back to CLOSED immediately upon success
        self.assertEqual(cb.failure_count, 0)

    def test_exponential_backoff_success(self):
        calls = []
        def flaky_func():
            calls.append(1)
            if len(calls) < 3:
                raise ValueError("Transient error")
            return "Done"

        # Should retry twice, and succeed on the third attempt
        result = ExponentialBackoff.execute(flaky_func, max_retries=3, base_delay=0.01, factor=2.0)
        self.assertEqual(result, "Done")
        self.assertEqual(len(calls), 3)

    def test_idempotency_caching(self):
        idem_key = "test-key-123"
        payload = {"booking_id": 99, "status": "CONFIRMED", "amount_paid": 950.0}

        # 1. No cache entry initially
        self.assertIsNone(get_idempotent_result(self.db, idem_key))

        # 2. Save result
        save_idempotent_result(self.db, idem_key, payload, ttl_seconds=10)

        # 3. Retrieve result
        cached = get_idempotent_result(self.db, idem_key)
        self.assertIsNotNone(cached)
        self.assertEqual(cached["booking_id"], 99)
        self.assertEqual(cached["status"], "CONFIRMED")

        # 4. Check expired cache
        save_idempotent_result(self.db, idem_key, payload, ttl_seconds=-1)
        expired = get_idempotent_result(self.db, idem_key)
        self.assertIsNone(expired)


if __name__ == "__main__":
    unittest.main()
