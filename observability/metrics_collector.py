import logging
from typing import Dict, Any

logger = logging.getLogger("travelops.observability.metrics_collector")

class MetricsCollector:
    # Official Groq API token pricing configurations (USD per million tokens)
    PRICING = {
        "llama3-70b-8192": {
            "prompt_rate_per_million": 0.59,
            "completion_rate_per_million": 0.79
        },
        "llama3-8b-8192": {
            "prompt_rate_per_million": 0.05,
            "completion_rate_per_million": 0.08
        }
    }

    @classmethod
    def calculate_llm_cost(cls, model_name: str, prompt_tokens: int, completion_tokens: int) -> float:
        """Calculates estimated USD token cost for the given model run."""
        pricing = cls.PRICING.get(model_name)
        if not pricing:
            # Default fallback pricing (similar to llama3-8b-8192)
            pricing = cls.PRICING["llama3-8b-8192"]
            
        p_rate = pricing["prompt_rate_per_million"]
        c_rate = pricing["completion_rate_per_million"]
        
        cost = (prompt_tokens * p_rate + completion_tokens * c_rate) / 1000000.0
        return round(cost, 6)
