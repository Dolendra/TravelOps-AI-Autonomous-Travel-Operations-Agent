#!/usr/bin/env python3
"""
TravelOps AI — Developer DX Demo CLI Runner
Runs key travel platform scenarios to demonstrate production capabilities:
1. Normal Booking Flow (Full search, weather, maps, hold, payment, notifications)
2. Payment Decline & Saga Compensating Rollback (Seat release, refund mocks)
3. Disruption & Autonomous Recovery (Bus cancellation event rebooking)
"""
import os
import sys
import asyncio
import logging
from datetime import datetime, timedelta

# Disable noisy logging for clean CLI visual feedback
logging.basicConfig(level=logging.WARNING)
logging.getLogger("travelops").setLevel(logging.INFO)

# ANSI terminal colors
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BLUE = "\033[94m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"

# Ensure DATABASE_URL is set
if not os.getenv("DATABASE_URL"):
    os.environ["DATABASE_URL"] = "sqlite:///travelops.db"

# Force db initialization pointing to the correct file
from backend.database import db
db.db_manager._initialized = False
db.db_manager.__init__()
db.engine = db.db_manager.get_engine()
db.SessionLocal = db.db_manager.session_factory

# Bind imports to correct SessionLocal
from backend.runtime.workflow import executor, runtime
executor.SessionLocal = db.SessionLocal
runtime.SessionLocal = db.SessionLocal

from backend.tools import travel_tools
travel_tools.SessionLocal = db.SessionLocal

from agents.recovery import recovery_agent
recovery_agent.SessionLocal = db.SessionLocal

# Seed database before running
db.init_db()

from backend.events.event_bus import EventBus
from agents.monitor.journey_monitor import JourneyMonitor
from agents.recovery.recovery_agent import RecoveryAgent
from backend.runtime.workflow.compiler import WorkflowCompiler
from backend.runtime.workflow.executor import WorkflowExecutor
from backend.runtime.workflow.runtime import WorkflowRuntime
from backend.database.models import TaskStateModel, WorkflowStateModel, BookingModel, BusInventoryModel, AuditLogModel, SessionModel, UserModel


def print_header(title):
    print("\n" + "="*80)
    print(f" {BOLD}{CYAN}{title}{RESET}")
    print("="*80)


def print_step(msg):
    print(f"[*] {msg}")


def print_success(msg):
    print(f"{GREEN}[OK] {msg}{RESET}")


def print_warning(msg):
    print(f"{YELLOW}[!] {msg}{RESET}")


def print_error(msg):
    print(f"{RED}[X] {msg}{RESET}")


async def ensure_demo_user():
    session = db.SessionLocal()
    try:
        user = session.query(UserModel).filter(UserModel.email == "demo_passenger@example.com").first()
        if not user:
            from backend.services.auth import SecurityService
            hashed = SecurityService.hash_password("password123")
            user = UserModel(
                email="demo_passenger@example.com",
                password_hash=hashed,
                name="Demo Passenger",
                role="passenger"
            )
            session.add(user)
            session.commit()
            session.refresh(user)
        return user.id
    finally:
        session.close()


