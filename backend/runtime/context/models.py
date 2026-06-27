import time
import hashlib
import json
from typing import List, Dict, Any, Optional

class ContextFragment:
    def __init__(self, name: str, content: str, priority: int, explainability: str):
        self.name = name
        self.content = content
        self.priority = priority
        self.explainability = explainability
        # Simple heuristic token estimation (1 token ~ 4 characters)
        self.tokens = max(1, len(content) // 4)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "content": self.content,
            "priority": self.priority,
            "tokens": self.tokens,
            "explainability": self.explainability
        }

class ContextBundle:
    def __init__(
        self,
        messages: List[Dict[str, str]],
        token_usage: int,
        sources: List[str],
        removed_sections: List[str],
        trace_id: str,
        version: str = "2.0.0",
        explainability: Optional[Dict[str, str]] = None,
        ttl_seconds: int = 300
    ):
        self.messages = messages
        self.token_usage = token_usage
        self.sources = sources
        self.removed_sections = removed_sections  # Keep for backwards compatibility
        self.removed_fragments = removed_sections  # Pruned sections
        self.trace_id = trace_id
        self.version = version
        self.explainability = explainability or {}
        
        self.created_at = time.time()
        self.expires_at = self.created_at + ttl_seconds
        self.token_count = token_usage
        
        # Calculate a secure SHA-256 hash of the compiled messages
        messages_json = json.dumps(messages, sort_keys=True)
        self.hash = hashlib.sha256(messages_json.encode('utf-8')).hexdigest()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "messages": self.messages,
            "token_usage": self.token_usage,
            "token_count": self.token_count,
            "sources": self.sources,
            "removed_sections": self.removed_sections,
            "removed_fragments": self.removed_fragments,
            "trace_id": self.trace_id,
            "version": self.version,
            "explainability": self.explainability,
            "created_at": self.created_at,
            "expires_at": self.expires_at,
            "hash": self.hash
        }
