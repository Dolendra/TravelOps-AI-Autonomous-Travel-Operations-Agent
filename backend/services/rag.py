import os
import re
import logging
from typing import List, Dict, Any, Tuple

logger = logging.getLogger("travelops.services.rag")

class RAGEngine:
    _segments: List[str] = []

    @classmethod
    def load_knowledge_base(cls, filepath: str = None) -> None:
        """Loads and splits the FAQ markdown document into segments."""
        if not filepath:
            filepath = r"d:\TravelOps AI – Autonomous Travel Operations Agent\knowledge_base\faq.md"
        
        if not os.path.exists(filepath):
            logger.warning(f"RAGEngine: FAQ file not found at {filepath}. Attempting relative lookup.")
            # Fallback to local workspace relative lookup if run in container or test env
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            filepath = os.path.join(base_dir, "knowledge_base", "faq.md")

        if not os.path.exists(filepath):
            logger.error(f"RAGEngine: FAQ file path resolved to {filepath} but does not exist.")
            cls._segments = []
            return
            
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()
                
            # Split document by headers or double newlines to isolate paragraphs
            raw_chunks = re.split(r'\n##+ ', content)
            cls._segments = []
            for chunk in raw_chunks:
                chunk_str = chunk.strip()
                if chunk_str:
                    cls._segments.append(chunk_str)
            logger.info(f"RAGEngine: Loaded {len(cls._segments)} segments from FAQ document.")
        except Exception as e:
            logger.error(f"RAGEngine: Failed to load FAQ document: {e}")
            cls._segments = []

    @classmethod
    def get_matching_context(cls, query: str, top_k: int = 1) -> str:
        """Finds the top-K segments in the FAQ matching the query by Jaccard similarity."""
        if not cls._segments:
            cls.load_knowledge_base()
            
        if not cls._segments:
            return ""
            
        query_words = set(re.findall(r'\w+', query.lower()))
        if not query_words:
            return ""
            
        scored_segments: List[Tuple[float, str]] = []
        for segment in cls._segments:
            seg_words = set(re.findall(r'\w+', segment.lower()))
            overlap = query_words.intersection(seg_words)
            # Jaccard Similarity: intersection size divided by union size
            union = query_words.union(seg_words)
            score = len(overlap) / len(union) if union else 0.0
            scored_segments.append((score, segment))
            
        # Sort descending by score
        scored_segments.sort(key=lambda x: x[0], reverse=True)
        top_matches = [seg for score, seg in scored_segments[:top_k] if score > 0.0]
        
        return "\n\n".join(top_matches)
