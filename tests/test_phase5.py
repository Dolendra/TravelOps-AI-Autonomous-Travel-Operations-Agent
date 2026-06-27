import os
import sys
import unittest
from unittest.mock import patch, MagicMock

# Add root folder to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.database.db import init_db, SessionLocal
from backend.services.llm import ModelRouter
from backend.services.rag import RAGEngine

class TestTravelOpsPhase5(unittest.TestCase):
    def test_cost_calculation_reasoning_model(self):
        router = ModelRouter()
        # Mocking groq client chat completion return
        mock_completion = MagicMock()
        mock_completion.choices = [MagicMock()]
        mock_completion.choices[0].message.content = "Mock response content"
        mock_completion.usage.prompt_tokens = 2000
        mock_completion.usage.completion_tokens = 500
        mock_completion.usage.total_tokens = 2500
        
        router.client = MagicMock()
        router.client.chat.completions.create.return_value = mock_completion
        
        res = router.generate(
            messages=[{"role": "user", "content": "test"}],
            capability="reasoning"
        )
        
        # Groq Llama 3 70B pricing:
        # Prompt: $0.59/1M, Completion: $0.79/1M
        # (2000 * 0.59 + 500 * 0.79) / 1,000,000 = (1180 + 395) / 1,000,000 = 1575 / 1,000,000 = 0.001575 USD
        self.assertTrue(res["success"])
        self.assertAlmostEqual(res["estimated_cost_usd"], 0.001575)
        
        metric = router.get_metrics()[0]
        self.assertAlmostEqual(metric["estimated_cost_usd"], 0.001575)

    def test_cost_calculation_fast_model(self):
        router = ModelRouter()
        mock_completion = MagicMock()
        mock_completion.choices = [MagicMock()]
        mock_completion.choices[0].message.content = "Fast response content"
        mock_completion.usage.prompt_tokens = 1000
        mock_completion.usage.completion_tokens = 200
        mock_completion.usage.total_tokens = 1200
        
        router.client = MagicMock()
        router.client.chat.completions.create.return_value = mock_completion
        
        res = router.generate(
            messages=[{"role": "user", "content": "test"}],
            capability="fast"
        )
        
        # Groq Llama 3 8B pricing:
        # Prompt: $0.05/1M, Completion: $0.08/1M
        # (1000 * 0.05 + 200 * 0.08) / 1,000,000 = (50 + 16) / 1,000,000 = 66 / 1,000,000 = 0.000066 USD
        self.assertTrue(res["success"])
        self.assertAlmostEqual(res["estimated_cost_usd"], 0.000066)

    def test_rag_knowledge_base_retrieval(self):
        # Trigger load faq context
        RAGEngine.load_knowledge_base()
        
        # 1. Check baggage policy search
        baggage_context = RAGEngine.get_matching_context("baggage limits allowed", top_k=1)
        self.assertIn("15 kg", baggage_context)
        self.assertIn("7 kg", baggage_context)
        
        # 2. Check upgrade policy search
        upgrade_context = RAGEngine.get_matching_context("upgrade loyalty points", top_k=1)
        self.assertIn("1000 loyalty points", upgrade_context)

if __name__ == "__main__":
    unittest.main()
