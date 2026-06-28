# ADR 0005: Decoupled Dynamic Agent Runtime

## Status
Accepted

## Context
A multi-agent system relies on specialized models performing parsing, planning, monitoring, and error reflections. Statically importing and routing tasks to hardcoded agent handlers leads to complex imports and hampers modularity.

## Decision
We implemented a **Decoupled Dynamic Agent Runtime**:
1. Decoupled agents into standalone classes (e.g. `IntentAgent`, `PlannerAgent`, `MemoryAgent`, `ReflectionAgent`).
2. Implemented an `@register_agent` decorator that maps agents by capability tags (e.g. `["plan"]`, `["reflection"]`) and version tags on startup.
3. The platform registry resolves agent capabilities dynamically based on the requested workflow node type, executing the preferred agent without static file coupling.

## Alternatives Considered
- **Static Orchestration Handler**: A single large class that matches task names and imports the correct agent files. *Rejected* due to tight coupling and lack of extensibility.
- **Autogen / LangChain Frameworks**: Using heavy third-party framework wrappers. *Rejected* to maintain absolute control over system prompt assembly, prompt templates loading, and caching logic.

## Consequences
- **Positive**: High extensibility. Easy to register new agents (e.g., `FlightAgent`, `HotelAgent`) simply by adding the class and tagging its capabilities.
- **Negative**: Dynamic loading makes runtime tracing slightly more complex since the execution path is resolved at runtime.
