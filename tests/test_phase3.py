import os
import sys
import unittest
import json
import asyncio
from unittest.mock import patch, MagicMock

# Add root folder to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.database.db import init_db, SessionLocal, engine, Base
from backend.database.models import TaskStateModel, CacheModel, WorkflowStateModel
from backend.services.llm import ModelRouter
from backend.services.prompt_loader import PromptLoader
from agents.planner.planner_agent import PlannerAgent
from agents.memory.memory_agent import MemoryAgent
from agents.reflection.reflection_agent import ReflectionAgent
from backend.workflows.orchestrator import WorkflowOrchestrator
import backend.tools.travel_tools


class TestTravelOpsPhase3(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ["DATABASE_URL"] = "sqlite:///:memory:"
        init_db()

    def setUp(self):
        self.db = SessionLocal()
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)

        # Seed mock buses for tool query consistency
        from backend.database.models import BusInventoryModel
        seats = json.dumps([f"{r}{c}" for r in range(1, 4) for c in ["A", "B"]])
        bus1 = BusInventoryModel(
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
        bus2 = BusInventoryModel(
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
        self.db.add(bus1)
        self.db.add(bus2)
        self.db.commit()

        self.model_router = ModelRouter()
        self.prompt_loader = PromptLoader()

    def tearDown(self):
        self.db.close()

    @patch("backend.services.llm.ModelRouter.generate")
    def test_planner_agent(self, mock_generate):
        # Mock planner JSON response
        mock_tasks = {
            "tasks": [
                {
                    "task_id": "search_1",
                    "name": "search_buses",
                    "dependencies": [],
                    "input_data": {"origin": "Bangalore", "destination": "Hyderabad", "travel_date": "2026-06-28"}
                },
                {
                    "task_id": "recommend_1",
                    "name": "recommend_options",
                    "dependencies": ["search_1"],
                    "input_data": {"preference": "highest_rating"}
                }
            ]
        }
        mock_generate.return_value = {"success": True, "content": json.dumps(mock_tasks)}

        planner = PlannerAgent(self.model_router, self.prompt_loader)
        graph = planner.generate_plan("Bangalore", "Hyderabad", "2026-06-28")
        
        self.assertIn("tasks", graph)
        self.assertEqual(len(graph["tasks"]), 2)
        self.assertEqual(graph["tasks"][0]["task_id"], "search_1")

    def test_memory_agent_heuristics(self):
        # Test heuristic fallback of MemoryAgent
        memory_agent = MemoryAgent(self.model_router, self.prompt_loader)
        
        # Test cheapest preference
        res_cheap = memory_agent.parse_preference_text("find the cheapest ticket please")
        self.assertEqual(res_cheap["sorting_preference"], "cheapest")

        # Test operator preference
        res_op = memory_agent.parse_preference_text("I want a VRL Travels bus")
        self.assertEqual(res_op["operator_preference"], "VRL")

        # Test seat preference
        res_seat = memory_agent.parse_preference_text("get me a window seat")
        self.assertEqual(res_seat["seat_preference"], "window")

    @patch("backend.services.llm.ModelRouter.generate")
    def test_memory_agent_llm(self, mock_generate):
        mock_generate.return_value = {
            "success": True,
            "content": json.dumps({
                "operator_preference": "KSRTC",
                "sorting_preference": "highest_rating",
                "seat_preference": "aisle",
                "reasoning_summary": "Extracted preferences successfully."
            })
        }
        
        memory_agent = MemoryAgent(self.model_router, self.prompt_loader)
        res = memory_agent.save_preference("session_test", "I want a high rated KSRTC aisle seat")
        
        self.assertEqual(res["operator_preference"], "KSRTC")
        self.assertEqual(res["sorting_preference"], "highest_rating")
        self.assertEqual(res["seat_preference"], "aisle")

        # Retrieve and verify persistence
        retrieved = memory_agent.retrieve_preferences("session_test")
        self.assertEqual(retrieved["operator_preference"], "KSRTC")

    @patch("backend.services.llm.ModelRouter.generate")
    def test_reflection_agent(self, mock_generate):
        session_id = "session_fail_test"
        failed_task_id = "hold_1"
        
        # Seed a failed task
        failed_task = TaskStateModel(
            session_id=session_id,
            task_id=failed_task_id,
            name="hold_seat",
            status="FAILED"
        )
        failed_task.set_input({"seat_number": "1A"})
        self.db.add(failed_task)
        self.db.commit()

        # Mock repair response
        mock_repair = {
            "action": "retry",
            "reasoning_summary": "Seat 1A was taken, retrying with seat 1B",
            "new_tasks": [
                {
                    "task_id": "hold_1",
                    "name": "hold_seat",
                    "dependencies": [],
                    "input_data": {"seat_number": "1B"}
                }
            ]
        }
        mock_generate.return_value = {"success": True, "content": json.dumps(mock_repair)}

        reflector = ReflectionAgent(self.model_router, self.prompt_loader)
        repaired = reflector.reflect_and_repair(session_id, failed_task_id, "Seat already booked")
        
        self.assertTrue(repaired)
        
        # Verify db state updated
        self.db.expire_all()
        updated_task = self.db.query(TaskStateModel).filter(
            TaskStateModel.session_id == session_id,
            TaskStateModel.task_id == failed_task_id
        ).first()
        self.assertEqual(updated_task.status, "PENDING")
        self.assertEqual(updated_task.get_input()["seat_number"], "1B")

    def test_orchestrator_execution(self):
        session_id = "session_orch_test"
        
        # Seed some tasks
        task_search = TaskStateModel(
            session_id=session_id,
            task_id="search_1",
            name="search_buses",
            status="PENDING"
        )
        task_search.set_input({"origin": "Bangalore", "destination": "Hyderabad", "travel_date": "2026-06-28"})
        
        task_rec = TaskStateModel(
            session_id=session_id,
            task_id="recommend_1",
            name="recommend_options",
            status="PENDING"
        )
        task_rec.set_dependencies(["search_1"])
        task_rec.set_input({"preference": "highest_rating"})

        self.db.add(task_search)
        self.db.add(task_rec)
        self.db.commit()

        # Run orchestrator execute loop synchronously using asyncio run
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(WorkflowOrchestrator.execute_graph(session_id))
        finally:
            loop.close()

        # Verify tasks are completed
        self.db.expire_all()
        t1 = self.db.query(TaskStateModel).filter(TaskStateModel.session_id == session_id, TaskStateModel.task_id == "search_1").first()
        t2 = self.db.query(TaskStateModel).filter(TaskStateModel.session_id == session_id, TaskStateModel.task_id == "recommend_1").first()
        
        self.assertEqual(t1.status, "COMPLETED")
        self.assertEqual(t2.status, "COMPLETED")
        self.assertIn("buses", t1.get_output())
        self.assertIn("recommended_buses", t2.get_output())


if __name__ == "__main__":
    unittest.main()
