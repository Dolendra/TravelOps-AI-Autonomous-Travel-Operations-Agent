import unittest
from backend.runtime.agent_runtime import AgentRuntime, AgentUnhealthyError, AgentExecutionError

class MockSearchAgent:
    def __init__(self):
        self.call_count = 0
        self.should_fail = False

    def search_buses(self, origin: str, destination: str) -> list:
        self.call_count += 1
        if self.should_fail:
            raise ValueError("API Connection Timeout")
        return [{"id": 1, "operator": "SRS Travels", "origin": origin, "destination": destination}]


class TestAgentRuntime(unittest.TestCase):
    def test_registration_and_execution(self):
        runtime = AgentRuntime()
        agent = MockSearchAgent()
        
        # Register search agent
        runtime.register_agent(
            name="SearchAgent",
            version="2.0.0",
            capabilities=["search", "query_buses"],
            instance=agent
        )
        
        # Verify routing by capability
        resolved = runtime.get_agent_by_capability("search")
        self.assertIs(resolved, agent)
        
        # Verify execution
        res = runtime.execute("search", "search_buses", "Bangalore", "Goa")
        self.assertEqual(len(res), 1)
        self.assertEqual(res[0]["operator"], "SRS Travels")
        self.assertEqual(agent.call_count, 1)

    def test_version_routing(self):
        runtime = AgentRuntime()
        agent_v1 = MockSearchAgent()
        agent_v2 = MockSearchAgent()
        
        runtime.register_agent("SearchAgentV1", "1.0.0", ["search"], agent_v1)
        runtime.register_agent("SearchAgentV2", "2.0.0", ["search"], agent_v2)
        
        # Should route to v2 when specified
        resolved = runtime.get_agent_by_capability("search", version="2.0.0")
        self.assertIs(resolved, agent_v2)
        
        # Should route to v1 when specified
        resolved = runtime.get_agent_by_capability("search", version="1.0.0")
        self.assertIs(resolved, agent_v1)

    def test_health_degradation_and_circuit_breaker(self):
        runtime = AgentRuntime()
        agent = MockSearchAgent()
        
        runtime.register_agent(
            name="FailingAgent",
            version="1.0.0",
            capabilities=["fail_capability"],
            instance=agent,
            max_consecutive_failures=2
        )
        
        # First execution fails -> Degraded state
        agent.should_fail = True
        with self.assertRaises(AgentExecutionError):
            runtime.execute("fail_capability", "search_buses", "A", "B")
            
        report = runtime.get_health_report()
        self.assertEqual(report[0]["health"], "DEGRADED")
        
        # Second execution fails -> UNHEALTHY state
        with self.assertRaises(AgentExecutionError):
            runtime.execute("fail_capability", "search_buses", "A", "B")
            
        report = runtime.get_health_report()
        self.assertEqual(report[0]["health"], "UNHEALTHY")
        
        # Third execution blocked immediately via circuit breaker (unhealthy state)
        with self.assertRaises(AgentUnhealthyError):
            runtime.execute("fail_capability", "search_buses", "A", "B")
            
        # Repair the agent and manually reset health check
        agent.should_fail = False
        entry = runtime.registry["failingagent"]
        entry["metadata"].record_success(0.01) # Simulated manual recovery health check success
        
        # Executing now succeeds
        res = runtime.execute("fail_capability", "search_buses", "A", "B")
        self.assertEqual(len(res), 1)
        self.assertEqual(runtime.registry["failingagent"]["metadata"].health, "HEALTHY")
