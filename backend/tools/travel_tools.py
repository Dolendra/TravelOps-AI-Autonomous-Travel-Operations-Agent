import json
import time
import uuid
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from sqlalchemy import func

from backend.tools.registry import BaseTool, register_tool
from backend.database.db import SessionLocal
from backend.database.models import (
    BusInventoryModel, BookingModel, CacheModel, TaskStateModel
)

logger = logging.getLogger("travelops.tools.travel_tools")


def luhn_check(card_num: str) -> bool:
    """Verifies card number using the Luhn algorithm."""
    # Strip spaces or dashes
    card_num = card_num.replace(" ", "").replace("-", "")
    if not card_num.isdigit() or len(card_num) < 13:
        return False
        
    digits = [int(d) for d in card_num]
    # Double every second digit from the right
    for i in range(len(digits) - 2, -1, -2):
        double_val = digits[i] * 2
        if double_val > 9:
            double_val -= 9
        digits[i] = double_val
    return sum(digits) % 10 == 0


def get_task_output_helper(db, session_id: str, task_name: str) -> Dict[str, Any]:
    """Helper to extract output of a previously completed task in the session."""
    task = db.query(TaskStateModel).filter(
        TaskStateModel.session_id == session_id,
        TaskStateModel.name == task_name
    ).first()
    if task and task.output_raw:
        try:
            return json.loads(task.output_raw)
        except Exception:
            pass
    return {}


@register_tool
class SearchBusTool(BaseTool):
    @property
    def name(self) -> str:
        return "search_buses"

    @property
    def description(self) -> str:
        return "Queries the intercity bus inventory by origin, destination, and travel_date. Arguments: origin (str), destination (str), travel_date (str)."

    def execute(self, session_id: str, **kwargs) -> Dict[str, Any]:
        origin = kwargs.get("origin")
        destination = kwargs.get("destination")
        travel_date = kwargs.get("travel_date")

        if not origin or not destination:
            return {"success": False, "error": "Missing required search parameters: 'origin' and 'destination'."}
            
        if not travel_date:
            travel_date = (datetime.utcnow() + timedelta(days=1)).strftime("%Y-%m-%d")

        db = SessionLocal()
        try:
            # 1. Check cache first
            cache_key = f"search:{origin.lower()}:{destination.lower()}:{travel_date}"
            cache_entry = db.query(CacheModel).filter(CacheModel.key == cache_key).first()
            if cache_entry and (not cache_entry.expires_at or cache_entry.expires_at > datetime.utcnow()):
                logger.info(f"Cache hit for key: {cache_key}")
                buses = json.loads(cache_entry.value)
                return {"success": True, "buses": buses, "cache_hit": True}

            # 2. Query Database
            logger.info(f"Cache miss. Querying DB for {origin} to {destination} on {travel_date}")
            query = db.query(BusInventoryModel).filter(
                func.lower(BusInventoryModel.origin) == origin.lower(),
                func.lower(BusInventoryModel.destination) == destination.lower()
            )
            results = query.all()
            
            buses = []
            for bus in results:
                buses.append({
                    "bus_id": bus.id,
                    "operator_name": bus.operator_name,
                    "bus_type": bus.bus_type,
                    "departure_time": bus.departure_time,
                    "arrival_time": bus.arrival_time,
                    "duration": bus.duration,
                    "origin": bus.origin,
                    "destination": bus.destination,
                    "fare": bus.fare,
                    "rating": bus.rating,
                    "available_seats": bus.available_seats,
                    "seat_layout": bus.get_seat_layout(),
                    "travel_date": travel_date  # dynamically map to query date
                })

            # 3. Store in Cache
            expires = datetime.utcnow() + timedelta(minutes=5)
            if cache_entry:
                cache_entry.value = json.dumps(buses)
                cache_entry.expires_at = expires
            else:
                new_cache = CacheModel(key=cache_key, value=json.dumps(buses), expires_at=expires)
                db.add(new_cache)
            db.commit()

            # Update task state output in the database
            task = db.query(TaskStateModel).filter(
                TaskStateModel.session_id == session_id,
                TaskStateModel.name == "search_buses"
            ).first()
            if task:
                task.status = "COMPLETED"
                task.set_output({"buses": buses})
                db.commit()

            return {"success": True, "buses": buses, "cache_hit": False}
        except Exception as e:
            db.rollback()
            logger.error(f"SearchBusTool execution error: {e}")
            return {"success": False, "error": str(e)}
        finally:
            db.close()


