import unittest
from backend.api.main import agent_runtime
from agents.intent.intent_agent import IntentAgent
from agents.planner.planner_agent import PlannerAgent
from agents.memory.memory_agent import MemoryAgent
from agents.reflection.reflection_agent import ReflectionAgent

class TestDynamicAgentRouting(unittest.TestCase):
    def test_core_agents_resolution(self):
        # Resolve Intent Agent
        intent_agent = agent_runtime.get_agent_by_capability("intent")
        self.assertIsInstance(intent_agent, IntentAgent)

        # Resolve Planner Agent
        planner_agent = agent_runtime.get_agent_by_capability("plan")
        self.assertIsInstance(planner_agent, PlannerAgent)

        # Resolve Memory Agent
        memory_agent = agent_runtime.get_agent_by_capability("memory")
        self.assertIsInstance(memory_agent, MemoryAgent)

        # Resolve Reflection Agent
        reflection_agent = agent_runtime.get_agent_by_capability("reflection")
        self.assertIsInstance(reflection_agent, ReflectionAgent)

    def test_health_report_structure(self):
        report = agent_runtime.get_health_report()
        self.assertTrue(len(report) > 0)
        
        # Verify schema shapes
        first_agent = report[0]
        self.assertIn("name", first_agent)
        self.assertIn("version", first_agent)
        self.assertIn("capabilities", first_agent)
        self.assertIn("health", first_agent)
        self.assertIn("avg_latency", first_agent)
