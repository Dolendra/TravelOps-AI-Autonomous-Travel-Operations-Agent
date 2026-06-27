import os
import time
import logging
from typing import List, Dict, Any, Optional
from groq import Groq
from dotenv import load_dotenv
from observability.metrics_collector import MetricsCollector

load_dotenv()

# Setup Logging
logger = logging.getLogger("travelops.services.llm")
logging.basicConfig(level=logging.INFO)

class ModelRouter:
    # Model Mappings based on requested capability
    CAPABILITY_MAP = {
        "reasoning": "llama3-70b-8192",  # Equivalent of 120B reasoning model on Groq
        "fast": "llama3-8b-8192"         # Equivalent of 20B fast model on Groq
    }

    DEFAULT_CAPABILITY = "fast"

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get("GROQ_API_KEY")
        if not self.api_key:
            logger.warning("GROQ_API_KEY environment variable is not set. LLM calls will fail.")
        
        # Initialize Groq Client
        self.client = Groq(api_key=self.api_key) if self.api_key else None
        
        # In-memory metrics tracking for Observability
        self.metrics_log: List[Dict[str, Any]] = []

    def generate(
        self,
        messages: List[Dict[str, str]],
        capability: str = "fast",
        temperature: float = 0.0,
        response_format: Optional[Dict[str, str]] = None,
        max_tokens: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Routes the messages to the target LLM based on requested capability.
        Returns a dict with completion content and execution metrics.
        """
        if not self.client:
            raise ValueError("Groq client not initialized. Ensure GROQ_API_KEY is provided.")

        model = self.CAPABILITY_MAP.get(capability, self.CAPABILITY_MAP[self.DEFAULT_CAPABILITY])
        
        start_time = time.time()
        logger.info(f"Routing request to model: {model} (Capability: {capability})")

        try:
            # Build API Call Arguments
            kwargs = {
                "model": model,
                "messages": messages,
                "temperature": temperature
            }
            if response_format:
                kwargs["response_format"] = response_format
            if max_tokens:
                kwargs["max_tokens"] = max_tokens

            # Call Groq API
            response = self.client.chat.completions.create(**kwargs)
            
            latency = time.time() - start_time
            content = response.choices[0].message.content
            
            # Extract Token Usage
            usage = response.usage
            prompt_tokens = usage.prompt_tokens if usage else 0
            completion_tokens = usage.completion_tokens if usage else 0
            total_tokens = usage.total_tokens if usage else 0

            # Calculate estimated USD cost using centralized MetricsCollector
            cost = MetricsCollector.calculate_llm_cost(model, prompt_tokens, completion_tokens)

            # Log Metrics
            metric = {
                "timestamp": time.time(),
                "capability": capability,
                "model": model,
                "latency_sec": round(latency, 3),
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": total_tokens,
                "estimated_cost_usd": round(cost, 6),
                "status": "success"
            }
            self.metrics_log.append(metric)
            
            logger.info(
                f"LLM request succeeded. Model: {model}. Latency: {metric['latency_sec']}s. Tokens: {total_tokens}. Cost: ${cost:.6f}"
            )

            return {
                "content": content,
                "model": model,
                "latency_sec": latency,
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": total_tokens,
                "estimated_cost_usd": cost,
                "success": True
            }

        except Exception as e:
            latency = time.time() - start_time
            logger.error(f"LLM call failed for model {model}: {e}")
            
            metric = {
                "timestamp": time.time(),
                "capability": capability,
                "model": model,
                "latency_sec": round(latency, 3),
                "status": "error",
                "error_message": str(e)
            }
            self.metrics_log.append(metric)
            
            return {
                "content": f"I encountered an error communicating with the model: {str(e)}",
                "model": model,
                "latency_sec": latency,
                "success": False,
                "error": str(e)
            }

    def get_metrics(self) -> List[Dict[str, Any]]:
        """Returns the in-memory log of executed requests."""
        return self.metrics_log
