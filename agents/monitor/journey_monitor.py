import logging
from typing import Dict, Any
from backend.database.db import SessionLocal
from backend.database.models import BookingModel, WorkflowStateModel, AuditLogModel
from backend.events.event_bus import EventBus

logger = logging.getLogger("travelops.agents.monitor")

class JourneyMonitor:
    @classmethod
    async def handle_bus_cancelled(cls, session_id: str, payload: Dict[str, Any]) -> None:
        """
        Subscribed callback triggered when a BusCancelled event is received.
        """
        bus_id = payload.get("bus_id")
        reason = payload.get("reason", "unknown reason")
        logger.info(f"JourneyMonitor: Received BusCancelled event for bus {bus_id} in session {session_id}")

        db = SessionLocal()
        try:
            # Check if there is an active CONFIRMED or HELD booking in this session for the cancelled bus
            active_booking = db.query(BookingModel).filter(
                BookingModel.session_id == session_id,
                BookingModel.bus_id == bus_id,
                BookingModel.status.in_(["HELD", "CONFIRMED"])
            ).first()

            if active_booking:
                logger.warning(f"JourneyMonitor: Active booking {active_booking.id} is impacted by bus cancellation.")
                
                # 1. Update workflow state to DISRUPTED
                db.add(WorkflowStateModel(session_id=session_id, state="DISRUPTED"))
                
                # 2. Write an audit log entry
                audit = AuditLogModel(
                    session_id=session_id,
                    agent_name="JourneyMonitor",
                    action="disruption_detected",
                    reasoning_summary=f"Disruption Detected: Bus {bus_id} has been cancelled by operator due to: {reason}. Active booking {active_booking.id} (PNR: {active_booking.pnr}) is impacted."
                )
                audit.set_payload(payload)
                db.add(audit)
                db.commit()

                # 3. Publish DisruptionDetected event to trigger recovery agent
                disruption_payload = {
                    "session_id": session_id,
                    "bus_id": bus_id,
                    "booking_id": active_booking.id,
                    "disruption_type": "cancellation",
                    "reason": reason
                }
                await EventBus.publish("DisruptionDetected", session_id, disruption_payload)
            else:
                logger.info(f"JourneyMonitor: No active bookings for bus {bus_id} in session {session_id}. No action needed.")
        except Exception as e:
            logger.error(f"Error in JourneyMonitor.handle_bus_cancelled: {e}")
        finally:
            db.close()

    @classmethod
    async def handle_bus_delayed(cls, session_id: str, payload: Dict[str, Any]) -> None:
        """
        Subscribed callback triggered when a BusDelayed event is received.
        """
        bus_id = payload.get("bus_id")
        delay_minutes = payload.get("delay_minutes", 0)
        logger.info(f"JourneyMonitor: Received BusDelayed event for bus {bus_id} in session {session_id} (delay: {delay_minutes} mins)")

        # Only trigger disruption if delay exceeds 120 minutes (2 hours)
        if delay_minutes < 120:
            logger.info(f"JourneyMonitor: Delay is {delay_minutes} minutes (< 120 mins threshold). Monitoring only.")
            return

        db = SessionLocal()
        try:
            active_booking = db.query(BookingModel).filter(
                BookingModel.session_id == session_id,
                BookingModel.bus_id == bus_id,
                BookingModel.status.in_(["HELD", "CONFIRMED"])
            ).first()

            if active_booking:
                logger.warning(f"JourneyMonitor: Active booking {active_booking.id} is impacted by excessive bus delay ({delay_minutes} mins).")
                
                # 1. Update workflow state to DISRUPTED
                db.add(WorkflowStateModel(session_id=session_id, state="DISRUPTED"))
                
                # 2. Write an audit log entry
                audit = AuditLogModel(
                    session_id=session_id,
                    agent_name="JourneyMonitor",
                    action="disruption_detected",
                    reasoning_summary=f"Disruption Detected: Bus {bus_id} has been delayed by {delay_minutes} minutes. Active booking {active_booking.id} (PNR: {active_booking.pnr}) is impacted."
                )
                audit.set_payload(payload)
                db.add(audit)
                db.commit()

                # 3. Publish DisruptionDetected event to trigger recovery agent
                disruption_payload = {
                    "session_id": session_id,
                    "bus_id": bus_id,
                    "booking_id": active_booking.id,
                    "disruption_type": "delay",
                    "delay_minutes": delay_minutes
                }
                await EventBus.publish("DisruptionDetected", session_id, disruption_payload)
            else:
                logger.info(f"JourneyMonitor: No active bookings for bus {bus_id} in session {session_id}. No action needed.")
        except Exception as e:
            logger.error(f"Error in JourneyMonitor.handle_bus_delayed: {e}")
        finally:
            db.close()
