import os
import sys
import unittest
from datetime import datetime

# Add the root directory to path so we can import backend packages
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.database.db import init_db, SessionLocal, engine, Base
from backend.database.models import (
    SessionModel, WorkflowStateModel, TaskStateModel, AuditLogModel, EventStoreModel
)
from backend.services.prompt_loader import PromptLoader
from backend.tools.registry import BaseTool, ToolRegistry, register_tool

# Define a mock tool for testing
class MockTestTool(BaseTool):
    @property
    def name(self) -> str:
        return "mock_test_tool"

    @property
    def description(self) -> str:
        return "A mock tool for unit testing."

    def execute(self, session_id: str, **kwargs) -> dict:
        return {"success": True, "received": kwargs}


class TestTravelOpsInfrastructure(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Configure database to use in-memory SQLite for clean testing
        os.environ["DATABASE_URL"] = "sqlite:///:memory:"
        init_db()

    def setUp(self):
        self.db = SessionLocal()
        # Clean state for test runs
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)

    def tearDown(self):
        self.db.close()

    def test_database_models_persistence(self):
        # 1. Test SessionModel
        session_id = "test_session_123"
        session = SessionModel(session_id=session_id)
        self.db.add(session)
        self.db.commit()

        saved_session = self.db.query(SessionModel).filter_by(session_id=session_id).first()
        self.assertIsNotNone(saved_session)
        self.assertEqual(saved_session.session_id, session_id)

        # 2. Test WorkflowStateModel
        state = WorkflowStateModel(session_id=session_id, state="SEARCHING")
        self.db.add(state)
        self.db.commit()

        saved_state = self.db.query(WorkflowStateModel).filter_by(session_id=session_id).first()
        self.assertIsNotNone(saved_state)
        self.assertEqual(saved_state.state, "SEARCHING")

        # 3. Test TaskStateModel
        task = TaskStateModel(session_id=session_id, task_id="task_1", name="search_buses", status="PENDING")
        task.set_dependencies(["dep_1", "dep_2"])
        task.set_input({"query": "delhi"})
        self.db.add(task)
        self.db.commit()

        saved_task = self.db.query(TaskStateModel).filter_by(task_id="task_1").first()
        self.assertIsNotNone(saved_task)
        self.assertEqual(saved_task.get_dependencies(), ["dep_1", "dep_2"])
        self.assertEqual(saved_task.get_input(), {"query": "delhi"})

    def test_prompt_loader(self):
        # Set up a temporary prompts directory path
        temp_prompts_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "temp_prompts")
        os.makedirs(temp_prompts_dir, exist_ok=True)
        
        test_prompt_file = os.path.join(temp_prompts_dir, "test_template.md")
        with open(test_prompt_file, "w", encoding="utf-8") as f:
            f.write("Hello {{name}}, welcome to {{destination}}!")

        try:
            loader = PromptLoader(prompts_dir=temp_prompts_dir)
            rendered = loader.load_prompt("test_template", {"name": "Alice", "destination": "Paris"})
            self.assertEqual(rendered, "Hello Alice, welcome to Paris!")
        finally:
            # Clean up
            if os.path.exists(test_prompt_file):
                os.remove(test_prompt_file)
            if os.path.exists(temp_prompts_dir):
                os.rmdir(temp_prompts_dir)

    def test_tool_registry_and_auditing(self):
        # Register mock tool
        ToolRegistry.register(MockTestTool())
        
        # Verify listing
        tools = ToolRegistry.list_tools()
        names = [t["name"] for t in tools]
        self.assertIn("mock_test_tool", names)

        # Execute mock tool and verify logs are written to database audit_logs
        session_id = "test_session_tools"
        result = ToolRegistry.execute_tool("mock_test_tool", session_id, param1="value1")
        self.assertTrue(result["success"])
        self.assertEqual(result["received"], {"param1": "value1"})

        # Verify audit logs in SQLite
        logs = self.db.query(AuditLogModel).filter_by(session_id=session_id).all()
        self.assertGreater(len(logs), 0)
        self.assertEqual(logs[0].agent_name, "ToolRegistry")
        self.assertIn("tool_call:mock_test_tool", logs[0].action)
        self.assertTrue(logs[0].get_payload()["success"])


if __name__ == "__main__":
    unittest.main()
