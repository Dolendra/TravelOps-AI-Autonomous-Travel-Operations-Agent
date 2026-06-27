# Agent Runtime & Registries

The **Agent Runtime** is the control layer that routes cognitive execution requests to the appropriate agent instance. It registers agents with metadata defining their version numbers, target capabilities, and current health statuses.

---

## 🏗️ The Agent Registry Core

Instead of direct Python class instantiation across route handlers, agents register globally in the `AgentRuntime`:

```
User Intent "search_bus"
         │
         ▼
 ┌───────────────┐
 │ Agent Runtime │
 └───────┬───────┘
         │
         ├─► Resolves Capability: ["search"]
         ├─► Verifies Health: "HEALTHY"
         ├─► Checks Version Constraint: ">=2.0.0"
         │
         ▼
 ┌───────────────┐
 │ SearchAgent   │
 └───────────────┘
```

Each registered entry is wrapped with an `AgentMetadata` tracking object:
* **Name**: The identifier of the agent.
* **Version**: Semantic version string (e.g. `2.0.0`).
* **Capabilities**: List of capability tags (e.g. `["plan", "compile"]`, `["search"]`).
* **Health Status**: Current operational health (`HEALTHY`, `DEGRADED`, `UNHEALTHY`).

---

## 🚦 Health Checks & Safety Circuit Breakers

The runtime acts as a **circuit breaker** protecting system execution:
1. **Failure Stamping**: When an agent execution fails (e.g. due to rate limits or API authentication issues), the runtime catches the exception and calls `record_failure()`.
2. **Status Degradation**:
   - On the first failure, status transitions to `DEGRADED`.
   - If consecutive failures reach the threshold (default: `3`), the state transitions to `UNHEALTHY`.
3. **Execution Blocking**: When an agent's status is `UNHEALTHY`, subsequent runtime calls to `execute(capability, ...)` will fail fast and raise `AgentUnhealthyError` without making expensive API calls.
4. **Auto-Recovery**: When a manual health check or a retry call returns successfully, the agent's failure count is reset to `0` and status is restored to `HEALTHY`.

---

## 📂 Active Agent Inventory

The repository contains 6 core agents registered with the runtime:

1. **IntentAgent**: Parses user sentences to identify the target goal and extract key parameters. Exposes capability `["intent"]`.
2. **PlannerAgent**: Compiles declarative task dependency graphs. Exposes capability `["plan", "compile"]`.
3. **MemoryAgent**: Reads and writes short-term, episodic, and preference state records. Exposes capability `["memory"]`.
4. **JourneyMonitor**: Listens to live vehicle streams to determine delays and issues. Exposes capability `["monitor"]`.
5. **RecoveryAgent**: Compiles rebooking options and resolves cancellations. Exposes capability `["recovery"]`.
6. **ReflectionAgent**: Reviews error reports and proposes edits to repair failed workflow nodes. Exposes capability `["reflection"]`.
