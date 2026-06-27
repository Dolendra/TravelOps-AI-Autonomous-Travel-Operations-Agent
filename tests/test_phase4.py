import os
import sys
import unittest
import json
import asyncio
from unittest.mock import patch, MagicMock

# Add root folder to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.database.db import init_db, SessionLocal, engine, Base
from backend.database.models import BookingModel, BusInventoryModel, TaskStateModel, CacheModel, WorkflowStateModel
from backend.events.event_bus import EventBus
from backend.services.scheduler import JobScheduler
from agents.monitor.journey_monitor import JourneyMonitor
from agents.recovery.recovery_agent import RecoveryAgent
import backend.tools.travel_tools  # Register tools


class TestTravelOpsPhase4(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ["DATABASE_URL"] = "sqlite:///:memory:"
        init_db()

    def setUp(self):
        self.db = SessionLocal()
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)

        # Seed mock buses
        seats = json.dumps([f"{r}{c}" for r in range(1, 4) for c in ["A", "B"]])
        self.bus1 = BusInventoryModel(
            operator_name="VRL Travels",
            bus_type="Sleeper",
            departure_time="22:00",
            arrival_time="06:00",
            duration="8h",
            origin="Bangalore",
            destination="Hyderabad",
            fare=1000.0,
            rating=4.5,
            available_seats=6,
            seat_layout_raw=seats
        )
        self.bus2 = BusInventoryModel(
            operator_name="SRS Travels",
            bus_type="Seater",
            departure_time="20:00",
            arrival_time="04:00",
            duration="8h",
            origin="Bangalore",
            destination="Hyderabad",
            fare=600.0,
            rating=3.9,
            available_seats=6,
            seat_layout_raw=seats
        )
        self.db.add(self.bus1)
        self.db.add(self.bus2)
        self.db.commit()

    def tearDown(self):
        self.db.close()

    def test_job_scheduler(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        fired = []
        async def mock_callback(arg):
            fired.append(arg)

        # Test schedule once
        try:
            JobScheduler.schedule_once("test_job_1", 0.1, mock_callback, "hello")
            loop.run_until_complete(asyncio.sleep(0.2))
            self.assertIn("hello", fired)
            
            # Test cancellation
            fired.clear()
            JobScheduler.schedule_once("test_job_2", 0.5, mock_callback, "world")
            JobScheduler.cancel_job("test_job_2")
            loop.run_until_complete(asyncio.sleep(0.6))
            self.assertNotIn("world", fired)
        finally:
            loop.close()

    @patch("backend.events.event_bus.EventBus.publish")
    def test_journey_monitor_cancellation(self, mock_publish):
        session_id = "session_monitor_test"
        
        # 1. Create active booking for bus 1
        booking = BookingModel(
            session_id=session_id,
            bus_id=self.bus1.id,
            seat_number="1A",
            status="CONFIRMED",
            passenger_name="Alice Green",
            price_paid=1000.0
        )
        self.db.add(booking)
        self.db.commit()

        # Run JourneyMonitor handle cancelled
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(
                JourneyMonitor.handle_bus_cancelled(session_id, {"bus_id": self.bus1.id, "reason": "Accident"})
            )
        finally:
            loop.close()

        # Check workflow state updated to DISRUPTED
        self.db.expire_all()
        state = self.db.query(WorkflowStateModel).filter(WorkflowStateModel.session_id == session_id).first()
        self.assertEqual(state.state, "DISRUPTED")
        
        # Check EventBus.publish was called for DisruptionDetected
        mock_publish.assert_called_with("DisruptionDetected", session_id, {
            "session_id": session_id,
            "bus_id": self.bus1.id,
            "booking_id": booking.id,
            "disruption_type": "cancellation",
            "reason": "Accident"
        })

    @patch("agents.memory.memory_agent.MemoryAgent.retrieve_preferences")
    def test_recovery_agent_rebooking(self, mock_retrieve):
        session_id = "session_recovery_test"
        
        # Mock preferences to rank SRS Travels (cheapest)
        mock_retrieve.return_value = {"sorting_preference": "cheapest"}
        
        # 1. Create booking for bus 1 (VRL Travels)
        booking = BookingModel(
            session_id=session_id,
            bus_id=self.bus1.id,
            seat_number="1A",
            status="CONFIRMED",
            passenger_name="Bob Brown",
            passenger_email="bob@example.com",
            price_paid=1000.0
        )
        self.db.add(booking)
        
        # Seed search task for parameter retrieval
        search_task = TaskStateModel(
            session_id=session_id,
            task_id="search_1",
            name="search_buses",
            status="COMPLETED"
        )
        search_task.set_input({"origin": "Bangalore", "destination": "Hyderabad", "travel_date": "2026-06-28"})
        self.db.add(search_task)
        self.db.commit()

        # Run RecoveryAgent handle disruption
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(
                RecoveryAgent.handle_disruption(session_id, {
                    "bus_id": self.bus1.id,
                    "booking_id": booking.id,
                    "disruption_type": "cancellation"
                })
            )
        finally:
            loop.close()

        # Verify old booking cancelled, new booking created for bus 2 (SRS Travels)
        self.db.expire_all()
        
        old_booking = self.db.query(BookingModel).filter(BookingModel.id == booking.id).first()
        self.assertEqual(old_booking.status, "CANCELLED")
        
        new_booking = self.db.query(BookingModel).filter(
            BookingModel.session_id == session_id,
            BookingModel.bus_id == self.bus2.id
        ).first()
        
        self.assertIsNotNone(new_booking)
        self.assertEqual(new_booking.status, "CONFIRMED")
        self.assertEqual(new_booking.price_paid, 600.0) # Price of SRS Travels
        self.assertIsNotNone(new_booking.pnr)
        
        # Check final workflow state updated to BOOKED
        state = self.db.query(WorkflowStateModel).filter(
            WorkflowStateModel.session_id == session_id
        ).order_by(WorkflowStateModel.id.desc()).first()
        self.assertEqual(state.state, "BOOKED")


if __name__ == "__main__":
    unittest.main()
