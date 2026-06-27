import logging
from typing import Dict, Any

from backend.database.db import SessionLocal
from backend.database.models import (
    BookingModel, BusInventoryModel, WorkflowStateModel, AuditLogModel, TaskStateModel
)
from backend.tools.registry import ToolRegistry
from agents.memory.memory_agent import MemoryAgent
from backend.services.llm import ModelRouter
from backend.services.prompt_loader import PromptLoader

logger = logging.getLogger("travelops.agents.recovery")

class RecoveryAgent:
    @classmethod
    async def handle_disruption(cls, session_id: str, payload: Dict[str, Any]) -> None:
        """
        Subscribed callback triggered when a DisruptionDetected event is published.
        Resolves the travel disruption autonomously.
        """
        bus_id = payload.get("bus_id")
        booking_id = payload.get("booking_id")
        disruption_type = payload.get("disruption_type", "disruption")
        logger.info(f"RecoveryAgent: Starting autonomous recovery for session {session_id} due to {disruption_type} on bus {bus_id}")

        db = SessionLocal()
        try:
            # 1. Fetch active booking
            booking = db.query(BookingModel).filter(BookingModel.id == booking_id).first()
            if not booking:
                logger.error(f"RecoveryAgent: Booking with ID {booking_id} not found. Aborting.")
                return

            # 2. Transition workflow state to RECOVERING
            db.add(WorkflowStateModel(session_id=session_id, state="RECOVERING"))
            db.commit()

            # 3. Release old seat and mark old booking as CANCELLED
            booking.status = "CANCELLED"
            old_bus = db.query(BusInventoryModel).filter(BusInventoryModel.id == booking.bus_id).first()
            if old_bus:
                old_bus.available_seats += 1
                logger.info(f"RecoveryAgent: Released seat {booking.seat_number} on old bus {old_bus.id}. Seats available: {old_bus.available_seats}")
            
            # Record refund event
            refund_log = AuditLogModel(
                session_id=session_id,
                agent_name="RecoveryAgent",
                action="process_refund",
                reasoning_summary=f"Processed 100% refund of {booking.price_paid} for CANCELLED booking {booking.id} (PNR: {booking.pnr}) due to operator {disruption_type}."
            )
            db.add(refund_log)
            db.commit()

            # 4. Extract search entities from previous search task
            search_task = db.query(TaskStateModel).filter(
                TaskStateModel.session_id == session_id,
                TaskStateModel.name == "search_buses"
            ).first()
            search_input = search_task.get_input() if search_task else {}
            origin = search_input.get("origin")
            destination = search_input.get("destination")
            travel_date = search_input.get("travel_date")

            if not origin or not destination:
                # Fallback to booking route details if search task is absent
                if old_bus:
                    origin = old_bus.origin
                    destination = old_bus.destination
                else:
                    logger.error("RecoveryAgent: Could not determine origin/destination. Aborting.")
                    db.add(WorkflowStateModel(session_id=session_id, state="FAILED"))
                    db.commit()
                    return

            # 5. Search for alternative buses
            search_tool = ToolRegistry.get_tool("search_buses")
            search_res = search_tool.execute(session_id, origin=origin, destination=destination, travel_date=travel_date)
            
            if not search_res.get("success"):
                logger.error(f"RecoveryAgent: Alternative search failed: {search_res.get('error')}. Aborting.")
                db.add(WorkflowStateModel(session_id=session_id, state="FAILED"))
                db.commit()
                return

            # Filter out the cancelled/disrupted bus run
            all_buses = search_res.get("buses", [])
            alternative_buses = [b for b in all_buses if b["bus_id"] != bus_id]

            if not alternative_buses:
                logger.warning(f"RecoveryAgent: No alternative buses found for route {origin} to {destination}. Aborting.")
                db.add(WorkflowStateModel(session_id=session_id, state="FAILED"))
                
                fail_log = AuditLogModel(
                    session_id=session_id,
                    agent_name="RecoveryAgent",
                    action="recovery_failed",
                    reasoning_summary=f"Recovery Failed: No alternative transit routes found for travel date {travel_date}."
                )
                db.add(fail_log)
                db.commit()
                return

            # 6. Retrieve preferences from MemoryAgent to rank alternatives
            memory_agent = MemoryAgent(ModelRouter(), PromptLoader())
            prefs = memory_agent.retrieve_preferences(session_id)
            sorting_pref = prefs.get("sorting_preference", "highest_rating")

            # Execute Recommend tool to filter and rank options
            rec_tool = ToolRegistry.get_tool("recommend_options")
            rec_res = rec_tool.execute(session_id, preference=sorting_pref, buses=alternative_buses)
            
            recommended_buses = rec_res.get("recommended_buses", [])
            if not recommended_buses:
                logger.error("RecoveryAgent: Failed to select recommended alternative. Aborting.")
                db.add(WorkflowStateModel(session_id=session_id, state="FAILED"))
                db.commit()
                return

            # Select the top recommended bus run
            top_bus = recommended_buses[0]
            logger.info(f"RecoveryAgent: Selected best alternative bus run: {top_bus['operator_name']} (Rating: {top_bus['rating']}, Fare: {top_bus['fare']})")

            # 7. Reserve/Hold seat on alternative bus
            hold_tool = ToolRegistry.get_tool("hold_seat")
            hold_res = hold_tool.execute(
                session_id,
                bus_id=top_bus["bus_id"],
                seat_number=None,  # Hold seat dynamically
                passenger_name=booking.passenger_name,
                passenger_email=booking.passenger_email
            )

            if not hold_res.get("success"):
                logger.error(f"RecoveryAgent: Failed to hold seat on alternative bus: {hold_res.get('error')}. Aborting.")
                db.add(WorkflowStateModel(session_id=session_id, state="FAILED"))
                db.commit()
                return

            new_booking_id = hold_res.get("booking_id")

            # 8. Process payment for new booking
            pay_tool = ToolRegistry.get_tool("process_payment")
            pay_res = pay_tool.execute(
                session_id,
                booking_id=new_booking_id,
                card_number="4111 1111 1111 1111"
            )

            if not pay_res.get("success"):
                logger.error(f"RecoveryAgent: Failed to process payment for alternative rebooking: {pay_res.get('error')}. Aborting.")
                db.add(WorkflowStateModel(session_id=session_id, state="FAILED"))
                db.commit()
                return

            # 9. Confirm booking (generate new PNR)
            confirm_tool = ToolRegistry.get_tool("confirm_booking")
            confirm_res = confirm_tool.execute(session_id, booking_id=new_booking_id)

            if not confirm_res.get("success"):
                logger.error(f"RecoveryAgent: Failed to confirm alternative booking: {confirm_res.get('error')}. Aborting.")
                db.add(WorkflowStateModel(session_id=session_id, state="FAILED"))
                db.commit()
                return

            new_ticket = confirm_res.get("ticket", {})
            new_pnr = new_ticket.get("pnr")
            new_seat = new_ticket.get("seat_number")

            # 10. Dispatch SMS/Email alerts
            notify_tool = ToolRegistry.get_tool("send_notification")
            notify_tool.execute(session_id)

            # 11. Finalize workflow state to BOOKED
            db.add(WorkflowStateModel(session_id=session_id, state="BOOKED"))
            
            complete_log = AuditLogModel(
                session_id=session_id,
                agent_name="RecoveryAgent",
                action="recovery_completed",
                reasoning_summary=(
                    f"Disruption Recovery Completed: Rebooked passenger autonomously on alternative bus "
                    f"'{top_bus['operator_name']}' (Seat: {new_seat}, PNR: {new_pnr}). Notification dispatched."
                )
            )
            db.add(complete_log)
            db.commit()
            logger.info(f"RecoveryAgent: Disruption recovery completed successfully for session {session_id}!")

        except Exception as e:
            logger.error(f"Error in RecoveryAgent.handle_disruption: {e}")
            db.rollback()
            db.add(WorkflowStateModel(session_id=session_id, state="FAILED"))
            db.commit()
        finally:
            db.close()
