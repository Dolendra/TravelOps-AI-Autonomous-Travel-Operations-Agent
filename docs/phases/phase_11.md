# Phase 11: Provider Integration Layer & Agent Runtime (v2.1 Production Release)

This phase establishes the provider integration and registry routing enhancements for **TravelOps AI v2.1**. It introduces a decoupled Provider Layer to abstract transit operator queries from tool logic, implements provider health tracking with automated failover, and refactors all cognitive and operational agents to resolve dynamically via the central `AgentRuntime`.

---

## 1. Provider Integration Layer (`backend/providers/`)

To prevent direct coupling of workflow tools to internal database models, we established a **Provider Abstraction Layer** which standardizes the schema signatures of external transit systems:

```
SearchBusTool ──► ProviderRouter ──► MockBusProvider   ──► Local DB
                                 └──► BackupBusProvider ──► Failover System
```

### Decoupled Code Layout
* [base.py](file:///d:/TravelOps%20AI%20%E2%80%93%20Autonomous%20Travel%20Operations%20Agent/backend/providers/base.py): Declares the `BaseTravelProvider` interface covering:
  - `search_buses(origin, destination, travel_date)`
  - `hold_seat(bus_id, seat_number, passenger_name, passenger_email, session_id)`
  - `confirm_booking(booking_id)`
  - `cancel_booking(booking_id, session_id)`
* [mock_bus.py](file:///d:/TravelOps%20AI%20%E2%80%93%20Autonomous%20Travel%20Operations%20Agent/backend/providers/mock_bus.py): Implements the primary provider, mapping logic to database models (SQLAlchemy ORM).
* [backup_bus.py](file:///d:/TravelOps%20AI%20%E2%80%93%20Autonomous%20Travel%20Operations%20Agent/backend/providers/backup_bus.py): Implements a backup provider that mirrors queries but prefixes operator names with `"Backup: "` to verify routing changes.
* [router.py](file:///d:/TravelOps%20AI%20%E2%80%93%20Autonomous%20Travel%20Operations%20Agent/backend/providers/router.py): Governs provider registrations and coordinates health states.

---

## 2. Health Monitoring & Provider Failover

The `ProviderRouter` maintains a thread-safe `ProviderHealth` profile for each provider instance:
* **Metric Tracking**: Success counts, latencies (averages derived from a sliding window of the last 20 calls), and consecutive failures.
* **Failover Policy**: If a provider fails to process a request (raises an exception), the router:
  1. Staps a failure count on the provider's health card.
  2. Traverses the registry for alternative healthy providers and immediately retries the operation.
  3. Trips the preferred provider state to `UNHEALTHY` if consecutive failures reach the threshold (default: `3`), bypassing it on all future requests.
* **Audit Trail logs**: Automatically writes provider selection details, latencies, and success states to the `AuditLogModel` under the `system_provider` session identifier.

---

## 3. Dynamic Agent Registry Routing

We registered all agents globally with `AgentRuntime` on startup in [main.py](file:///d:/TravelOps%20AI%20%E2%80%93%20Autonomous%20Travel%20Operations%20Agent/backend/api/main.py):

```python
agent_runtime = AgentRuntime(model_router, prompt_loader)
agent_runtime.register_agent("IntentAgent", "2.0.0", ["intent"], IntentAgent(model_router, prompt_loader))
agent_runtime.register_agent("PlannerAgent", "2.0.0", ["plan", "compile"], PlannerAgent(model_router, prompt_loader))
agent_runtime.register_agent("MemoryAgent", "2.0.0", ["memory"], MemoryAgent(model_router, prompt_loader))
agent_runtime.register_agent("JourneyMonitor", "2.0.0", ["monitor"], JourneyMonitor)
agent_runtime.register_agent("RecoveryAgent", "2.0.0", ["recovery"], RecoveryAgent)
agent_runtime.register_agent("ReflectionAgent", "2.0.0", ["reflection"], ReflectionAgent(model_router, prompt_loader))
```

The gateway routes incoming user message contexts and compiles plans by retrieving agents dynamically (e.g. `agent_runtime.get_agent_by_capability("intent")`) instead of loading hardcoded module instances.

---

## 4. Verification Results

### A. Unit Tests
* **Provider Routing Tests** ([test_provider_routing.py](file:///d:/TravelOps%20AI%20%E2%80%93%20Autonomous%20Travel%20Operations%20Agent/tests/test_provider_routing.py)): Verifies routing, audit logs, and automatic failovers to `MockBusProvider` when `DummyFailProvider` encounters errors.
* **Dynamic Agent Routing Tests** ([test_dynamic_agent_routing.py](file:///d:/TravelOps%20AI%20%E2%80%93%20Autonomous%20Travel%20Operations%20Agent/tests/test_dynamic_agent_routing.py)): Confirms agent capability resolution and health status schemas.
* **Result**: `OK` (All 55 tests passed successfully).

### B. CLI Scenarios Demo
* **Command**: `python demo_scenarios.py all`
* **Output Matrix**:
  - **Scenario 1 (Normal Success)**: All tasks complete. Weather, distance, and booking confirmations routed successfully via `MockBusProvider`.
  - **Scenario 2 (Saga Rollback)**: Payment failure triggers Saga engine, reverting held seats via `ProviderRouter.cancel_booking()`.
  - **Scenario 3 (Disruption Rebooking)**: Cancellation event triggers rebooking, selecting alternative route from inventory and reserving it.
