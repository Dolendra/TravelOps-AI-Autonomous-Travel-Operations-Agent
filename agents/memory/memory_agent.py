import json
import logging
from typing import Dict, Any

from backend.services.llm import ModelRouter
from backend.services.prompt_loader import PromptLoader
from backend.database.db import SessionLocal
from backend.database.models import CacheModel

logger = logging.getLogger("travelops.agents.memory")

class MemoryAgent:
    def __init__(self, model_router: ModelRouter, prompt_loader: PromptLoader):
        self.model_router = model_router
        self.prompt_loader = prompt_loader

    def save_preference(self, session_id: str, preference_text: str) -> Dict[str, Any]:
        """
        Parses and saves user preferences into the database cache.
        """
        # 1. Parse preferences (LLM with fallback to heuristic)
        parsed_prefs = self.parse_preference_text(preference_text)
        
        # 2. Save/merge with existing preferences for this session in SQLite CacheModel
        db = SessionLocal()
        try:
            cache_key = f"memory:preferences:{session_id}"
            cache_entry = db.query(CacheModel).filter(CacheModel.key == cache_key).first()
            
            existing_prefs = {}
            if cache_entry:
                try:
                    existing_prefs = json.loads(cache_entry.value)
                except Exception:
                    pass
            
            # Merge: update only non-null values
            for k, v in parsed_prefs.items():
                if v is not None:
                    existing_prefs[k] = v
                    
            merged_json = json.dumps(existing_prefs)
            
            if cache_entry:
                cache_entry.value = merged_json
            else:
                new_cache = CacheModel(key=cache_key, value=merged_json)
                db.add(new_cache)
                
            db.commit()
            logger.info(f"Saved memory preferences for session {session_id}: {merged_json}")
            return existing_prefs
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to save preferences to database cache: {e}")
            return parsed_prefs
        finally:
            db.close()

    def retrieve_preferences(self, session_id: str) -> Dict[str, Any]:
        """
        Pulls profile rules/preferences from database cache.
        """
        db = SessionLocal()
        try:
            cache_key = f"memory:preferences:{session_id}"
            cache_entry = db.query(CacheModel).filter(CacheModel.key == cache_key).first()
            if cache_entry:
                return json.loads(cache_entry.value)
        except Exception as e:
            logger.error(f"Failed to retrieve memory preferences: {e}")
        finally:
            db.close()
        return {}

    def parse_preference_text(self, preference_text: str) -> Dict[str, Any]:
        """
        Extracts preferences using LLM, with local heuristic fallback.
        """
        # Initialize default structure
        result = {
            "operator_preference": None,
            "sorting_preference": None,
            "seat_preference": None,
            "reasoning_summary": "Extracted using fallback heuristics."
        }
        
        if not self.model_router.api_key:
            return self._heuristic_fallback(preference_text, result)
            
        try:
            prompt = self.prompt_loader.load_prompt("memory", {})
            messages = [
                {"role": "system", "content": prompt},
                {"role": "user", "content": preference_text}
            ]
            response = self.model_router.generate(
                messages=messages,
                capability="fast",
                response_format={"type": "json_object"}
            )
            if response["success"]:
                parsed = json.loads(response["content"])
                logger.info(f"MemoryAgent parsed preferences successfully via LLM: {parsed}")
                return parsed
            else:
                logger.warning(f"Memory Agent LLM call failed: {response.get('error')}. Using heuristic fallback.")
                return self._heuristic_fallback(preference_text, result)
        except Exception as e:
            logger.error(f"MemoryAgent error during LLM parse: {e}. Using heuristic fallback.")
            return self._heuristic_fallback(preference_text, result)

    def _heuristic_fallback(self, text: str, defaults: Dict[str, Any]) -> Dict[str, Any]:
        text_lower = text.lower()
        
        # Sort preferences
        if "cheapest" in text_lower or "cheap" in text_lower or "budget" in text_lower or "low fare" in text_lower:
            defaults["sorting_preference"] = "cheapest"
        elif "rating" in text_lower or "best" in text_lower or "top" in text_lower:
            defaults["sorting_preference"] = "highest_rating"
            
        # Operator preferences
        operators = ["vrl", "ksrtc", "srs", "orange", "national", "intracity"]
        for op in operators:
            if op in text_lower:
                defaults["operator_preference"] = op.upper()
                break
                
        # Seat preferences
        seats = ["window", "aisle", "sleeper", "seater"]
        for st in seats:
            if st in text_lower:
                defaults["seat_preference"] = st
                break
                
        return defaults
