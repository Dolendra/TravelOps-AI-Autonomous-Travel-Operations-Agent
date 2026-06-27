# Release Notes — TravelOps AI

We are proud to document the release history of the TravelOps AI platform, transitioning from a single-user prototype into a domain-agnostic enterprise AI travel operations platform.

---

## 🚀 TravelOps AI v2.1 (Provider Runtime & Failovers)

This release focuses on platform **extensibility and decoupling**, shifting operational tasks (Search, hold, confirm, cancel) onto a dedicated Provider Integration Layer, and dynamically resolving all cognitive/operational agents out of the `AgentRuntime` registry.

### Key Highlights in v2.1:
1. **Provider Abstraction Layer**: Establishes `BaseTravelProvider` interface to encapsulate external transit vendor integrations.
2. **Provider Health Router**: Introduces `ProviderRouter` that profiles execution latency statistics, records failure counts, and triggers immediate retry failovers if preferred providers error.
3. **Dynamic Agent Registry**: Connects the FastAPI gateway and workflow executors to dynamically route reasoning goals via capability tags rather than hardcoding imports.

---

## 🚀 TravelOps AI v2.0 (Production Release)

This release elevated the project from a simple cognitive application prototype into a multi-tenant, workflow-centric operations platform.

### Key Highlights in v2.0:
1. **Declarative Workflow DSL**: Workflows are compiled into Directed Acyclic Graphs (DAGs) and executed in concurrent waves.
2. **Context Caching & Budgets**: Integrates `ContextRuntime` caching LLM responses with TTL leases and containing API costs via sliding token budgets.
3. **Saga Compensations**: Automatically triggers reverse compensating rollbacks to clean up inventory upon transaction faults.
4. **Human-in-the-Loop Gates**: Pauses execution waves for high-value tasks until operators submit approvals.
5. **Real-World Integrations**: Plugs in Google Distance Matrix, Open-Meteo REST forecast, SMTP servers, and Twilio WhatsApp channels with zero-config geodistance and mock fallback loops.

---

## 🛠️ E2E Test Suite Results

* **Automated Unit Tests**: **55/55 test cases passed successfully** (including new `test_provider_routing.py` and `test_dynamic_agent_routing.py` suites).
* **CLI Demo Tool**: Integrated `demo_scenarios.py` to trigger normal runs, Saga rollbacks, and recovery loops directly from a terminal interface.
