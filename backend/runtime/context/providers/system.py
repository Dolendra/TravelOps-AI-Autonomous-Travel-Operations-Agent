from typing import Any
from backend.services.prompt_loader import PromptLoader
from backend.runtime.context.models import ContextFragment

class SystemProvider:
    def __init__(self, prompt_loader: PromptLoader):
        self.prompt_loader = prompt_loader

    def get_fragment(self, agent: str) -> ContextFragment:
        """Retrieves system prompt directive instructions for the specified agent."""
        system_content = self.prompt_loader.load_prompt(agent, {})
        return ContextFragment(
            name="system",
            content=system_content,
            priority=100,
            explainability=f"Required rules and operational directives for the '{agent}' agent."
        )
