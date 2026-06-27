from typing import Any
from agents.memory.memory_agent import MemoryAgent
from backend.runtime.context.models import ContextFragment

class MemoryProvider:
    def __init__(self, memory_agent: MemoryAgent):
        self.memory_agent = memory_agent

    def get_fragment(self, session_id: str) -> ContextFragment:
        """Retrieves persistent user preferences profiles (Semantic Memory)."""
        prefs = self.memory_agent.retrieve_preferences(session_id)
        pref_list = []
        if prefs.get("operator_preference"):
            pref_list.append(f"- Preferred Operator: {prefs['operator_preference']}")
        if prefs.get("sorting_preference"):
            pref_list.append(f"- Preferred Sorting: {prefs['sorting_preference']}")
        if prefs.get("seat_preference"):
            pref_list.append(f"- Preferred Seat Type: {prefs['seat_preference']}")

        compiled_content = "Passenger Preferences Profile:\n" + "\n".join(pref_list) if pref_list else "No special preferences stored in memory."
        explainability = (
            f"Passenger preference profile dynamically loaded from semantic memory (Matched: {', '.join(pref_list)})."
            if pref_list else "No active traveler preferences matched in semantic memory."
        )
        return ContextFragment(
            name="memory",
            content=compiled_content,
            priority=70,
            explainability=explainability
        )