@register_tool
class RecommendOptionsTool(BaseTool):
    @property
    def name(self) -> str:
        return "recommend_options"

    @property
    def description(self) -> str:
        return "Filters and ranks bus options based on user preferences. Arguments: preference (str: 'cheapest', 'highest_rating'), buses (optional list)."

    def execute(self, session_id: str, **kwargs) -> Dict[str, Any]:
        preference = kwargs.get("preference", "highest_rating")
        buses = kwargs.get("buses")

        db = SessionLocal()
        try:
            # Check MemoryAgent if preference is default 'highest_rating'
            if preference == "highest_rating":
                try:
                    from agents.memory.memory_agent import MemoryAgent
                    from backend.services.llm import ModelRouter
                    from backend.services.prompt_loader import PromptLoader
                    memory_agent = MemoryAgent(ModelRouter(), PromptLoader())
                    prefs = memory_agent.retrieve_preferences(session_id)
                    if prefs and prefs.get("sorting_preference"):
                        preference = prefs.get("sorting_preference")
                        logger.info(f"RecommendOptionsTool: Retrieved sorting preference from memory: {preference}")
                except Exception as mem_err:
                    logger.warning(f"Could not retrieve memory preferences in RecommendOptionsTool: {mem_err}")

            # If buses list is not provided, load output of the search_buses task
            if not buses:
                search_output = get_task_output_helper(db, session_id, "search_buses")
                buses = search_output.get("buses", [])

            if not buses:
                return {"success": False, "error": "No bus results found to recommend from. Search buses first."}

            # Multi-criteria scoring formula:
            # Score = (Rating * 15) - (Fare * 0.05)
            scored_buses = []
            for b in buses:
                score = (b["rating"] * 15) - (b["fare"] * 0.05)
                scored_buses.append((score, b))

            # Sort
            if preference == "cheapest":
                scored_buses.sort(key=lambda x: x[1]["fare"])
            elif preference == "highest_rating":
                scored_buses.sort(key=lambda x: x[1]["rating"], reverse=True)
            else:
                # Default by overall score
                scored_buses.sort(key=lambda x: x[0], reverse=True)

            recommended = [item[1] for item in scored_buses[:3]]

            # Save task output
            task = db.query(TaskStateModel).filter(
                TaskStateModel.session_id == session_id,
                TaskStateModel.name == "recommend_options"
            ).first()
            if task:
                task.status = "COMPLETED"
                task.set_output({"recommended_buses": recommended})
                db.commit()

            return {"success": True, "recommended_buses": recommended}
        except Exception as e:
            logger.error(f"RecommendOptionsTool execution error: {e}")
            return {"success": False, "error": str(e)}
        finally:
            db.close()