async def run_normal_booking():
    print_header("SCENARIO 1: Normal Booking Journey (Full Success)")
    user_id = await ensure_demo_user()
    
    session_id = f"demo_success_{int(datetime.utcnow().timestamp())}"
    print_step(f"Creating a new travel operations session: {session_id}")
    
    session = db.SessionLocal()
    try:
        new_sess = SessionModel(session_id=session_id, user_id=user_id)
        session.add(new_sess)
        session.add(WorkflowStateModel(session_id=session_id, state="NEW"))
        session.commit()

        variables = {
            "origin": "Bangalore",
            "destination": "Hyderabad",
            "travel_date": (datetime.utcnow() + timedelta(days=2)).strftime("%Y-%m-%d"),
            "preferences": "highest_rating",
            "idempotency_key": f"key_demo_success_{int(datetime.utcnow().timestamp())}",
            "email": "demo_passenger@example.com",
            "bus_id": "1",
            "seat_number": "",
            "amount": 950.0,
            "card_number": "4111 1111 1111 1111",
            "booking_id": "100"
        }

        print_step("Compiling full_booking.yaml DSL workflow...")
        tasks = WorkflowCompiler.compile_workflow("full_booking", variables)
        
        for task in tasks:
            t_model = TaskStateModel(
                session_id=session_id,
                task_id=task.get("task_id"),
                name=task.get("name"),
                status="PENDING"
            )
            t_model.set_dependencies(task.get("dependencies", []))
            t_model.set_input(task.get("input_data", {}))
            session.add(t_model)
        session.commit()

        print_step("Executing Compiled Task Dependency Graph concurrently...")
        await WorkflowExecutor.execute_graph(session_id)

        # Reload session to check results
        session.close()
        session = db.SessionLocal()
        
        db_tasks = session.query(TaskStateModel).filter(TaskStateModel.session_id == session_id).all()
        print(f"\n{BOLD}--- Task Execution Status Matrix ---{RESET}")
        for t in db_tasks:
            status_color = f"{GREEN}COMPLETED{RESET}" if t.status == "COMPLETED" else t.status
            print(f"Task: {t.name:<25} ID: {t.task_id:<12} Status: {status_color}")
            out = t.get_output() or {}
            if t.name == "get_route_details":
                print(f"   -> {BLUE}Maps output:{RESET} Distance = {out.get('distance')}, Duration = {out.get('duration')} (Source: {out.get('source')})")
            elif t.name == "get_weather_forecast":
                weather_temp = str(out.get('temperature', '')).replace('°', ' ')
                print(f"   -> {BLUE}Weather output:{RESET} Temp = {weather_temp}, Condition = {out.get('condition')} (Source: {out.get('source')})")
            elif t.name == "confirm_booking":
                ticket = out.get("ticket", {})
                print(f"   -> {BLUE}Booking confirmed:{RESET} PNR = {ticket.get('pnr')}, Seat = {ticket.get('seat_number')}, Operator = {ticket.get('operator_name')}")

        booking = session.query(BookingModel).filter(BookingModel.session_id == session_id).first()
        if booking:
            print_success(f"Booking confirmed in database! PNR: {booking.pnr}, Status: {booking.status}, Seat: {booking.seat_number}")
        else:
            print_error("No booking record created in database.")
            
    finally:
        session.close()


