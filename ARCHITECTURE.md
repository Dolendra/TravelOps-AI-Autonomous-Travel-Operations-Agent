# System Architecture — TravelOps AI

TravelOps AI is structured as a **Multi-Agent Orchestration Platform** with a decoupled travel domain layer. It translates natural language operational instructions into robust, fault-tolerant execution pipelines.

---

## 🏗️ Architectural Blueprint

```
                      +-----------------------------+
                      |   Vite React Front-End      |
                      |  (Interactive Studio Portal)|
                      +--------------+--------------+
                                     |  REST
                                     v
                      +-----------------------------+
                      |      FastAPI Gateway        |
                      +--------------+--------------+
                                     |
                                     v
  +----------------------------------+----------------------------------+
  |                                                                     |
  v                                                                     v
+-----------------------------+                       +-----------------------------+
|    Agent Runtime Engine     |                       |  Workflow Orchestrator DSL  |
|  (Dynamic registry, tags)   |                       |  (Declarative compilation)  |
+--------------+--------------+                       +--------------+--------------+
               |                                                     |
               | Resolves                                            | Runs Tasks
               +----------------------> [Tool Registry] <------------+
                                             |
                                             v
                              +-----------------------------+
                              |   Provider Integration      |
                              |  (Abstract Provider SDK)    |
                              +--------------+--------------+
                                             |
                                             v
                              +-----------------------------+
                              |   Provider Health Router    |
                              | (Latency profiling, retry)  |
                              +--------+-----------+--------+
                                       |           |
                                       v           v
                                   [VRL Bus]   [IntrCity] (Backup)
```

---

## 🎛️ Key Subsystems

### 1. Declarative Workflow DSL & Executor
- **Compiler**: Resolves template variables (e.g. origins, seat numbers, cards) recursively and compiles them into a Directed Acyclic Graph (DAG) using a declarative YAML syntax.
- **Executor**: Executes tasks in concurrent waves based on topological dependencies.
- **Saga Compensation**: Automatically schedules reverse compensating tasks (e.g. `release_seat` or `refund_payment`) to cleanly rollback active bookings if any downstream task fails.

### 2. Provider Integration Layer & Health Router
- **Provider SDK**: Exposes a unified interface (`BaseTravelProvider`) to abstract external transit vendors.
- **Health Router**: Maintains a sliding-window record of API latencies and consecutive failures. If a provider's failure count exceeds `3`, the router marks it as `UNHEALTHY` and automatically redirects traffic to registered backup adapters.

### 3. Agent Runtime Engine
- Decouples reasoning and operational roles into specialized agents (e.g. `IntentAgent`, `PlannerAgent`, `JourneyMonitor`, `RecoveryAgent`, `ReflectionAgent`).
- Agents are registered dynamically based on capability tags, allowing the orchestrator to route goals on the fly without importing hardcoded files.

### 4. Context Caching & Budgets
- **Leased Context Cache**: Stores LLM responses under configurable TTL leases.
- **Token Budgets**: Implements a sliding token expenditure cap. If execution queries exceed the token threshold, the circuit trips to block API costs.

---

## 💾 Database Schema

The platform relies on an SQLite instance (`travelops.db`) containing the following core entities:
* **`sessions`**: Active customer operator contexts.
* **`conversations`**: Chat messages history.
* **`task_states`**: Pipeline task execution outputs, dependency arrays, and latencies.
* **`workflow_states`**: Session milestone status markers (`OPTIONS_FOUND`, `BOOKED`, `RECOVERED`).
* **`bookings`**: Seat coordinates, passenger details, PNR identifiers, and billing amounts.
* **`audit_logs`**: Cognitive reasoning logging summaries for AI studio timeline feeds.
* **`event_store`**: Persistent event streams (`BusCancelled`, `DisruptionDetected`) for event-driven recovery.
