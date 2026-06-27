import uuid
import logging
import asyncio
from datetime import datetime
from typing import Dict, List, Callable, Any, Awaitable
from backend.database.db import SessionLocal
from backend.database.models import EventStoreModel

logger = logging.getLogger("travelops.events.event_bus")

class EventBus:
    _subscribers: Dict[str, List[Callable[[str, Dict[str, Any]], Awaitable[None]]]] = {}
    _lock = asyncio.Lock()

    @classmethod
    async def subscribe(cls, event_type: str, callback: Callable[[str, Dict[str, Any]], Awaitable[None]]):
        """
        Registers an async subscriber callback for a specific event type.
        """
        async with cls._lock:
            if event_type not in cls._subscribers:
                cls._subscribers[event_type] = []
            cls._subscribers[event_type].append(callback)
            logger.info(f"Subscribed callback {callback.__name__} to event: {event_type}")

    @classmethod
    async def publish(cls, event_type: str, session_id: str, payload: Dict[str, Any]):
        """
        Publishes an event.
        1. Persists the event in the database Event Store.
        2. Dispatches it asynchronously to all active subscribers.
        """
        event_id = str(uuid.uuid4())
        logger.info(f"Publishing event {event_type} [ID: {event_id}] for session {session_id}")

        # Step 1: Save to Event Store
        db = SessionLocal()
        try:
            event_entry = EventStoreModel(
                id=event_id,
                event_type=event_type,
                session_id=session_id,
                timestamp=datetime.utcnow()
            )
            event_entry.set_payload(payload)
            db.add(event_entry)
            db.commit()
            logger.info(f"Event {event_id} successfully persisted in Event Store.")
        except Exception as e:
            logger.error(f"Failed to persist event {event_id} in Event Store: {e}")
        finally:
            db.close()

        # Step 2: Notify subscribers
        subscribers = cls._subscribers.get(event_type, [])
        if not subscribers:
            logger.info(f"No active subscribers for event: {event_type}")
            return

        tasks = []
        for cb in subscribers:
            # Wrap in try-except to prevent one subscriber failure from crashing others
            async def safe_cb(callback=cb):
                try:
                    await callback(session_id, payload)
                except Exception as ex:
                    logger.error(f"Subscriber callback {callback.__name__} raised exception: {ex}")

            tasks.append(safe_cb())

        # Execute all subscribers concurrently
        await asyncio.gather(*tasks)
        logger.info(f"Event {event_type} [ID: {event_id}] dispatched to {len(subscribers)} subscribers.")
