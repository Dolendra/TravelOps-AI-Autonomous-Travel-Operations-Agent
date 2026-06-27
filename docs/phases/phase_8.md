# Phase 8 — Production Platform (Real Enterprise AI)

This phase elevates TravelOps AI into a production-grade enterprise platform by introducing a declarative workflow engine (Pillar 1) and a prioritized, token-budgeted prompt context assembly runtime (Pillar 2). These systems cleanly decouple LLM reasoning agents from deterministic workflow execution and optimize query context sizes while enforcing strict data protection guardrails.

---

## 1. Architectural Blueprint

The prompt and workflow execution pipelines process customer events and construct context boundaries as follows:

```
                          Customer Chat Request
                                    │
                                    ▼
                         [ Modular Intent Agent ]
                                    │
          ┌─────────────────────────┴─────────────────────────┐
          ▼ (search_bus)                                      ▼ (general_chat / support)
[ Declarative Workflow Compiler ]                 [ Prompt Context Builder ]
  - Loads YAML DSL Definitions                      - Gathers prioritized context fragments
  - Injects parsed parameters                       - Prunes fragments via TokenBudgetManager
  - Validates DAG cycles (Acyclic DFS)              - Sanitizes PII using GuardrailsProcessor
  - Saves task states in SQLite                     - Cache lookups via ContextCache hashes
          │                                                   │
          ▼                                                   ▼
[ Workflow Executor / DAG Solver ]                 [ Target LLM Routing ]
```

---

## 2. File & Module Structure

The following modules represent the core features developed under this phase:

| File Path | Description |
| :--- | :--- |
| [`backend/workflows/compiler.py`](file:///d:/TravelOps%20AI%20%E2%80%93%20Autonomous%20Travel%20Operations%20Agent/backend/workflows/compiler.py) | **[New]** Reads YAML templates, resolves recursive inline placeholders, and validates execution graphs against circular loops. |
| [`backend/workflows/definitions/`](file:///d:/TravelOps%20AI%20%E2%80%93%20Autonomous%20Travel%20Operations%20Agent/backend/workflows/definitions/) | **[New]** YAML DSL templates defining standard intercity travel flows (`full_booking.yaml`, `search_and_recommend.yaml`, `cancel_booking.yaml`, `disruption_recovery.yaml`). |
| [`backend/context/models.py`](file:///d:/TravelOps%20AI%20%E2%80%93%20Autonomous%20Travel%20Operations%20Agent/backend/context/models.py) | **[New]** Context models containing `ContextFragment` and `ContextBundle` data schemas tracking metadata, versions, and trace IDs. |
| [`backend/context/providers/`](file:///d:/TravelOps%20AI%20%E2%80%93%20Autonomous%20Travel%20Operations%20Agent/backend/context/providers/) | **[New]** Layered context providers: `system.py` (100), `workflow.py` (90), `conversation.py` (80/40), `memory.py` (70), `policy.py` (60), and `rag.py` (50). |
| [`backend/context/token_budget.py`](file:///d:/TravelOps%20AI%20%E2%80%93%20Autonomous%20Travel%20Operations%20Agent/backend/context/token_budget.py) | **[New]** Clips or truncates low-priority context fragments (e.g. RAG, old history) dynamically when exceeding the 8000 token limit. |
| [`backend/context/cache.py`](file:///d:/TravelOps%20AI%20%E2%80%93%20Autonomous%20Travel%20Operations%20Agent/backend/context/cache.py) | **[New]** Caches compiled context bundles in-memory using SHA256 hashes generated from the session, query, and history signatures. |
| [`backend/context/builder.py`](file:///d:/TravelOps%20AI%20%E2%80%93%20Autonomous%20Travel%20Operations%20Agent/backend/context/builder.py) | **[New]** Entrypoint assembling context layers, invoking budgeting/caching, applying PII masking, and returning compiled bundles. |
| [`tests/test_context_assembly.py`](file:///d:/TravelOps%20AI%20%E2%80%93%20Autonomous%20Travel%20Operations%20Agent/tests/test_context_assembly.py) | **[New]** Verification test suite checking token budget sorting/pruning, cache hits/misses, and unified assembly responses. |

---

## 3. Core Implementation Details

### A. Declarative Workflow Engine (Pillar 1)
* **YAML DSL Templates**: Replaces hardcoded Python task creation. Defines strict workflows containing step lists, dependencies, and required input parameters.
* **Variable Resolution**: Automatically parses templates at run-time, recursively replacing placeholders like `${origin}` or `${travel_date}` with current session parameters.
* **Circular Loop Safety**: Employs a Depth-First Search (DFS) topological sorter during compilation. If a cycle is detected, the engine raises a compilation failure block immediately, ensuring task sequences form a valid Directed Acyclic Graph (DAG).

### B. Prompt Context Assembly Service (Pillar 2)
* **Layered Fragment Assembly**: Assembles prompts dynamically using modular providers, scoring priority levels from system rules down to dialogue history:
  1. **System Prompt (Priority 100)**: Directives matching the routing agent.
  2. **Active Workflow (Priority 90)**: Active state machine status and current task progress details.
  3. **User Active Query (Priority 80)**: The parsed current user instruction.
  4. **User Preferences (Priority 70)**: Custom passenger profiles extracted by `MemoryAgent`.
  5. **Standard Policies (Priority 60)**: Business guidelines for refunds and cancellation rules.
  6. **RAG Vector FAQ Matches (Priority 50)**: Matching FAQ answers retrieved via Jaccard text overlap similarity.
  7. **Conversation History Logs (Priority 40)**: Preceding dialogue turns.
* **Sliding Token Budgets**: Automatically prunes lower priority fragments (RAG or history logs) if total character sizes exceed token budget bounds (defaulting to 8000 tokens), preventing LLM prompt degradation.
* **Secure Cache Storage**: Caches completed bundles in a secure hash map. Avoids repetitive database checks if dialogue states or active queries remain unchanged.

---

## 4. Verification & Testing Metrics

Both workflow engine and context assembly features have been thoroughly tested:
* **Context Assembly Unit Tests**: Created `tests/test_context_assembly.py`. Successfully tests:
  - Pruning low-priority fragments under strict budget constraints.
  - Checking memory caching hits and misses.
  - Resolving unified context structures with active database records and PII card scrubbing.
* **System Integration Verification**: All 40 unit tests completed successfully:
  ```text
  Ran 40 tests in 8.125s. OK.
  ```
* **Offline Swarm Evaluations**: Evaluated 5 main travel scenarios checking intent matching, entity extraction, and compiled tasks shapes:
  - **Intent Accuracy**: 100.0%
  - **Entity Accuracy**: 100.0%
  - **Workflow Success Rate**: 100.0%
  - **Average Latency**: 0.138s
