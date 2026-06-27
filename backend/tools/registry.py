import time
import json
import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, Type, Callable, List
from backend.database.db import SessionLocal
from backend.database.models import AuditLogModel

logger = logging.getLogger("travelops.tools.registry")

class BaseTool(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        """Unique identifier for the tool."""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """Detailed description of what the tool does and its parameters."""
        pass

    @abstractmethod
    def execute(self, session_id: str, **kwargs) -> Dict[str, Any]:
        """Core execution logic of the tool."""
        pass


class ToolRegistry:
    _registry: Dict[str, BaseTool] = {}

    @classmethod
    def register(cls, tool_instance: BaseTool):
        """Registers a tool instance."""
        cls._registry[tool_instance.name] = tool_instance
        logger.info(f"Registered tool: {tool_instance.name}")

    @classmethod
    def get_tool(cls, name: str) -> BaseTool:
        """Retrieves a registered tool."""
        if name not in cls._registry:
            raise KeyError(f"Tool '{name}' is not registered.")
        return cls._registry[name]

    @classmethod
    def list_tools(cls) -> List[Dict[str, str]]:
        """Returns descriptions of all registered tools."""
        return [
            {"name": name, "description": tool.description}
            for name, tool in cls._registry.items()
        ]

    @classmethod
    def execute_tool(cls, name: str, session_id: str, **kwargs) -> Dict[str, Any]:
        """
        Executes the registered tool and records an entry in the Audit Logs database table.
        """
        try:
            tool = cls.get_tool(name)
        except KeyError as e:
            return {"success": False, "error": str(e)}

        start_time = time.time()
        logger.info(f"Executing tool '{name}' for session: {session_id} with args: {kwargs}")

        # Audit log initial execution state
        db = SessionLocal()
        audit_entry = AuditLogModel(
            session_id=session_id,
            agent_name="ToolRegistry",
            action=f"tool_call:{name}",
            reasoning_summary=f"Executing tool {name} with inputs."
        )
        audit_entry.set_payload({"inputs": kwargs})
        db.add(audit_entry)
        db.commit()
        db.refresh(audit_entry)

        try:
            result = tool.execute(session_id, **kwargs)
            latency = time.time() - start_time
            
            # Update audit log with output and success state
            audit_entry.reasoning_summary = f"Tool {name} completed successfully in {round(latency, 3)}s."
            audit_entry.set_payload({
                "inputs": kwargs,
                "outputs": result,
                "latency_sec": round(latency, 3),
                "success": True
            })
            db.commit()
            
            return result
        except Exception as e:
            latency = time.time() - start_time
            logger.error(f"Error executing tool '{name}': {e}")
            
            # Update audit log with error details
            audit_entry.reasoning_summary = f"Tool {name} failed in {round(latency, 3)}s."
            audit_entry.set_payload({
                "inputs": kwargs,
                "error": str(e),
                "latency_sec": round(latency, 3),
                "success": False
            })
            db.commit()
            
            return {"success": False, "error": str(e)}
        finally:
            db.close()


def register_tool(cls: Type[BaseTool]):
    """Decorator to register a tool class directly."""
    instance = cls()
    ToolRegistry.register(instance)
    return cls
