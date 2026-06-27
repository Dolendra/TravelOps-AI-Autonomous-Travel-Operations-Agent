import logging
import time
from typing import Dict, Any, List, Optional, Type, Callable

logger = logging.getLogger("travelops.runtime.agent")

class AgentExecutionError(Exception):
    """Raised when agent execution fails."""
    pass

class AgentUnhealthyError(Exception):
    """Raised when attempting to execute an unhealthy/disabled agent."""
    pass

class AgentMetadata:
    def __init__(self, name: str, version: str, capabilities: List[str], max_consecutive_failures: int = 3):
        self.name = name
        self.version = version
        self.capabilities = capabilities
        self.health = "HEALTHY"  # HEALTHY, DEGRADED, UNHEALTHY
        self.consecutive_failures = 0
        self.max_consecutive_failures = max_consecutive_failures
        self.last_health_check = time.time()
        self.latency_history: List[float] = []

    def record_success(self, latency: float):
        self.consecutive_failures = 0
        self.latency_history.append(latency)
        if len(self.latency_history) > 10:
            self.latency_history.pop(0)
        
        # Recover health status
        if self.health != "HEALTHY":
            logger.info(f"Agent '{self.name}' recovered to HEALTHY status.")
            self.health = "HEALTHY"

    def record_failure(self):
        self.consecutive_failures += 1
        if self.consecutive_failures >= self.max_consecutive_failures:
            logger.critical(f"Agent '{self.name}' has failed {self.consecutive_failures} times. Tripping health status to UNHEALTHY.")
            self.health = "UNHEALTHY"
        elif self.health == "HEALTHY":
            logger.warning(f"Agent '{self.name}' experienced a failure. Status degraded.")
            self.health = "DEGRADED"

    def get_avg_latency(self) -> float:
        if not self.latency_history:
            return 0.0
        return sum(self.latency_history) / len(self.latency_history)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "capabilities": self.capabilities,
            "health": self.health,
            "consecutive_failures": self.consecutive_failures,
            "avg_latency": self.get_avg_latency()
        }


class AgentRuntime:
    def __init__(self, model_router: Any = None, prompt_loader: Any = None):
        self.model_router = model_router
        self.prompt_loader = prompt_loader
        self.registry: Dict[str, Dict[str, Any]] = {}  # name -> {"metadata": AgentMetadata, "instance": Any}

    def register_agent(self, name: str, version: str, capabilities: List[str], instance: Any, max_consecutive_failures: int = 3):
        """
        Registers a live agent instance with capability mapping, health checking, and version rules.
        """
        metadata = AgentMetadata(name, version, capabilities, max_consecutive_failures)
        self.registry[name.lower()] = {
            "metadata": metadata,
            "instance": instance
        }
        logger.info(f"Agent '{name}' v{version} registered with capabilities: {capabilities}")

    def get_agent_by_capability(self, capability: str, version: Optional[str] = None) -> Any:
        """
        Resolves and returns a healthy agent instance by matching capabilities and version constraint.
        """
        for entry in self.registry.values():
            metadata: AgentMetadata = entry["metadata"]
            if capability.lower() in [c.lower() for c in metadata.capabilities]:
                # Version filtering if requested
                if version and metadata.version != version:
                    continue
                
                # Check health status
                if metadata.health == "UNHEALTHY":
                    logger.warning(f"Resolved agent '{metadata.name}' is marked UNHEALTHY.")
                    continue
                
                return entry["instance"]
                
        # Fallback to degraded agents if no healthy one exists
        for entry in self.registry.values():
            metadata: AgentMetadata = entry["metadata"]
            if capability.lower() in [c.lower() for c in metadata.capabilities]:
                if version and metadata.version != version:
                    continue
                return entry["instance"]

        raise ValueError(f"No agent registered for capability '{capability}'" + (f" with version '{version}'" if version else ""))

    def execute(self, capability: str, method_name: str, *args, **kwargs) -> Any:
        """
        Resolves agent capability, runs sanity health checks, executes method, and profiles metric logs.
        """
        for entry in self.registry.values():
            metadata: AgentMetadata = entry["metadata"]
            if capability.lower() in [c.lower() for c in metadata.capabilities]:
                if metadata.health == "UNHEALTHY":
                    raise AgentUnhealthyError(f"Agent '{metadata.name}' is currently disabled/unhealthy due to persistent failures.")
                
                instance = entry["instance"]
                if not hasattr(instance, method_name):
                    raise AttributeError(f"Agent '{metadata.name}' does not implement method '{method_name}'")
                
                method: Callable = getattr(instance, method_name)
                start_time = time.time()
                try:
                    logger.info(f"AgentRuntime routing execution to '{metadata.name}' for action '{method_name}'...")
                    result = method(*args, **kwargs)
                    latency = time.time() - start_time
                    metadata.record_success(latency)
                    return result
                except Exception as e:
                    metadata.record_failure()
                    logger.error(f"Error executing agent '{metadata.name}': {e}")
                    raise AgentExecutionError(f"Agent execution failed: {e}") from e

        raise ValueError(f"No active agent found registered with capability: {capability}")

    def get_health_report(self) -> List[Dict[str, Any]]:
        """
        Returns list of health statuses for all registered agents.
        """
        return [entry["metadata"].to_dict() for entry in self.registry.values()]
