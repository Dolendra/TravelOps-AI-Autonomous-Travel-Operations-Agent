import json
import logging
from typing import Dict, Any

from backend.services.llm import ModelRouter
from backend.services.prompt_loader import PromptLoader

logger = logging.getLogger("travelops.agents.planner")

class PlannerAgent:
    def __init__(self, model_router: ModelRouter, prompt_loader: PromptLoader):
        self.model_router = model_router
        self.prompt_loader = prompt_loader

    def generate_plan(self, origin: str, destination: str, travel_date: str, preferences: str = "highest_rating") -> Dict[str, Any]:
        """
        Queries the reasoning model to build a Task Dependency Graph for a trip.
        """
        try:
            planner_prompt = self.prompt_loader.load_prompt("planner", {})
            user_instruction = (
                f"Create a task graph for travel from {origin} to {destination} on {travel_date}. "
                f"Preference: {preferences}."
            )
            messages = [
                {"role": "system", "content": planner_prompt},
                {"role": "user", "content": user_instruction}
            ]

            response = self.model_router.generate(
                messages=messages,
                capability="reasoning",
                response_format={"type": "json_object"}
            )

            if response["success"]:
                graph = json.loads(response["content"])
                logger.info(f"Successfully generated task graph plan via reasoning model: {len(graph.get('tasks', []))} tasks.")
                return graph
            else:
                logger.error(f"Planner Model call failed: {response.get('error')}. Returning fallback linear plan...")
                return self._fallback_plan(origin, destination, travel_date, preferences)
        except Exception as e:
            logger.error(f"Failed generating task graph plan: {e}. Returning fallback linear plan...")
            return self._fallback_plan(origin, destination, travel_date, preferences)

    def _fallback_plan(self, origin: str, destination: str, travel_date: str, preferences: str) -> Dict[str, Any]:
        """Provides a standard search-then-recommend task graph when LLM planning is unavailable."""
        return {
            "tasks": [
                {
                    "id": "task_1",
                    "name": "search_buses",
                    "depend_on_ids": [],
                    "status": "PENDING",
                    "input_parameters": {
                        "origin": origin,
                        "destination": destination,
                        "travel_date": travel_date
                    }
                },
                {
                    "id": "task_2",
                    "name": "recommend_options",
                    "depend_on_ids": ["task_1"],
                    "status": "PENDING",
                    "input_parameters": {
                        "preferences": preferences
                    }
                }
            ]
        }

