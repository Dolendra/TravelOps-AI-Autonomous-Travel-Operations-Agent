import hashlib
import json
import time
from typing import List, Dict, Any, Optional
from backend.runtime.context.models import ContextBundle

class ContextCache:
    def __init__(self):
        self._cache = {}

    def _make_key(
        self,
        agent: str,
        session_id: str,
        user_query: str,
        chat_history: Optional[List[Dict[str, str]]] = None
    ) -> str:
        # Standardize chat history to a stable string for hashing
        history_str = json.dumps(chat_history or [], sort_keys=True)
        key_source = f"{agent}:{session_id}:{user_query}:{history_str}"
        return hashlib.sha256(key_source.encode('utf-8')).hexdigest()

    def get(
        self,
        agent: str,
        session_id: str,
        user_query: str,
        chat_history: Optional[List[Dict[str, str]]] = None
    ) -> Optional[ContextBundle]:
        """Retrieves a cached ContextBundle if it exists and has not expired."""
        key = self._make_key(agent, session_id, user_query, chat_history)
        bundle = self._cache.get(key)
        if bundle:
            # Check expiration TTL
            if time.time() > bundle.expires_at:
                del self._cache[key]
                return None
            return bundle
        return None

    def set(
        self,
        agent: str,
        session_id: str,
        user_query: str,
        chat_history: Optional[List[Dict[str, str]]],
        bundle: ContextBundle
    ) -> None:
        """Saves a ContextBundle to the cache."""
        key = self._make_key(agent, session_id, user_query, chat_history)
        self._cache[key] = bundle

    def clear(self) -> None:
        """Clears the cache."""
        self._cache.clear()
