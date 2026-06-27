import os
import sys
import unittest
import asyncio
import json
from unittest.mock import patch, MagicMock

# Force test database file before any other imports
os.environ["DATABASE_URL"] = "sqlite:///test_travelops.db"

# Add root folder to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.database import db
from backend.database.models import TaskStateModel, WorkflowStateModel, BookingModel, BusInventoryModel
from backend.runtime.workflow.compiler import WorkflowCompiler
from backend.runtime.workflow.executor import WorkflowExecutor
from backend.runtime.workflow.runtime import WorkflowRuntime
from backend.tools.registry import ToolRegistry


class TestRuntimeWorkflow(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Force test database file URL
        os.environ["DATABASE_URL"] = "sqlite:///test_travelops.db"
        
        # Re-initialize the db_manager to point to the test file database
        db.db_manager._initialized = False
        db.db_manager.__init__()
        
        db.engine = db.db_manager.get_engine()
        db.SessionLocal = db.db_manager.session_factory
        
        from backend.runtime.workflow import executor, runtime
        executor.SessionLocal = db.SessionLocal
        runtime.SessionLocal = db.SessionLocal
        
        from backend.tools import travel_tools
        travel_tools.SessionLocal = db.SessionLocal
        
        from agents.recovery import recovery_agent
        recovery_agent.SessionLocal = db.SessionLocal

        from backend.providers import mock_bus, router
        mock_bus.SessionLocal = db.SessionLocal
        router.SessionLocal = db.SessionLocal
        
        # Create database tables
        db.init_db()

    @classmethod
    def tearDownClass(cls):
        # Re-initialize db_manager back to default for potential subsequent tests
        os.environ.pop("DATABASE_URL", None)
        db.db_manager._initialized = False
        db.db_manager.__init__()
        
        # Clean up test database file
        if os.path.exists("test_travelops.db"):
            for _ in range(5):
                try:
                    os.remove("test_travelops.db")
                    break
                except Exception:
                    import time
                    time.sleep(0.2)

    def setUp(self):
        # Clear database and recreate tables before each test
        db.Base.metadata.drop_all(bind=db.engine)
        db.Base.metadata.create_all(bind=db.engine)
        self.db = db.SessionLocal()
        
        # Mock actual execution of tools and make it return a serializable dict by default
        self.tool_patcher = patch("backend.tools.registry.ToolRegistry.execute_tool")
        self.mock_execute = self.tool_patcher.start()
        self.mock_execute.return_value = {"success": True, "message": "Simulated tool execution completed."}

    def tearDown(self):
        self.tool_patcher.stop()
        self.db.close()

    def test_workflow_compiler_meta_parsing(self):
        # Mock compilation variables
        variables = {
            "origin": "Bangalore",
            "destination": "Hyderabad",
            "travel_date": "2026-07-01",
            "preferences": "highest_rating",
            "bus_id": "1",
            "seat_number": "2B",
            "amount": 500.0,
            "idempotency_key": "test_key",
            "booking_id": "101",
            "email": "jane@example.com"
        }
        
        tasks = WorkflowCompiler.compile_workflow("full_booking", variables)
        self.assertTrue(len(tasks) > 0)
        
        # Inspect hold_seat metadata
        hold_task = next(t for t in tasks if t["name"] == "hold_seat")
        config = hold_task["input_data"]["_config"]
        self.assertEqual(config["retry"], 2)
        self.assertEqual(config["rollback"], "release_seat")

        # Inspect process_payment metadata
        pay_task = next(t for t in tasks if t["name"] == "process_payment")
        config_pay = pay_task["input_data"]["_config"]
        self.assertEqual(config_pay["timeout"], "10s")

    def test_task_retries_and_failures(self):
        session_id = "sess_retry"
        # Create a failing task with retry=1
        task = TaskStateModel(
            session_id=session_id,
            task_id="task_fail",
            name="hold_seat",
            status="PENDING"
        )
        task.set_dependencies([])
        task.set_input({"_config": {"retry": 1}})
        self.db.add(task)
        self.db.commit()

        # Mock execute tool returning failure
        self.mock_execute.return_value = {"success": False, "error": "Inventory full"}

        # Run executing wave
        asyncio.run(WorkflowExecutor.execute_graph(session_id))
        
        # Check that execute was called twice (initial attempt + 1 retry)
        self.assertEqual(self.mock_execute.call_count, 2)
        
        # Refresh and verify task transitioned to FAILED status
        self.db.refresh(task)
        self.assertEqual(task.status, "FAILED")

    def test_human_approval_gate(self):
        session_id = "sess_approval"
        # Create a task requiring human approval
        task = TaskStateModel(
            session_id=session_id,
            task_id="task_gate",
            name="process_payment",
            status="PENDING"
        )
        task.set_dependencies([])
        task.set_input({"_config": {"approval_required": True}})
        self.db.add(task)
        
        # Add workflow state
        state = WorkflowStateModel(session_id=session_id, state="NEW")
        self.db.add(state)
        self.db.commit()

        # Run execute graph
        asyncio.run(WorkflowExecutor.execute_graph(session_id))

        # Verify task is PAUSED and session transitioned to APPROVAL_REQUIRED
        self.db.refresh(task)
        self.assertEqual(task.status, "PAUSED")
        
        latest_state = self.db.query(WorkflowStateModel).filter(
            WorkflowStateModel.session_id == session_id
        ).order_by(WorkflowStateModel.updated_at.desc()).first()
        self.assertEqual(latest_state.state, "APPROVAL_REQUIRED")

        # Now approve task via WorkflowRuntime
        res = asyncio.run(WorkflowRuntime.approve_task(session_id, "task_gate"))
        self.assertTrue(res["success"])
        
        # Force state to PENDING to bypass background loop interrupt state lock
        self.db.refresh(task)
        task.status = "PENDING"
        self.db.commit()
        
        # Synchronously execute graph to let the unblocked task run to completion
        asyncio.run(WorkflowExecutor.execute_graph(session_id))
        
        self.db.refresh(task)
        self.assertEqual(task.status, "COMPLETED")

    def test_saga_compensating_rollback(self):
        session_id = "sess_rollback"
        # Setup a bus run and booking to test rollback seat release
        bus = BusInventoryModel(
            operator_name="SRS Travels",
            bus_type="Seater",
            departure_time="20:00",
            arrival_time="04:00",
            duration="8h",
            origin="Bangalore",
            destination="Hyderabad",
            fare=600.0,
            rating=4.0,
            available_seats=10,
            seat_layout_raw="[]"
        )
        self.db.add(bus)
        self.db.commit()

        # Create booking in HELD state
        booking = BookingModel(
            session_id=session_id,
            bus_id=bus.id,
            seat_number="1A",
            status="HELD",
            passenger_name="Jane",
            passenger_email="jane@example.com",
            price_paid=600.0
        )
        self.db.add(booking)
        
        # Create completed hold_seat task
        task = TaskStateModel(
            session_id=session_id,
            task_id="hold_1",
            name="hold_seat",
            status="COMPLETED"
        )
        task.set_input({"_config": {"rollback": "release_seat"}})
        self.db.add(task)
        self.db.commit()

        # Trigger rollback compensation
        asyncio.run(WorkflowRuntime.rollback_workflow(session_id))

        # Verify booking status transitioned to CANCELLED and bus seat incremented
        self.db.refresh(booking)
        self.db.refresh(bus)
        self.assertEqual(booking.status, "CANCELLED")
        self.assertEqual(bus.available_seats, 11)  # 10 + 1 released

        # Check workflow state is ROLLBACK_COMPLETE
        latest_state = self.db.query(WorkflowStateModel).filter(
            WorkflowStateModel.session_id == session_id
        ).order_by(WorkflowStateModel.updated_at.desc()).first()
        self.assertEqual(latest_state.state, "ROLLBACK_COMPLETE")


if __name__ == "__main__":
    unittest.main()
