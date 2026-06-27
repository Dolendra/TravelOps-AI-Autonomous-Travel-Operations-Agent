import os
import sys
import unittest
import time
from unittest.mock import patch, MagicMock

# Add root folder to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.runtime.context.models import ContextFragment, ContextBundle
from backend.runtime.context.budget import TokenBudgetManager
from backend.runtime.context.cache import ContextCache
from backend.runtime.context.builder import AIRuntime
from backend.services.prompt_loader import PromptLoader


class TestRuntimeContext(unittest.TestCase):
    def setUp(self):
        self.model_router = MagicMock()
        self.model_router.api_key = "dummy_key"
        self.prompt_loader = PromptLoader()
        self.runtime = AIRuntime(self.model_router, self.prompt_loader)

    def test_dynamic_token_budget_bounds(self):
        # Test default agent budget
        manager_def = TokenBudgetManager(limit=8000)
        self.assertEqual(manager_def.limit, 8000)

        # Test intent agent budget limit
        manager_intent = TokenBudgetManager(agent="intent")
        self.assertEqual(manager_intent.limit, 2500)

        # Test support agent budget limit
        manager_support = TokenBudgetManager(agent="support")
        self.assertEqual(manager_support.limit, 6000)

        # Test planner agent budget limit
        manager_planner = TokenBudgetManager(agent="planner")
        self.assertEqual(manager_planner.limit, 12000)

        # Test reflection agent budget limit
        manager_reflection = TokenBudgetManager(agent="reflection")
        self.assertEqual(manager_reflection.limit, 10000)

    def test_context_bundle_metadata_and_hashing(self):
        messages = [{"role": "system", "content": "Welcome to TravelOps v2"}]
        bundle = ContextBundle(
            messages=messages,
            token_usage=15,
            sources=["system"],
            removed_sections=["history"],
            trace_id="trace_test_123",
            version="2.0.0",
            explainability={"system": "System instructions"}
        )

        self.assertEqual(bundle.version, "2.0.0")
        self.assertEqual(bundle.trace_id, "trace_test_123")
        self.assertEqual(bundle.token_count, 15)
        self.assertIn("system", bundle.explainability)
        self.assertTrue(len(bundle.hash) == 64)  # SHA-256 is 64 hex chars
        self.assertTrue(bundle.expires_at > bundle.created_at)

    def test_context_cache_expiration(self):
        cache = ContextCache()
        bundle = ContextBundle(
            messages=[{"role": "user", "content": "hi"}],
            token_usage=10,
            sources=["system"],
            removed_sections=[],
            trace_id="test_trace",
            ttl_seconds=1  # 1 second TTL
        )
        
        agent = "support"
        session_id = "sess_1"
        query = "hello"

        cache.set(agent, session_id, query, None, bundle)
        self.assertIsNotNone(cache.get(agent, session_id, query, None))

        # Sleep to simulate TTL lease expiry
        time.sleep(1.1)
        self.assertIsNone(cache.get(agent, session_id, query, None))


if __name__ == "__main__":
    unittest.main()
