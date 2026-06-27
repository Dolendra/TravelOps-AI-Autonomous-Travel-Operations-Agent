from typing import List, Tuple
from backend.runtime.context.models import ContextFragment

class TokenBudgetManager:
    # Class-level dynamic token budgets by agent types
    BUDGET_MAP = {
        "intent": 2500,
        "support": 6000,
        "planner": 12000,
        "reflection": 10000
    }

    def __init__(self, limit: int = 8000, agent: str = None):
        if agent and agent.lower() in self.BUDGET_MAP:
            self.limit = self.BUDGET_MAP[agent.lower()]
        else:
            self.limit = limit

    def fit_fragments(self, fragments: List[ContextFragment]) -> Tuple[List[ContextFragment], List[str]]:
        """
        Sorts context fragments by priority descending and fits them within the dynamically
        resolved token budget.
        """
        # Sort fragments by priority descending, then by name for determinism
        sorted_frags = sorted(fragments, key=lambda x: (-x.priority, x.name))
        
        accepted: List[ContextFragment] = []
        removed: List[str] = []
        current_tokens = 0
        
        for frag in sorted_frags:
            if current_tokens + frag.tokens <= self.limit:
                accepted.append(frag)
                current_tokens += frag.tokens
            else:
                remaining_tokens = self.limit - current_tokens
                # If there's enough space to be useful (e.g. > 50 tokens), truncate.
                # Otherwise, drop completely.
                if remaining_tokens > 50:
                    truncated_len = remaining_tokens * 4
                    truncated_content = frag.content[:truncated_len] + "\n[TRUNCATED DUE TO BUDGET]"
                    
                    # Create truncated fragment clone
                    truncated_frag = ContextFragment(
                        name=frag.name,
                        content=truncated_content,
                        priority=frag.priority,
                        explainability=f"{frag.explainability} (Truncated due to token budget limits)"
                    )
                    truncated_frag.tokens = remaining_tokens
                    
                    accepted.append(truncated_frag)
                    current_tokens += remaining_tokens
                    removed.append(f"{frag.name} (truncated)")
                else:
                    removed.append(frag.name)
                    
        return accepted, removed
