import os
import sys
import asyncio

# Add root folder to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.database.db import SessionLocal
from backend.database.models import BookingModel, BusInventoryModel
from backend.events.event_bus import EventBus
from agents.monitor.journey_monitor import JourneyMonitor
from agents.recovery.recovery_agent import RecoveryAgent

async def run_disruption():
    print("[*] Launching disruption event simulator...")
    
    # 1. Register event subscribers so the event bus maps callbacks correctly
    EventBus.subscribe("BusCancelled", JourneyMonitor.handle_bus_cancelled)
    EventBus.subscribe("DisruptionDetected", RecoveryAgent.handle_disruption)
    
    # 2. Query database for latest confirmed booking
    db = SessionLocal()
    try:
        booking = db.query(BookingModel).filter(BookingModel.status == "CONFIRMED").order_by(BookingModel.id.desc()).first()
        if not booking:
            print("[!] No active confirmed booking found in the database to disrupt.")
            print("[*] Hint: Start a session in the Operations Studio Console first.")
            return
            
        bus = db.query(BusInventoryModel).filter(BusInventoryModel.id == booking.bus_id).first()
        if not bus:
            print("[!] Associated bus inventory not found.")
            return
            
        print(f"[*] Found active target booking:")
        print(f"    - Booking ID: {booking.id}")
        print(f"    - PNR Code: {booking.pnr}")
        print(f"    - Operator: {bus.operator_name}")
        print(f"    - Passenger: {booking.passenger_name}")
        print(f"    - Session ID: {booking.session_id}")
        
        # 3. Publish the BusCancelled event to the event bus
        print(f"\n[!] Simulating BusCancelled event on Bus ID {bus.id}...")
        event_payload = {
            "bus_id": bus.id,
            "operator_name": bus.operator_name,
            "origin": bus.origin,
            "destination": bus.destination,
            "departure_time": bus.departure_time,
            "travel_date": "2026-06-29"
        }
        
        await EventBus.publish("BusCancelled", booking.session_id, event_payload)
        
        # Give async handlers a moment to complete
        await asyncio.sleep(1)
        
        # 4. Reload and show output booking details
        db.expire_all()
        new_booking = db.query(BookingModel).filter(
            BookingModel.session_id == booking.session_id,
            BookingModel.status == "CONFIRMED"
        ).order_by(BookingModel.id.desc()).first()
        
        if new_booking and new_booking.id != booking.id:
            new_bus = db.query(BusInventoryModel).filter(BusInventoryModel.id == new_booking.bus_id).first()
            print("\n[OK] Autonomous Recovery Completed Successfully!")
            print(f"     - Old Booking status: CANCELLED")
            print(f"     - New Booking ID: {new_booking.id}")
            print(f"     - New PNR Code: {new_booking.pnr}")
            print(f"     - New Operator: {new_bus.operator_name if new_bus else 'Unknown'}")
            print(f"     - New Seat: {new_booking.seat_number}")
        else:
            print("\n[!] Disruption handled, but no new booking was created. Check logs.")
            
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(run_disruption())
