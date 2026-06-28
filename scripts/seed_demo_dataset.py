import os
import sys
import random
import json
from datetime import datetime, timedelta

# Add root folder to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.database.db import SessionLocal, init_db
from backend.database.models import (
    SessionModel, BookingModel, BusInventoryModel, WorkflowStateModel,
    TaskStateModel, AuditLogModel, EventStoreModel
)

def seed_dataset():
    print("[*] Launching TravelOps AI Studio Demo Seeder...")
    init_db()
    db = SessionLocal()

    # Verify we have seeded bus routes
    buses = db.query(BusInventoryModel).all()
    if not buses:
        print("[!] Bus inventory empty. Please run scripts/reset_db.py first.")
        return

    # User pools
    first_names = ["John", "Jane", "Alice", "Bob", "Charlie", "David", "Emily", "Fiona", "George", "Hannah", "Ian", "Julia"]
    last_names = ["Smith", "Doe", "Johnson", "Brown", "Taylor", "Miller", "Wilson", "Anderson", "Thomas", "Jackson", "White", "Harris"]
    origins = ["Bangalore", "Hyderabad", "Delhi", "Jaipur", "Mumbai", "Pune", "Chennai", "Kochi"]
    destinations = ["Hyderabad", "Bangalore", "Jaipur", "Delhi", "Pune", "Mumbai", "Kochi", "Chennai"]
    operators = ["VRL Travels", "IntrCity SmartBus", "SRS Travels", "Orange Tours"]

    print("[*] Seeding 50 Conversations/Sessions...")
    session_ids = []
    
    # 1. Generate 50 sessions
    for i in range(50):
        s_id = f"sess_{random.randint(10000000, 99999999)}"
        created_at = datetime.utcnow() - timedelta(days=random.randint(0, 10), hours=random.randint(0, 23))
        
        session = SessionModel(session_id=s_id)
        session.created_at = created_at
        db.add(session)
        session_ids.append((s_id, created_at))
    db.commit()

    print("[*] Seeding 100 Bookings, including cancellations and recoveries...")
    # 2. Seeding Bookings
    # We want 100 total bookings.
    # 20 Cancellations (status = 'CANCELLED')
    # 5 Payment Failures (payment task failed, booking cancelled)
    # 3 Recoveries (disruption cancelled active booking, rebooked)
    
    booking_count = 0
    
    # Track metrics
    total_tokens = 0
    total_cost_usd = 0.0

    # Seeding Recoveries (3 cases)
    # Session ID recovery
    recovery_sess_ids = [f"demo_recover_{k}" for k in range(1, 4)]
    for s_id in recovery_sess_ids:
        # Create session
        dt = datetime.utcnow() - timedelta(hours=random.randint(2, 24))
        session = SessionModel(session_id=s_id)
        session.created_at = dt
        db.add(session)
        
        # Initial booking (impacted by cancellation)
        bus1 = buses[0]
        booking_old = BookingModel(
            session_id=s_id,
            bus_id=bus1.id,
            pnr=f"PNR{random.randint(100000, 999999)}",
            seat_number="2A",
            status="CANCELLED",
            passenger_name="Jane Doe",
            passenger_email="jane.doe@example.com",
            price_paid=950.0
        )
        db.add(booking_old)
        
        # Recovery booking (Rebooked Alternative)
        bus2 = buses[1] if len(buses) > 1 else buses[0]
        booking_new = BookingModel(
            session_id=s_id,
            bus_id=bus2.id,
            pnr=f"PNR{random.randint(100000, 999999)}",
            seat_number="1C",
            status="CONFIRMED",
            passenger_name="Jane Doe",
            passenger_email="jane.doe@example.com",
            price_paid=1100.0
        )
        db.add(booking_new)
        booking_count += 2
        
        # State transitions
        db.add(WorkflowStateModel(session_id=s_id, state="RECOVERED"))
        
        # Events
        import uuid
        ev1 = EventStoreModel(id=str(uuid.uuid4()), session_id=s_id, event_type="BusCancelled")
        ev1.set_payload({"bus_id": bus1.id, "booking_id": 1})
        db.add(ev1)
        
        ev2 = EventStoreModel(id=str(uuid.uuid4()), session_id=s_id, event_type="DisruptionDetected")
        ev2.set_payload({"bus_id": bus1.id, "booking_id": 1})
        db.add(ev2)
        
        ev3 = EventStoreModel(id=str(uuid.uuid4()), session_id=s_id, event_type="BookingCompleted")
        ev3.set_payload({"booking_id": 2})
        db.add(ev3)

        # Chat
        db.add(AuditLogModel(session_id=s_id, agent_name="User", action="chat_message", reasoning_summary="Search sleeper buses Bangalore to Hyderabad"))
        db.add(AuditLogModel(session_id=s_id, agent_name="Assistant", action="chat_message", reasoning_summary="I have compiled and run the booking. PNR: PNR_OLD"))
        db.add(AuditLogModel(session_id=s_id, agent_name="JourneyMonitor", action="monitor", reasoning_summary="JourneyMonitor: Active booking is impacted by bus cancellation."))
        db.add(AuditLogModel(session_id=s_id, agent_name="RecoveryAgent", action="recover", reasoning_summary="RecoveryAgent: Rebooked seat on alternative bus run (IntrCity SmartBus)."))
        
        # Tasks
        for t_name, status in [("search_buses", "COMPLETED"), ("hold_seat", "COMPLETED"), ("process_payment", "COMPLETED"), ("confirm_booking", "COMPLETED")]:
            task = TaskStateModel(session_id=s_id, task_id=f"{t_name}_rec", name=t_name, status=status)
            task.set_input({"origin": "Bangalore", "destination": "Hyderabad"})
            db.add(task)

    # Seeding Payment Failures (5 cases)
    for k in range(5):
        s_id = f"demo_pay_fail_{k}"
        dt = datetime.utcnow() - timedelta(hours=random.randint(10, 48))
        session = SessionModel(session_id=s_id)
        session.created_at = dt
        db.add(session)
        
        booking_fail = BookingModel(
            session_id=s_id,
            bus_id=buses[0].id,
            pnr=None,
            seat_number="3B",
            status="CANCELLED",
            passenger_name="Alice Smith",
            passenger_email="alice@example.com",
            price_paid=0.0
        )
        db.add(booking_fail)
        booking_count += 1
        
        db.add(WorkflowStateModel(session_id=s_id, state="FAILED"))
        
        # Audit Logs
        db.add(AuditLogModel(session_id=s_id, agent_name="User", action="chat_message", reasoning_summary="Book bus from Bangalore to Hyderabad"))
        db.add(AuditLogModel(session_id=s_id, agent_name="Assistant", action="chat_message", reasoning_summary="Booking failed due to payment decline. Initiated compensating rollback."))
        
        # Tasks
        for t_name, status in [("search_buses", "COMPLETED"), ("hold_seat", "COMPLETED"), ("process_payment", "FAILED")]:
            task = TaskStateModel(session_id=s_id, task_id=f"{t_name}_pay", name=t_name, status=status)
            task.set_input({"origin": "Bangalore", "destination": "Hyderabad"})
            if status == "FAILED":
                task.set_output({"error": "Payment Declined: Luhn validation check failed."})
            db.add(task)

    # Standard Confirmations and Cancellations (to make up 100 total bookings)
    # Remaining bookings: 100 - 6 (recoveries) - 5 (payment failures) = 89 bookings
    # Let's seed 15 cancellations, 74 confirmed standard bookings.
    cancellation_targets = 15
    confirmed_targets = 74
    
    for i in range(cancellation_targets + confirmed_targets):
        # Pick a random session from generated pool
        s_id, dt = random.choice(session_ids)
        bus = random.choice(buses)
        
        status = "CANCELLED" if i < cancellation_targets else "CONFIRMED"
        pnr = f"PNR{random.randint(100000, 999999)}" if status == "CONFIRMED" else None
        
        name = f"{random.choice(first_names)} {random.choice(last_names)}"
        email = f"{name.lower().replace(' ', '.')}@example.com"
        
        booking = BookingModel(
            session_id=s_id,
            bus_id=bus.id,
            pnr=pnr,
            seat_number=f"{random.randint(1, 10)}{random.choice(['A','B','C','D'])}",
            status=status,
            passenger_name=name,
            passenger_email=email,
            price_paid=bus.fare if status == "CONFIRMED" else 0.0
        )
        db.add(booking)
        booking_count += 1
        
        # Add workflow states
        state_str = "COMPLETED" if status == "CONFIRMED" else "ROLLBACK_COMPLETE"
        db.add(WorkflowStateModel(session_id=s_id, state=state_str))
        
        # Tasks
        for t_name, t_status in [("search_buses", "COMPLETED"), ("hold_seat", "COMPLETED"), ("process_payment", "COMPLETED"), ("confirm_booking", "COMPLETED" if status == "CONFIRMED" else "PENDING")]:
            task = TaskStateModel(session_id=s_id, task_id=f"{t_name}_{i}", name=t_name, status=t_status)
            task.set_input({"origin": bus.origin, "destination": bus.destination})
            db.add(task)
            
        # Add timeline logs with realistic tokens & costs
        tokens = random.randint(1000, 2500)
        cost = tokens * 0.000015
        total_tokens += tokens
        total_cost_usd += cost
        
        db.add(AuditLogModel(
            session_id=s_id, 
            agent_name="IntentAgent", 
            action="parse_intent", 
            reasoning_summary=f"Parsed customer travel intent to go from {bus.origin} to {bus.destination}.",
            payload_raw=json.dumps({"tokens": tokens, "cost": cost})
        ))
        
        tokens_pl = random.randint(2000, 4000)
        cost_pl = tokens_pl * 0.00003
        total_tokens += tokens_pl
        total_cost_usd += cost_pl
        
        db.add(AuditLogModel(
            session_id=s_id, 
            agent_name="PlannerAgent", 
            action="generate_plan", 
            reasoning_summary="Generated a Directed Acyclic Graph containing route details, weather forecasts, and seats booking.",
            payload_raw=json.dumps({"tokens": tokens_pl, "cost": cost_pl})
        ))

    # Seed Provider health metrics into ProviderRouter log simulations
    print("[*] Seeding provider health records...")
    # Add dummy entries in AuditLog for ProviderRouter selections
    for provider_name in ["MockBusProvider", "BackupBusProvider"]:
        for _ in range(10):
            db.add(AuditLogModel(
                session_id="system_provider",
                agent_name="ProviderRouter",
                action="select_provider",
                reasoning_summary=f"Selected {provider_name} to search buses. Latency: {random.randint(40, 95)}ms. Success: True"
            ))

    db.commit()
    db.close()
    
    print(f"[OK] Database successfully seeded with:")
    print(f"     - {booking_count} Bookings (including 20 cancellations, 5 payment failures, 3 rebookings)")
    print(f"     - 50 active conversational sessions")
    print(f"     - Total simulated tokens: {total_tokens} (approx cost: ${total_cost_usd:.4f})")
    print(f"     - Dynamic audit logs and provider statistics loaded.")

if __name__ == "__main__":
    seed_dataset()
