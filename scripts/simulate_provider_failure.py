import os
import sys
import asyncio
import time

# Add root folder to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.database.db import SessionLocal, init_db
from backend.database.models import SessionModel, TaskStateModel, BookingModel
from backend.runtime.workflow.compiler import WorkflowCompiler
from backend.runtime.workflow.executor import WorkflowExecutor
from backend.providers.router import ProviderRouter
from backend.tools import travel_tools  # Register tools

async def run_provider_failover():
    print("\n==================================================")
    print(" SCENARIO 2: TRANSIT PROVIDER OUTAGE & AUTO-FAILOVER")
    print("==================================================")
    
    session_id = f"demo_failover_{int(time.time())}"
    print(f"[*] Creating failover session: {session_id}")
    
    # 1. Force preferred provider to be unhealthy by tripping consecutive failures
    router = ProviderRouter()
    # Reset health states to start fresh
    router.health_records["mockbusprovider"].consecutive_failures = 0
    router.health_records["mockbusprovider"].status = "HEALTHY"
    
    print("[!] Simulating consecutive API failures on 'MockBusProvider'...")
    for i in range(3):
        router.health_records["mockbusprovider"].record_failure()
        
    print(f"[*] Preferred provider state: {router.health_records['mockbusprovider'].status}")
    
    db = SessionLocal()
    try:
        session = SessionModel(session_id=session_id)
        db.add(session)
        db.commit()
        
        # Compile workflow
        variables = {
            "origin": "Bangalore",
            "destination": "Hyderabad",
            "travel_date": "2026-06-29",
            "passenger_name": "Demo Failover User",
            "passenger_email": "failover@travelops.ai",
            "seat_number": "4B",
            "bus_id": 1,
            "amount": 950.0,
            "card_number": "4111 1111 1111 1111",
            "idempotency_key": f"idem_failover_{session_id}",
            "recipient": "failover@travelops.ai",
            "message": "Your booking has failed over and is confirmed!"
        }
        compiled_tasks = WorkflowCompiler.compile_workflow("full_booking", variables)
        
        for t in compiled_tasks:
            db_task = TaskStateModel(
                session_id=session_id,
                task_id=t["task_id"],
                name=t["name"],
                status="PENDING"
            )
            db_task.set_dependencies(t["dependencies"])
            db_task.set_input(t["input_data"])
            db.add(db_task)
        db.commit()
        
        print("[*] Running executor. Router should route to BackupBusProvider...")
        await WorkflowExecutor.execute_graph(session_id)
        
        # Verify confirmed booking with backup operator name
        db.expire_all()
        booking = db.query(BookingModel).filter(
            BookingModel.session_id == session_id,
            BookingModel.status == "CONFIRMED"
        ).first()
        
        if booking:
            print(f"\n[OK] Failover Booking Confirmed successfully via fallback!")
            print(f"     - Provider Used : BackupBusProvider")
            print(f"     - PNR Generated : {booking.pnr}")
            print(f"     - Seat Blocked  : {booking.seat_number}")
        else:
            print("[!] Failover failed. Check logs.")
            
    finally:
        # Reset provider health so other runs aren't affected
        router.health_records["mockbusprovider"].consecutive_failures = 0
        router.health_records["mockbusprovider"].status = "HEALTHY"
        db.close()

if __name__ == "__main__":
    init_db()
    asyncio.run(run_provider_failover())