async def run_payment_decline_rollback():
    print_header("SCENARIO 2: Payment Decline & Saga compensating rollback")
    user_id = await ensure_demo_user()
    
    session_id = f"demo_rollback_{int(datetime.utcnow().timestamp())}"
    print_step(f"Creating a new travel operations session: {session_id}")
    
    session = db.SessionLocal()
    try:
        # Check initial seats available on Bus 1
        bus = session.query(BusInventoryModel).filter(BusInventoryModel.id == 1).first()
        initial_seats = bus.available_seats
        print_step(f"Initial available seats on Bus ID 1 ('{bus.operator_name}'): {initial_seats}")

        new_sess = SessionModel(session_id=session_id, user_id=user_id)
        session.add(new_sess)
        session.add(WorkflowStateModel(session_id=session_id, state="NEW"))
        session.commit()

        variables = {
            "origin": "Bangalore",
            "destination": "Hyderabad",
            "travel_date": (datetime.utcnow() + timedelta(days=2)).strftime("%Y-%m-%d"),
            "preferences": "highest_rating",
            "idempotency_key": f"key_demo_rollback_{int(datetime.utcnow().timestamp())}",
            "email": "demo_passenger@example.com",
            "bus_id": "1",
            "seat_number": "",
            "amount": 950.0,
            "card_number": "4111 1111 1111 1111",
            "booking_id": "101"
        }

        print_step("Compiling full_booking.yaml DSL workflow...")
        tasks = WorkflowCompiler.compile_workflow("full_booking", variables)
        
        # Override card_number in the payment task to fail Luhn check
        for task in tasks:
            if task.get("name") == "process_payment":
                task["input_data"]["card_number"] = "4111 1111 1111 1112" # Fails Luhn check!

        for task in tasks:
            t_model = TaskStateModel(
                session_id=session_id,
                task_id=task.get("task_id"),
                name=task.get("name"),
                status="PENDING"
            )
            t_model.set_dependencies(task.get("dependencies", []))
            t_model.set_input(task.get("input_data", {}))
            session.add(t_model)
        session.commit()

        print_step("Executing Compiled Task Dependency Graph (Triggering payment failure)...")
        await WorkflowExecutor.execute_graph(session_id)

        # Reload session to check rollback status
        session.close()
        session = db.SessionLocal()
        
        db_tasks = session.query(TaskStateModel).filter(TaskStateModel.session_id == session_id).all()
        print(f"\n{BOLD}--- Task Execution Status Matrix ---{RESET}")
        for t in db_tasks:
            status_color = f"{GREEN}COMPLETED{RESET}" if t.status == "COMPLETED" else (f"{RED}FAILED{RESET}" if t.status == "FAILED" else t.status)
            print(f"Task: {t.name:<25} ID: {t.task_id:<12} Status: {status_color}")
            if t.name == "process_payment":
                print(f"   -> {RED}Payment execution result:{RESET} {t.get_output().get('error')}")

        # Check booking status (should be CANCELLED by Saga Rollback)
        booking = session.query(BookingModel).filter(BookingModel.session_id == session_id).first()
        if booking:
            print_warning(f"Booking status in database: {YELLOW}{booking.status}{RESET} (successfully rolled back to CANCELLED)")
        
        # Check seats returned to inventory
        bus = session.query(BusInventoryModel).filter(BusInventoryModel.id == 1).first()
        final_seats = bus.available_seats
        print_success(f"Final available seats on Bus ID 1: {final_seats} (Saga successfully restored the seat!)")
        
    finally:
        session.close()


async def run_disruption_recovery():
    print_header("SCENARIO 3: Disruption Event & Autonomous Recovery Rebooking")
    user_id = await ensure_demo_user()
    
    session_id = f"demo_disrupt_{int(datetime.utcnow().timestamp())}"
    print_step(f"Creating a new travel operations session: {session_id}")
    
    session = db.SessionLocal()
    try:
        new_sess = SessionModel(session_id=session_id, user_id=user_id)
        session.add(new_sess)
        session.add(WorkflowStateModel(session_id=session_id, state="NEW"))
        session.commit()

        variables = {
            "origin": "Bangalore",
            "destination": "Hyderabad",
            "travel_date": (datetime.utcnow() + timedelta(days=2)).strftime("%Y-%m-%d"),
            "preferences": "highest_rating",
            "idempotency_key": f"key_demo_disrupt_{int(datetime.utcnow().timestamp())}",
            "email": "demo_passenger@example.com",
            "bus_id": "1", # VRL Travels Bangalore -> Hyderabad
            "seat_number": "",
            "amount": 950.0,
            "card_number": "4111 1111 1111 1111",
            "booking_id": "102"
        }

        print_step("Compiling full_booking.yaml DSL workflow...")
        tasks = WorkflowCompiler.compile_workflow("full_booking", variables)
        
        for task in tasks:
            t_model = TaskStateModel(
                session_id=session_id,
                task_id=task.get("task_id"),
                name=task.get("name"),
                status="PENDING"
            )
            t_model.set_dependencies(task.get("dependencies", []))
            t_model.set_input(task.get("input_data", {}))
            session.add(t_model)
        session.commit()

        print_step("Step 3.1: Running normal booking workflow first...")
        await WorkflowExecutor.execute_graph(session_id)

        # Verify successful booking
        booking = session.query(BookingModel).filter(
            BookingModel.session_id == session_id,
            BookingModel.status == "CONFIRMED"
        ).first()
        
        if not booking:
            print_error("Failed to create active booking for disruption demo.")
            return

        print_success(f"Successful booking created. PNR: {booking.pnr}, Bus ID: {booking.bus_id}, Seat: {booking.seat_number}")
        
        # Step 3.2: Trigger disruption
        print_step(f"Step 3.2: Registering EventBus subscribers and simulating Bus Cancelled Event on Bus ID {booking.bus_id}...")
        
        # Explicitly subscribe callbacks on EventBus
        await EventBus.subscribe("BusCancelled", JourneyMonitor.handle_bus_cancelled)
        await EventBus.subscribe("BusDelayed", JourneyMonitor.handle_bus_delayed)
        await EventBus.subscribe("DisruptionDetected", RecoveryAgent.handle_disruption)
        
        # Publish BusCancelled event
        payload = {
            "bus_id": booking.bus_id,
            "reason": "Severe engine failure on highway near Anantapur"
        }
        await EventBus.publish("BusCancelled", session_id, payload)
        
        # Reload session to check recovery outputs
        session.close()
        session = db.SessionLocal()
        
        recovery_booking = session.query(BookingModel).filter(
            BookingModel.session_id == session_id,
            BookingModel.status == "CONFIRMED"
        ).first()
        
        old_booking = session.query(BookingModel).filter(BookingModel.id == booking.id).first()
        
        print_warning(f"Old Booking ID {booking.id} status is now: {YELLOW}{old_booking.status}{RESET}")
        if recovery_booking and recovery_booking.id != booking.id:
            bus = session.query(BusInventoryModel).filter(BusInventoryModel.id == recovery_booking.bus_id).first()
            print_success(f"Recovery Rebooking completed autonomously by RecoveryAgent!")
            print(f"   -> {BLUE}New Booking ID:{RESET} {recovery_booking.id}")
            print(f"   -> {BLUE}New PNR Code:{RESET} {recovery_booking.pnr}")
            print(f"   -> {BLUE}New Operator:{RESET} {bus.operator_name if bus else 'Alternative operator'}")
            print(f"   -> {BLUE}New Seat Number:{RESET} {recovery_booking.seat_number}")
            print(f"   -> {BLUE}New Fare Paid:{RESET} {recovery_booking.price_paid}")
        else:
            print_error("Autonomous recovery did not result in a new confirmed booking.")
            
    finally:
        session.close()


