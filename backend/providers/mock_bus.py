import logging
import uuid
from typing import Dict, Any, List
from sqlalchemy import func

from backend.providers.base import BaseTravelProvider
from backend.database.db import SessionLocal
from backend.database.models import BusInventoryModel, BookingModel

logger = logging.getLogger("travelops.providers.mock_bus")

class MockBusProvider(BaseTravelProvider):
    @property
    def name(self) -> str:
        return "MockBusProvider"

    def search_buses(self, origin: str, destination: str, travel_date: str) -> List[Dict[str, Any]]:
        db = SessionLocal()
        try:
            logger.info(f"MockBusProvider searching buses from {origin} to {destination} on {travel_date}")
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
                    "travel_date": travel_date
                })
            return buses
        finally:
            db.close()

    def hold_seat(self, bus_id: int, seat_number: str, passenger_name: str, passenger_email: str, session_id: str) -> Dict[str, Any]:
        db = SessionLocal()
        try:
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
                
                try:
                    layout = bus.get_seat_layout()
                except Exception:
                    layout = ["1A", "1B", "2A", "2B", "3A", "3B"]
                
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
            if bus.available_seats > 0:
                bus.available_seats -= 1
            db.commit()
            db.refresh(new_booking)
            
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
            logger.error(f"MockBusProvider hold_seat error: {e}")
            return {"success": False, "error": str(e)}
        finally:
            db.close()

    def confirm_booking(self, booking_id: int) -> Dict[str, Any]:
        db = SessionLocal()
        try:
            booking = db.query(BookingModel).filter(BookingModel.id == booking_id).first()
            if not booking:
                return {"success": False, "error": f"Booking with ID {booking_id} not found."}
                
            booking.status = "CONFIRMED"
            if not booking.pnr:
                booking.pnr = "".join(uuid.uuid4().hex[:6].upper())
            db.commit()
            db.refresh(booking)
            
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
            return {"success": True, "ticket": ticket}
        except Exception as e:
            db.rollback()
            logger.error(f"MockBusProvider confirm_booking error: {e}")
            return {"success": False, "error": str(e)}
        finally:
            db.close()

    def cancel_booking(self, booking_id: int, session_id: str) -> Dict[str, Any]:
        db = SessionLocal()
        try:
            booking = db.query(BookingModel).filter(BookingModel.id == booking_id).first()
            if not booking:
                return {"success": False, "error": f"Booking with ID {booking_id} not found."}
                
            logger.info(f"MockBusProvider cancelling booking {booking_id} for seat '{booking.seat_number}'")
            booking.status = "CANCELLED"
            
            # Return seat to inventory
            bus = db.query(BusInventoryModel).filter(BusInventoryModel.id == booking.bus_id).first()
            if bus:
                bus.available_seats += 1
                
            db.commit()
            return {"success": True, "booking_id": booking_id, "status": "CANCELLED"}
        except Exception as e:
            db.rollback()
            logger.error(f"MockBusProvider cancel_booking error: {e}")
            return {"success": False, "error": str(e)}
        finally:
            db.close()
