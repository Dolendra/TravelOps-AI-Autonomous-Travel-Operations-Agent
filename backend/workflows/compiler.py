import os
import re
import yaml
import logging
from typing import Dict, Any, List

logger = logging.getLogger("travelops.workflows.compiler")

class WorkflowCompiler:
    DEFINITIONS_DIR = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "workflows",
        "definitions"
    )

    @classmethod
    def load_definition(cls, workflow_name: str) -> Dict[str, Any]:
        """Loads a YAML workflow definition file from the definitions directory."""
        filename = f"{workflow_name}.yaml"
        filepath = os.path.join(cls.DEFINITIONS_DIR, filename)
        
        if not os.path.exists(filepath):
            logger.error(f"Workflow definition file not found: {filepath}")
            raise FileNotFoundError(f"Workflow definition template '{workflow_name}' does not exist.")

        try:
            with open(filepath, "r", encoding="utf-8") as f:
                definition = yaml.safe_load(f)
                return definition
        except Exception as e:
            logger.error(f"Failed to parse workflow YAML {filepath}: {e}")
            raise ValueError(f"Invalid YAML schema in workflow definition '{workflow_name}': {e}")

    @classmethod
    def compile_workflow(cls, workflow_name: str, variables: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Loads a workflow template and compiles it by resolving variables and validating the graph.
        Returns a list of task dicts ready to be saved as database task states.
        """
        definition = cls.load_definition(workflow_name)
        tasks = definition.get("tasks", [])
        
        if not tasks:
            raise ValueError(f"Workflow definition '{workflow_name}' has no tasks.")

        # 1. Resolve parameters recursively
        resolved_tasks = []
        for task in tasks:
            task_id = task.get("task_id")
            name = task.get("name")
            dependencies = task.get("dependencies", [])
            input_data = task.get("input_data", {})

            if not task_id or not name:
                raise ValueError("Each task must define a unique 'task_id' and 'name'.")

            resolved_input = cls._resolve_value(input_data, variables)
            
            resolved_tasks.append({
                "task_id": task_id,
                "name": name,
                "dependencies": dependencies,
                "input_data": resolved_input,
                "status": "PENDING"
            })

        # 2. Check for circular dependencies (DAG check)
        cls._validate_acyclic(resolved_tasks)

        logger.info(f"Successfully compiled workflow '{workflow_name}' with {len(resolved_tasks)} tasks.")
        return resolved_tasks

    @classmethod
    def _resolve_value(cls, val: Any, variables: Dict[str, Any]) -> Any:
        """Recursively replaces ${variable} placeholders with context values."""
        if isinstance(val, str):
            # Direct exact match replacement (preserves types like int/float/boolean)
            if val.startswith("${") and val.endswith("}"):
                var_name = val[2:-1]
                return variables.get(var_name, val)
            
            # Inline substring template interpolation
            def repl(match):
                var_name = match.group(1)
                return str(variables.get(var_name, match.group(0)))
            
            return re.sub(r"\$\{([^}]+)\}", repl, val)
        
        elif isinstance(val, dict):
            return {k: cls._resolve_value(v, variables) for k, v in val.items()}
        
        elif isinstance(val, list):
            return [cls._resolve_value(item, variables) for item in val]
        
        return val

    @classmethod
    def _validate_acyclic(cls, tasks: List[Dict[str, Any]]):
        """Ensures that task states represent a Directed Acyclic Graph (DAG)."""
        adj = {t["task_id"]: t.get("dependencies", []) for t in tasks}
        visited = {} # None = unvisited, 1 = visiting, 2 = visited
        
        def dfs(node):
            if visited.get(node) == 1:
                return True # Cycle detected!
            if visited.get(node) == 2:
                return False
            
            visited[node] = 1
            # Check dependencies. If dependency ID is missing from task list, raise warning/error or treat as fine
            for dep in adj.get(node, []):
                if dep not in adj:
                    # Ignore external dependencies that aren't parts of this specific compiled wave
                    continue
                if dfs(dep):
                    return True
            visited[node] = 2
            return False

        for task_id in adj:
            if dfs(task_id):
                logger.error(f"Workflow compilation failed due to circular dependency in '{task_id}'")
                raise ValueError(f"Circular dependency detected involving task ID '{task_id}'.")