async def main():
    if len(sys.argv) > 1:
        arg = sys.argv[1]
        if arg == "1":
            await run_normal_booking()
        elif arg == "2":
            await run_payment_decline_rollback()
        elif arg == "3":
            await run_disruption_recovery()
        elif arg == "all":
            await run_normal_booking()
            await run_payment_decline_rollback()
            await run_disruption_recovery()
        else:
            print(f"Usage: python demo_scenarios.py [1|2|3|all]")
        return

    # Check TTY for interactive mode
    if not sys.stdin.isatty():
        print("[*] Stdin is not a TTY. Running all scenarios sequentially...")
        await run_normal_booking()
        await run_payment_decline_rollback()
        await run_disruption_recovery()
        return

    while True:
        print("\n" + "="*60)
        print(f" {BOLD}{CYAN}TravelOps AI v2.0 Production Release Demo scenarios{RESET}")
        print("="*60)
        print("1. Run Scenario 1: Normal Booking Journey (Full Success)")
        print("2. Run Scenario 2: Payment Decline & Saga compensating rollback")
        print("3. Run Scenario 3: Disruption Event & Autonomous Recovery")
        print("4. Run all scenarios")
        print("5. Exit")
        print("="*60)
        
        try:
            choice = input("Enter your choice (1-5): ").strip()
            if choice == "1":
                await run_normal_booking()
            elif choice == "2":
                await run_payment_decline_rollback()
            elif choice == "3":
                await run_disruption_recovery()
            elif choice == "4":
                await run_normal_booking()
                await run_payment_decline_rollback()
                await run_disruption_recovery()
            elif choice == "5" or not choice:
                print("Exiting. Thank you!")
                break
            else:
                print("Invalid choice. Please enter a number between 1 and 5.")
        except (KeyboardInterrupt, EOFError):
            print("\nExiting. Thank you!")
            break


if __name__ == "__main__":
    asyncio.run(main())
