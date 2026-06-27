import os
import logging
from typing import Dict, Any

logger = logging.getLogger("travelops.services.prompt_loader")

class PromptLoader:
    def __init__(self, prompts_dir: str = None):
        if prompts_dir is None:
            # Root directory is two levels up from backend/services/
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            prompts_dir = os.path.join(base_dir, "prompts")
        self.prompts_dir = prompts_dir
        logger.info(f"Initialized PromptLoader with directory: {self.prompts_dir}")

    def load_prompt(self, name: str, variables: Dict[str, Any] = None) -> str:
        """
        Loads a prompt markdown template by name and replaces double curly-bracket placeholders.
        Example: {{current_date}} -> '2026-06-27'
        """
        # Strip potential file extension if provided in name
        if name.endswith(".md"):
            name = name[:-3]
            
        file_path = os.path.join(self.prompts_dir, f"{name}.md")
        if not os.path.exists(file_path):
            logger.error(f"Prompt template file not found: {file_path}")
            raise FileNotFoundError(f"Prompt template file not found: {file_path}")

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                template = f.read()
        except Exception as e:
            logger.error(f"Failed to read prompt file {file_path}: {e}")
            raise

        if variables:
            for key, value in variables.items():
                placeholder = f"{{{{{key}}}}}"
                template = template.replace(placeholder, str(value))
                
        return template
