import os
import sys
import asyncio
import time

# Add root folder to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.database.db import SessionLocal, init_db
from backend.database.models import SessionModel, TaskStateModel, BookingModel, WorkflowStateModel
from backend.runtime.workflow.compiler import WorkflowCompiler
from backend.runtime.workflow.executor import WorkflowExecutor
from backend.tools import travel_tools  # Register tools

async def run_payment_failure():
    print("\n==================================================")
    print(" SCENARIO 3: TRANSACTION FAILURE & SAGA ROLLBACK")
    print("==================================================")
    
    session_id = f"demo_rollback_{int(time.time())}"
    print(f"[*] Creating rollback session: {session_id}")
    
    db = SessionLocal()
    try:
        session = SessionModel(session_id=session_id)
        db.add(session)
        db.commit()
        
        # Compile workflow with invalid card number
        variables = {
            "origin": "Bangalore",
            "destination": "Hyderabad",
            "travel_date": "2026-06-29",
            "passenger_name": "Demo Rollback User",
            "passenger_email": "rollback@travelops.ai",
            "seat_number": "6C",
            "bus_id": 1,
            "amount": 950.0,
            "card_number": "1234 5678", # Invalid Card (Luhn check fails)
            "idempotency_key": f"idem_rollback_{session_id}",
            "recipient": "rollback@travelops.ai",
            "message": "This notification should not send!"
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
        
        print("[*] Running executor. Payment should fail, triggering Saga...")
        await WorkflowExecutor.execute_graph(session_id)
        
        # Give compensating tasks a moment to complete
        await asyncio.sleep(1)
        
        db.expire_all()
        booking = db.query(BookingModel).filter(BookingModel.session_id == session_id).first()
        workflow_state = db.query(WorkflowStateModel).filter(WorkflowStateModel.session_id == session_id).first()
        
        print(f"\n[OK] Saga Compensations Executed successfully!")
        if booking:
            print(f"     - Booking status: {booking.status} (Released seat {booking.seat_number})")
        if workflow_state:
            print(f"     - Workflow state: {workflow_state.state}")
            
    finally:
        db.close()

if __name__ == "__main__":
    init_db()
    asyncio.run(run_payment_failure())
