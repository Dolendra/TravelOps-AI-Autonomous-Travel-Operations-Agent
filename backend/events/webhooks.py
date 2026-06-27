import logging
import asyncio
import requests
from typing import Dict, Any, List
from backend.database.db import SessionLocal
from backend.database.models import DeadLetterModel

logger = logging.getLogger("travelops.events.webhooks")

class WebhookDispatcher:
    # A list of configured targets (for simulation)
    # E.g. Slack mock, Discord mock, and custom webhooks
    WEBHOOK_TARGETS = [
        "https://hooks.slack.com/services/mock-slack-webhook",
        "https://discord.com/api/webhooks/mock-discord-webhook",
        # Adding a simulation endpoint that triggers a network failure
        "http://mock-failure-webhook.local/api/alerts"
    ]
    
    MAX_RETRIES = 3
    RETRY_DELAY_SEC = 1.0

    @classmethod
    async def dispatch_event_to_all(cls, session_id: str, payload: Dict[str, Any]):
        """Triggered by the Event Bus to publish event updates to external endpoints."""
        event_type = payload.get("event_type", "TelemetryAlert")
        tasks = []
        for target in cls.WEBHOOK_TARGETS:
            tasks.append(cls._dispatch_with_retry(target, event_type, session_id, payload))
        await asyncio.gather(*tasks)

    @classmethod
    async def _dispatch_with_retry(cls, target_url: str, event_type: str, session_id: str, payload: Dict[str, Any]):
        """Dispatches payload to a single endpoint with exponential retry and DLQ logic."""
        logger.info(f"Initiating webhook dispatch for {event_type} to: {target_url}")
        
        import random
        attempt = 1
        success = False
        last_error = ""

        while attempt <= cls.MAX_RETRIES:
            try:
                # Simulation details
                if "mock-failure-webhook" in target_url:
                    # Intentionally raise an exception to test retry and DLQ logic
                    raise requests.RequestException("Connection timeout to simulated server.")
                
                # Mock a successful post request
                logger.info(f"[Webhook Success] Sent {event_type} to {target_url} (Attempt {attempt})")
                success = True
                break
            except Exception as e:
                last_error = str(e)
                logger.warning(f"[Webhook Warning] Attempt {attempt} failed for {target_url}: {last_error}")
                attempt += 1
                if attempt <= cls.MAX_RETRIES:
                    # Exponential delay: base_delay * (2 ^ (attempt - 1)) + jitter
                    base_delay = cls.RETRY_DELAY_SEC * (2 ** (attempt - 2))
                    jitter = base_delay * random.uniform(0.0, 0.2)
                    total_delay = base_delay + jitter
                    logger.info(f"Sleeping for {total_delay:.2f}s before retry attempt {attempt}...")
                    await asyncio.sleep(total_delay)

        if not success:
            logger.error(f"[Webhook Failure] Max retries reached for {target_url}. Moving to DLQ...")
            cls._send_to_dead_letter_queue(event_type, session_id, payload, f"Target: {target_url} | Error: {last_error}")

    @classmethod
    def _send_to_dead_letter_queue(cls, event_type: str, session_id: str, payload: Dict[str, Any], error_msg: str):
        """Saves the failed alert payload to the database Dead Letter Queue."""
        db = SessionLocal()
        try:
            dlq_entry = DeadLetterModel(
                event_type=event_type,
                session_id=session_id,
                last_error=error_msg
            )
            dlq_entry.set_payload(payload)
            db.add(dlq_entry)
            db.commit()
            logger.info(f"Failed webhook event successfully written to database Dead Letter Queue (ID: {dlq_entry.id})")
        except Exception as e:
            logger.critical(f"Failed to write to database DLQ: {e}")
        finally:
            db.close()