@register_tool
class HoldSeatTool(BaseTool):
    @property
    def name(self) -> str:
        return "hold_seat"

    @property
    def description(self) -> str:
        return "Locks a specific seat on a selected bus, shifting status to held. Arguments: bus_id (int), seat_number (str), passenger_name (str), passenger_email (str)."

    def execute(self, session_id: str, **kwargs) -> Dict[str, Any]:
        bus_id = kwargs.get("bus_id")
        seat_number = kwargs.get("seat_number")
        passenger_name = kwargs.get("passenger_name", "Jane Doe")
        passenger_email = kwargs.get("passenger_email", "jane.doe@example.com")

        db = SessionLocal()
        try:
            # Contextual lookup: if bus_id is not specified, grab from recommendation output
            if not bus_id:
                rec_output = get_task_output_helper(db, session_id, "recommend_options")
                recommended = rec_output.get("recommended_buses", [])
                if recommended:
                    bus_id = recommended[0]["bus_id"]

            if not bus_id:
                return {"success": False, "error": "Missing required parameter: 'bus_id'."}

            # Query the bus run
            bus = db.query(BusInventoryModel).filter(BusInventoryModel.id == bus_id).first()
            if not bus:
                return {"success": False, "error": f"Bus run with ID {bus_id} not found."}

            # If seat number is not specified, dynamically select the first available seat
            if not seat_number:
                # Find all reserved seats for this bus
                reserved_bookings = db.query(BookingModel).filter(
                    BookingModel.bus_id == bus_id,
                    BookingModel.status.in_(["HELD", "CONFIRMED"])
                ).all()
                reserved_seats = {b.seat_number for b in reserved_bookings}
                
                # Get total seat layout
                try:
                    layout = bus.get_seat_layout()
                except Exception:
                    layout = ["1A", "1B", "2A", "2B", "3A", "3B"]
                
                # Find first unreserved seat
                available_seat = None
                for seat in layout:
                    if seat not in reserved_seats:
                        available_seat = seat
                        break
                
                if not available_seat:
                    return {"success": False, "error": f"No available seats remaining on bus {bus_id}."}
                seat_number = available_seat
            # Check if seat is already booked/held
            existing_booking = db.query(BookingModel).filter(
                BookingModel.bus_id == bus_id,
                BookingModel.seat_number == seat_number,
                BookingModel.status.in_(["HELD", "CONFIRMED"])
            ).first()
            if existing_booking:
                return {"success": False, "error": f"Seat {seat_number} is already reserved on bus {bus_id}."}

            # Create Held Booking
            new_booking = BookingModel(
                session_id=session_id,
                bus_id=bus_id,
                seat_number=seat_number,
                status="HELD",
                passenger_name=passenger_name,
                passenger_email=passenger_email,
                price_paid=bus.fare
            )
            db.add(new_booking)
            
            # Decrement seats available
            if bus.available_seats > 0:
                bus.available_seats -= 1
                
            db.commit()
            db.refresh(new_booking)

            # Update task output
            task = db.query(TaskStateModel).filter(
                TaskStateModel.session_id == session_id,
                TaskStateModel.name == "hold_seat"
            ).first()
            if task:
                task.status = "COMPLETED"
                task.set_output({
                    "booking_id": new_booking.id,
                    "status": new_booking.status,
                    "fare": bus.fare,
                    "seat_number": seat_number,
                    "operator_name": bus.operator_name
                })
                db.commit()

            return {
                "success": True,
                "booking_id": new_booking.id,
                "status": "HELD",
                "seat_number": seat_number,
                "fare": bus.fare,
                "operator_name": bus.operator_name
            }
        except Exception as e:
            db.rollback()
            logger.error(f"HoldSeatTool execution error: {e}")
            return {"success": False, "error": str(e)}
        finally:
            db.close()


@register_tool
class ProcessPaymentTool(BaseTool):
    @property
    def name(self) -> str:
        return "process_payment"

    @property
    def description(self) -> str:
        return "Simulates payment transaction for held bookings. Arguments: card_number (str), booking_id (optional int)."

    def execute(self, session_id: str, **kwargs) -> Dict[str, Any]:
        card_number = kwargs.get("card_number")
        booking_id = kwargs.get("booking_id")
        idempotency_key = kwargs.get("idempotency_key")

        if not card_number:
            return {"success": False, "error": "Missing required card parameter: 'card_number'."}

        from backend.services.reliability import db_breaker, get_idempotent_result, save_idempotent_result

        def run_txn():
            db = SessionLocal()
            try:
                if idempotency_key:
                    cached = get_idempotent_result(db, idempotency_key)
                    if cached:
                        logger.info(f"ProcessPaymentTool: Found idempotent cached response for key: {idempotency_key}")
                        return cached

                # Contextual lookup of booking_id if missing
                nonlocal booking_id
                if not booking_id:
                    hold_output = get_task_output_helper(db, session_id, "hold_seat")
                    booking_id = hold_output.get("booking_id")

                if not booking_id:
                    return {"success": False, "error": "No active booking found. Reserve a seat first."}

                booking = db.query(BookingModel).filter(BookingModel.id == booking_id).first()
                if not booking:
                    return {"success": False, "error": f"Booking with ID {booking_id} not found."}

                # Luhn check validation
                if not luhn_check(card_number):
                    res = {"success": False, "error": "Payment Declined: Invalid credit card number format (Luhn check failed)."}
                    if idempotency_key:
                        save_idempotent_result(db, idempotency_key, res)
                    return res

                # Simulate card processing delay and update booking status to CONFIRMED
                time.sleep(0.1)
                booking.status = "CONFIRMED"
                
                txn_id = f"TXN_{uuid.uuid4().hex[:8].upper()}"
                db.commit()

                # Update task output
                task = db.query(TaskStateModel).filter(
                    TaskStateModel.session_id == session_id,
                    TaskStateModel.name == "process_payment"
                ).first()
                if task:
                    task.status = "COMPLETED"
                    task.set_output({
                        "booking_id": booking.id,
                        "transaction_id": txn_id,
                        "success": True,
                        "amount": booking.price_paid
                    })
                    db.commit()

                res = {
                    "success": True,
                    "booking_id": booking.id,
                    "transaction_id": txn_id,
                    "amount_paid": booking.price_paid
                }
                if idempotency_key:
                    save_idempotent_result(db, idempotency_key, res)
                return res
            except Exception as e:
                db.rollback()
                logger.error(f"ProcessPaymentTool execution error: {e}")
                return {"success": False, "error": str(e)}
            finally:
                db.close()

        try:
            return db_breaker.call(run_txn)
        except Exception as err:
            return {"success": False, "error": f"Database breaker blocked or failed: {str(err)}"}



