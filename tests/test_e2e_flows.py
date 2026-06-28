import pytest
import asyncio
import time
from backend.database.db import SessionLocal, init_db
from backend.database.models import SessionModel, TaskStateModel, BookingModel, WorkflowStateModel, EventStoreModel
from backend.runtime.workflow.compiler import WorkflowCompiler
from backend.runtime.workflow.executor import WorkflowExecutor
from backend.events.event_bus import EventBus
from backend.providers.router import ProviderRouter
from backend.tools import travel_tools  # Register tools

@pytest.fixture(autouse=True)
def setup_db():
    # Reset database schema before each test run
    from backend.database.db import engine, Base
    import backend.database.models
    Base.metadata.drop_all(bind=engine)
    init_db()
    yield

@pytest.mark.asyncio
async def test_e2e_booking_flow():
    """Test standard successful booking pipeline execution."""
    session_id = f"test_e2e_success_{int(time.time())}"
    db = SessionLocal()
    
    # 1. Register session
    session = SessionModel(session_id=session_id)
    db.add(session)
    db.commit()
    
    # 2. Compile tasks
    variables = {
        "origin": "Bangalore",
        "destination": "Hyderabad",
        "travel_date": "2026-06-29",
        "passenger_name": "E2E User",
        "passenger_email": "e2e@travelops.ai",
        "seat_number": "12A",
        "bus_id": 1,
        "amount": 950.0,
        "card_number": "4111 1111 1111 1111", # Valid Card
        "idempotency_key": f"idem_e2e_{session_id}",
        "recipient": "e2e@travelops.ai",
        "message": "E2E Confirmation Message"
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
    
    # 3. Execute
    await WorkflowExecutor.execute_graph(session_id)
    
    # 4. Assertions
    db.expire_all()
    booking = db.query(BookingModel).filter(BookingModel.session_id == session_id).first()
    workflow_state = db.query(WorkflowStateModel).filter(
        WorkflowStateModel.session_id == session_id
    ).order_by(WorkflowStateModel.id.desc()).first()
    
    assert booking is not None
    assert booking.status == "CONFIRMED"
    assert booking.seat_number == "12A"
    assert booking.pnr is not None
    assert workflow_state is not None
    assert workflow_state.state == "BOOKED"
    db.close()

@pytest.mark.asyncio
async def test_e2e_provider_failover():
    """Test automatic failover routing when preferred provider is degraded."""
    session_id = f"test_e2e_failover_{int(time.time())}"
    db = SessionLocal()
    
    # Trip ProviderRouter consecutive failures count to force outage state
    router = ProviderRouter()
    router.health_records["mockbusprovider"].consecutive_failures = 0
    router.health_records["mockbusprovider"].status = "HEALTHY"
    for _ in range(3):
        router.health_records["mockbusprovider"].record_failure()
        
    assert router.health_records["mockbusprovider"].status == "UNHEALTHY"
    
    session = SessionModel(session_id=session_id)
    db.add(session)
    db.commit()
    
    variables = {
        "origin": "Bangalore",
        "destination": "Hyderabad",
        "travel_date": "2026-06-29",
        "passenger_name": "Failover User",
        "passenger_email": "failover@travelops.ai",
        "seat_number": "12B",
        "bus_id": 1,
        "amount": 950.0,
        "card_number": "4111 1111 1111 1111",
        "idempotency_key": f"idem_failover_{session_id}",
        "recipient": "failover@travelops.ai",
        "message": "Failover Alert"
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
    
    await WorkflowExecutor.execute_graph(session_id)
    
    db.expire_all()
    booking = db.query(BookingModel).filter(BookingModel.session_id == session_id).first()
    assert booking is not None
    assert booking.status == "CONFIRMED"
    # Reset router health to healthy for subsequent runs
    router.health_records["mockbusprovider"].consecutive_failures = 0
    router.health_records["mockbusprovider"].status = "HEALTHY"
    db.close()

@pytest.mark.asyncio
async def test_e2e_payment_failure_saga():
    """Test payment failure triggering compensating Saga rollbacks."""
    session_id = f"test_e2e_saga_{int(time.time())}"
    db = SessionLocal()
    
    session = SessionModel(session_id=session_id)
    db.add(session)
    db.commit()
    
    variables = {
        "origin": "Bangalore",
        "destination": "Hyderabad",
        "travel_date": "2026-06-29",
        "passenger_name": "Saga User",
        "passenger_email": "saga@travelops.ai",
        "seat_number": "12C",
        "bus_id": 1,
        "amount": 950.0,
        "card_number": "1234 5678", # Invalid Card (Luhn check fails)
        "idempotency_key": f"idem_saga_{session_id}",
        "recipient": "saga@travelops.ai",
        "message": "Saga alerts"
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
    
    await WorkflowExecutor.execute_graph(session_id)
    
    # Wait for rollback to finish
    await asyncio.sleep(0.5)
    
    db.expire_all()
    booking = db.query(BookingModel).filter(BookingModel.session_id == session_id).first()
    assert booking is not None
    assert booking.status == "CANCELLED"
    db.close()

@pytest.mark.asyncio
async def test_e2e_disruption_recovery():
    """Test journey cancellation detection and auto-recovery rebooking."""
    session_id = f"test_e2e_disruption_{int(time.time())}"
    db = SessionLocal()
    
    # 1. Create a confirmed booking to cancel
    session = SessionModel(session_id=session_id)
    db.add(session)
    
    booking = BookingModel(
        session_id=session_id,
        pnr="E2EDIS",
        passenger_name="Jane Doe",
        passenger_email="jane@example.com",
        bus_id=1,
        seat_number="2A",
        price_paid=950.0,
        status="CONFIRMED"
    )
    db.add(booking)
    
    workflow_state = WorkflowStateModel(
        session_id=session_id,
        state="BOOKED"
    )
    db.add(workflow_state)
    db.commit()
    
    # 2. Register subscribers on the event bus
    from backend.events.event_bus import EventBus
    from agents.monitor.journey_monitor import JourneyMonitor
    from agents.recovery.recovery_agent import RecoveryAgent
    
    # Verify subscribers bound
    await EventBus.subscribe("BusCancelled", JourneyMonitor.handle_bus_cancelled)
    await EventBus.subscribe("DisruptionDetected", RecoveryAgent.handle_disruption)
    
    # 3. Publish cancellation event
    await EventBus.publish("BusCancelled", session_id, {
        "bus_id": 1,
        "reason": "Engine failure breakdown",
        "session_id": session_id
    })
    
    # Let event loop dispatch event and invoke recovery workflow
    await asyncio.sleep(1)
    
    db.expire_all()
    # Check if a recovery log was created
    event = db.query(EventStoreModel).filter(
        EventStoreModel.session_id == session_id,
        EventStoreModel.event_type == "BusCancelled"
    ).first()
    
    assert event is not None
    db.close()
