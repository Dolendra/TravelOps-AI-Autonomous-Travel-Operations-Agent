import os
import sys
import asyncio
import time

# Add root folder to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.database.db import SessionLocal, init_db
from backend.database.models import SessionModel, TaskStateModel, BookingModel, WorkflowStateModel, AuditLogModel
from backend.runtime.workflow.compiler import WorkflowCompiler
from backend.runtime.workflow.executor import WorkflowExecutor
from backend.tools import travel_tools  # Register tools

async def run_success_booking():
    print("\n==================================================")
    print(" SCENARIO 1: SUCCESSFUL AUTONOMOUS TRIP BOOKING")
    print("==================================================")
    
    session_id = f"demo_success_{int(time.time())}"
    print(f"[*] Creating demo session: {session_id}")
    
    db = SessionLocal()
    try:
        # Create session
        session = SessionModel(session_id=session_id)
        db.add(session)
        db.commit()
        
        # User input message simulation
        db.add(AuditLogModel(
            session_id=session_id,
            agent_name="User",
            action="chat_message",
            reasoning_summary="Search sleeper buses Bangalore to Hyderabad for Demo Success User on June 29"
        ))
        
        # Compile DSL graph
        print("[*] Compiling Declarative Workflow DSL Graph...")
        variables = {
            "origin": "Bangalore",
            "destination": "Hyderabad",
            "travel_date": "2026-06-29",
            "passenger_name": "Demo Success User",
            "passenger_email": "success@travelops.ai",
            "seat_number": "10A",
            "bus_id": 1,
            "amount": 950.0,
            "card_number": "4111 1111 1111 1111", # Valid Visa Card
            "idempotency_key": f"idem_success_{session_id}",
            "recipient": "success@travelops.ai",
            "message": "Your travel booking Bangalore -> Hyderabad is confirmed!"
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
        
        # Run execution loop
        print("[*] Executing workflow tasks in waves...")
        await WorkflowExecutor.execute_graph(session_id)
        
        # Check booking output
        db.expire_all()
        booking = db.query(BookingModel).filter(
            BookingModel.session_id == session_id,
            BookingModel.status == "CONFIRMED"
        ).first()
        
        if booking:
            print(f"\n[OK] Booking successfully Confirmed!")
            print(f"     - PNR Generated: {booking.pnr}")
            print(f"     - Seat Blocked : {booking.seat_number}")
            print(f"     - Amount Paid  : ${booking.price_paid:.2f}")
        else:
            print("[!] Booking execution finished, but booking was not confirmed.")
            
    finally:
        db.close()

if __name__ == "__main__":
    init_db()
    asyncio.run(run_success_booking())
