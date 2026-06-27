import json
import logging
from datetime import datetime
from typing import Dict, Any

from backend.services.llm import ModelRouter
from backend.services.prompt_loader import PromptLoader

logger = logging.getLogger("travelops.agents.intent")

class IntentAgent:
    def __init__(self, model_router: ModelRouter, prompt_loader: PromptLoader):
        self.model_router = model_router
        self.prompt_loader = prompt_loader

    def parse_intent(self, message: str) -> Dict[str, Any]:
        """
        Parses user message to determine primary intent and extract entities.
        Uses fast model capability with JSON formatting.
        """
        now = datetime.now()
        curr_date = now.strftime("%Y-%m-%d")
        curr_weekday = now.strftime("%A")

        try:
            intent_system_prompt = self.prompt_loader.load_prompt("intent", {
                "current_date": curr_date,
                "current_weekday": curr_weekday
            })
            messages = [
                {"role": "system", "content": intent_system_prompt},
                {"role": "user", "content": message}
            ]

            # Trigger LLM generation routing
            response = self.model_router.generate(
                messages=messages,
                capability="fast",
                response_format={"type": "json_object"}
            )

            if response["success"]:
                parsed = json.loads(response["content"])
                logger.info(f"Successfully parsed intent via LLM: {parsed.get('primary_intent')}")
                return parsed
            else:
                logger.error(f"Intent LLM call failed: {response.get('error')}. Applying fallback rule-based parser...")
                return self._fallback_parse(message)
        except Exception as e:
            logger.error(f"Failed parsing LLM intent response: {e}. Applying fallback rule-based parser...")
            return self._fallback_parse(message)

    def _fallback_parse(self, message: str) -> Dict[str, Any]:
        """Rule-based intent parser to use when LLM API keys are invalid or expired."""
        msg_lower = message.lower()
        intent = "general_chat"
        entities = {}

        # 1. Parse Intent Heuristics
        if any(w in msg_lower for w in ["cancel", "refund"]):
            intent = "cancel_bus"
        elif any(w in msg_lower for w in ["time", "status", "delay", "on time", "monitor"]):
            intent = "monitor_journey"
        elif any(w in msg_lower for w in ["confirm", "pay", "payment"]):
            intent = "confirm_booking"
        elif any(w in msg_lower for w in ["search", "find", "sleeper", "buses", "go to"]) or ("bus" in msg_lower and "time" not in msg_lower):
            intent = "search_bus"
        
        # 2. Extract Entities via Heuristics
        import re
        
        # Match cities
        for city in ["Bangalore", "Goa", "Chennai", "Mumbai", "Hyderabad"]:
            if city.lower() in msg_lower:
                if "origin" not in entities:
                    # heuristic: first city is origin if before "to"
                    if "to" in msg_lower and msg_lower.find(city.lower()) < msg_lower.find("to"):
                        entities["origin"] = city
                    else:
                        entities["origin"] = city
                else:
                    entities["destination"] = city

        # Special adjustments for directionality
        if "origin" in entities and "destination" not in entities:
            if "chennai" in msg_lower and entities["origin"] != "Chennai":
                entities["destination"] = "Chennai"
        if "origin" not in entities and "destination" in entities:
            if "bangalore" in msg_lower and entities["destination"] != "Bangalore":
                entities["origin"] = "Bangalore"

        # Match dates
        date_match = re.search(r"\b\d{4}-\d{2}-\d{2}\b", message)
        if date_match:
            entities["travel_date"] = date_match.group(0)

        # Match PNR
        pnr_match = re.search(r"\b[A-Z0-9]{5,6}\b", message)
        if pnr_match:
            entities["pnr"] = pnr_match.group(0)

        # Match Booking ID
        booking_id_match = re.search(r"\b\d+\b", message)
        if booking_id_match and intent != "search_bus":
            entities["booking_id"] = int(booking_id_match.group(0))

        return {
            "primary_intent": intent,
            "entities": entities,
            "confidence": 0.7
        }

