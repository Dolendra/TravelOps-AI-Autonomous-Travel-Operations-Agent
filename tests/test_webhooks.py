import unittest
import asyncio
from backend.database.db import SessionLocal
from backend.database.models import DeadLetterModel
from backend.events.webhooks import WebhookDispatcher

class TestWebhookRetryDLQ(unittest.TestCase):
    def setUp(self):
        # Clear DLQ logs for test isolation
        db = SessionLocal()
        try:
            db.query(DeadLetterModel).delete()
            db.commit()
        finally:
            db.close()

    def test_webhook_retry_and_dlq(self):
        """Verifies that failed webhooks trigger retries and persist to DLQ."""
        session_id = "test_webhook_session_123"
        payload = {
            "event_type": "BusCancelled",
            "session_id": session_id,
            "bus_id": 999
        }
        
        # Shorten delay during tests to run instantly
        original_delay = WebhookDispatcher.RETRY_DELAY_SEC
        WebhookDispatcher.RETRY_DELAY_SEC = 0.01
        
        try:
            # Run async dispatcher
            asyncio.run(WebhookDispatcher.dispatch_event_to_all(session_id, payload))
        finally:
            WebhookDispatcher.RETRY_DELAY_SEC = original_delay

        # Verify DLQ entries
        db = SessionLocal()
        try:
            entries = db.query(DeadLetterModel).filter(DeadLetterModel.session_id == session_id).all()
            self.assertEqual(len(entries), 1)
            self.assertEqual(entries[0].event_type, "BusCancelled")
            self.assertIn("mock-failure-webhook", entries[0].last_error)
            self.assertIn("Connection timeout", entries[0].last_error)
        finally:
            db.close()

if __name__ == "__main__":
    unittest.main()
