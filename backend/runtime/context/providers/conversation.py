from typing import List, Dict, Any
from backend.runtime.context.models import ContextFragment

class ConversationProvider:
    def get_history_fragment(self, chat_history: List[Dict[str, str]]) -> ContextFragment:
        """Retrieves formatted working memory chat dialogue history logs."""
        content_lines = []
        # Format chat history (excluding the active query turn)
        for msg in chat_history:
            sender = msg.get("sender", "User")
            text = msg.get("message", "")
            content_lines.append(f"{sender}: {text}")

        compiled_content = "\n".join(content_lines) if content_lines else "No previous dialog history."
        explainability = (
            f"Working memory logs of the previous {len(chat_history)} conversation turns for dialog continuity."
        )
        return ContextFragment(
            name="history",
            content=compiled_content,
            priority=40,
            explainability=explainability
        )

    def get_query_fragment(self, user_query: str) -> ContextFragment:
        """Retrieves the active user query instruction input."""
        return ContextFragment(
            name="query",
            content=f"Active User Query: {user_query}",
            priority=80,
            explainability=f"The current user question or directive requiring action: '{user_query}'"
        )
