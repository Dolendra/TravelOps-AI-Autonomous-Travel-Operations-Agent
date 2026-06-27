from backend.services.rag import RAGEngine
from backend.runtime.context.models import ContextFragment

class RAGProvider:
    def get_fragment(self, user_query: str) -> ContextFragment:
        """Retrieves matched FAQ context matching the user query via Jaccard similarity."""
        faq_context = RAGEngine.get_matching_context(user_query, top_k=1)
        compiled_content = faq_context if faq_context else "No matching FAQ knowledge base articles."
        explainability = (
            f"Frequently Asked Questions (FAQ) matched dynamically via Jaccard overlap: '{faq_context[:100]}...'"
            if faq_context else "No matching FAQ articles resolved in the knowledge base."
        )
        return ContextFragment(
            name="rag",
            content=compiled_content,
            priority=50,
            explainability=explainability
        )