@register_tool
class ConfirmBookingTool(BaseTool):
    @property
    def name(self) -> str:
        return "confirm_booking"

    @property
    def description(self) -> str:
        return "Issues the final passenger PNR ticket code. Arguments: booking_id (optional int)."

    def execute(self, session_id: str, **kwargs) -> Dict[str, Any]:
        booking_id = kwargs.get("booking_id")
        idempotency_key = kwargs.get("idempotency_key")

        from backend.services.reliability import db_breaker, get_idempotent_result, save_idempotent_result

        def run_txn():
            db = SessionLocal()
            try:
                if idempotency_key:
                    cached = get_idempotent_result(db, idempotency_key)
                    if cached:
                        logger.info(f"ConfirmBookingTool: Found idempotent cached response for key: {idempotency_key}")
                        return cached

                # Contextual lookup of booking_id if missing
                nonlocal booking_id
                if not booking_id:
                    pay_output = get_task_output_helper(db, session_id, "process_payment")
                    booking_id = pay_output.get("booking_id")

                if not booking_id:
                    return {"success": False, "error": "No booking found. Process payment first."}

                booking = db.query(BookingModel).filter(BookingModel.id == booking_id).first()
                if not booking:
                    return {"success": False, "error": f"Booking with ID {booking_id} not found."}

                if booking.status != "CONFIRMED":
                    return {"success": False, "error": f"Booking is in state '{booking.status}', cannot generate PNR. Process payment first."}

                # Generate PNR if not already present
                if not booking.pnr:
                    pnr = "".join(uuid.uuid4().hex[:6].upper())
                    booking.pnr = pnr
                    db.commit()
                
                # Fetch associated bus info
                bus = db.query(BusInventoryModel).filter(BusInventoryModel.id == booking.bus_id).first()
                bus_type = bus.bus_type if bus else "Sleeper AC"
                operator = bus.operator_name if bus else "Travel Express"

                ticket = {
                    "pnr": booking.pnr,
                    "passenger_name": booking.passenger_name,
                    "passenger_email": booking.passenger_email,
                    "seat_number": booking.seat_number,
                    "operator_name": operator,
                    "bus_type": bus_type,
                    "fare": booking.price_paid,
                    "status": "CONFIRMED"
                }

                # Update task output
                task = db.query(TaskStateModel).filter(
                    TaskStateModel.session_id == session_id,
                    TaskStateModel.name == "confirm_booking"
                ).first()
                if task:
                    task.status = "COMPLETED"
                    task.set_output(ticket)
                    db.commit()

                res = {"success": True, "ticket": ticket}
                if idempotency_key:
                    save_idempotent_result(db, idempotency_key, res)
                return res
            except Exception as e:
                db.rollback()
                logger.error(f"ConfirmBookingTool execution error: {e}")
                return {"success": False, "error": str(e)}
            finally:
                db.close()

        try:
            return db_breaker.call(run_txn)
        except Exception as err:
            return {"success": False, "error": f"Database breaker blocked or failed: {str(err)}"}



@register_tool
class SendNotificationTool(BaseTool):
    @property
    def name(self) -> str:
        return "send_notification"

    @property
    def description(self) -> str:
        return "Dispatches booking confirmations to email and SMS channels. Arguments: channels (optional list)."

    def execute(self, session_id: str, **kwargs) -> Dict[str, Any]:
        channels = kwargs.get("channels", ["SMS", "Email"])

        db = SessionLocal()
        try:
            # Grab ticket from confirm_booking task
            ticket_output = get_task_output_helper(db, session_id, "confirm_booking")
            ticket = ticket_output.get("ticket", {})

            # Update task output
            task = db.query(TaskStateModel).filter(
                TaskStateModel.session_id == session_id,
                TaskStateModel.name == "send_notification"
            ).first()
            if task:
                task.status = "COMPLETED"
                task.set_output({"delivered_channels": channels, "notified": True})
                db.commit()

            return {
                "success": True,
                "notified": True,
                "delivered_channels": channels,
                "pnr": ticket.get("pnr")
            }
        except Exception as e:
            logger.error(f"SendNotificationTool execution error: {e}")
            return {"success": False, "error": str(e)}
        finally:
            db.close()
