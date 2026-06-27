# TravelOps AI — Phase 3: Multi-Agent System (Orchestration) Documentation

This document contains a comprehensive breakdown of the files, classes, methods, and functions created or modified during **Phase 3: Multi-Agent System (Orchestration)**. In this phase, we implemented dynamic graph planning, concurrent DAG execution solvers, self-repair reflection agents, persistent preference memory stores, and real-time backend-driven UI status tracking.

---

## System Architecture

The blueprint below represents the multi-agent system architecture and concurrent orchestration engine implemented in Phase 3, showing the interaction between the Memory Agent, Planner Agent, Workflow Orchestrator, and Self-Reflection Repair Agent.

```mermaid
graph TD
    User["User Message"] -->|Message POST| Gateway["API Gateway (main.py)"]
    
    subgraph MultiAgents ["Multi-Agent System Layer"]
        MemAgent["MemoryAgent (Preference Extractor)"]
        PlanAgent["PlannerAgent (DAG Task Planner)"]
        Orch["WorkflowOrchestrator (Wave Scheduler)"]
        RefAgent["ReflectionAgent (Self-Repair Planner)"]
    end

    subgraph Storage ["Persistent State Layer (SQLite)"]
        DBCache["CacheModel (Preferences)"]
        DBTasks["TaskStateModel (DAG States)"]
    end

    Gateway -->|1. Parse & Merge Preferences| MemAgent
    MemAgent <-->|Read / Write Profile| DBCache
    Gateway -->|2. Generate Travel Graph| PlanAgent
    PlanAgent -->|Injects Preferences| PlanAgent
    PlanAgent -->|3. Populate PENDING Tasks| DBTasks
    
    Gateway -->|4. Trigger Run Endpoint| Orch
    Orch <-->|5. Read / Update Status Waves| DBTasks
    Orch -->|6. Execute Tool API| ToolRegistry["ToolRegistry (Execute API)"]
    
    ToolRegistry -->|If Tool Fails (success=False)| Orch
    Orch -->|7. Invoke Repair| RefAgent
    RefAgent -->|Reads Graph State| DBTasks
    RefAgent -->|8. Patch Input & Reset PENDING| DBTasks
    
    UI["Vite Client (App.jsx)"] <-->|9. Poll Status (2s interval)| Gateway
```

---

## 1. Directory & File Overview

The new and modified files in Phase 3 include:

| File Path | Description |
| :--- | :--- |
| [`agents/memory/memory_agent.py`](file:///d:/TravelOps%20AI%20%E2%80%93%20Autonomous%20Travel%20Operations%20Agent/agents/memory/memory_agent.py) | **[New]** Created the `MemoryAgent` class to handle preference extraction and persistence in the database cache. |
| [`prompts/memory.md`](file:///d:/TravelOps%20AI%20%E2%80%93%20Autonomous%20Travel%20Operations%20Agent/prompts/memory.md) | **[New]** Created the system prompt template for the Memory Agent to guide LLM extraction. |
| [`agents/reflection/reflection_agent.py`](file:///d:/TravelOps%20AI%20%E2%80%93%20Autonomous%20Travel%20Operations%20Agent/agents/reflection/reflection_agent.py) | **[New]** Created the `ReflectionAgent` class to self-repair failed task graphs dynamically. |
| [`backend/workflows/orchestrator.py`](file:///d:/TravelOps%20AI%20%E2%80%93%20Autonomous%20Travel%20Operations%20Agent/backend/workflows/orchestrator.py) | **[New]** Created the `WorkflowOrchestrator` execution loop to solve DAG graphs concurrently. |
| [`backend/tools/travel_tools.py`](file:///d:/TravelOps%20AI%20%E2%80%93%20Autonomous%20Travel%20Operations%20Agent/backend/tools/travel_tools.py) | **[Modified]** Updated `RecommendOptionsTool` to retrieve user sorting preferences from memory dynamically. |
| [`backend/api/main.py`](file:///d:/TravelOps%20AI%20%E2%80%93%20Autonomous%20Travel%20Operations%20Agent/backend/api/main.py) | **[Modified]** Integrated `PlannerAgent` and `MemoryAgent` into chat message routing, implemented the `/run` background tasks endpoint, and updated `mock_planner` fallback robustness. |
| [`frontend/src/App.jsx`](file:///d:/TravelOps%20AI%20%E2%80%93%20Autonomous%20Travel%20Operations%20Agent/frontend/src/App.jsx) | **[Modified]** Replaced client-side simulation with backend orchestrator execution hooks and implemented 2-second dynamic state polling. |
| [`tests/test_phase3.py`](file:///d:/TravelOps%20AI%20%E2%80%93%20Autonomous%20Travel%20Operations%20Agent/tests/test_phase3.py) | **[New]** Created the Phase 3 test suite containing unit tests for planner, memory, reflection, and concurrent orchestrator loop execution. |

---

## 2. Memory Extraction & Cache

### File: [`agents/memory/memory_agent.py`](file:///d:/TravelOps%20AI%20%E2%80%93%20Autonomous%20Travel%20Operations%20Agent/agents/memory/memory_agent.py)
Extracts and persists semantic user travel preferences in the SQLite DB `CacheModel` table.

#### Classes & Methods:
* **`MemoryAgent`**
  * **Role:** Manages user profile/preferences storage.
  * **Methods:**
    * `__init__(model_router: ModelRouter, prompt_loader: PromptLoader)`: Binds router and prompt loaders.
    * `save_preference(session_id: str, preference_text: str) -> Dict[str, Any]`: Parses the user message text, loads existing preferences from SQLite cache (key: `memory:preferences:{session_id}`), merges new non-null updates, commits back to the database, and returns the merged profile.
    * `retrieve_preferences(session_id: str) -> Dict[str, Any]`: Retrieves the profile dictionary mapped to `memory:preferences:{session_id}` in `CacheModel`.
    * `parse_preference_text(preference_text: str) -> Dict[str, Any]`: Evaluates preference input using the `memory` prompt template via the LLM API, falling back to local heuristics if the API call fails or key is missing.
    * `_heuristic_fallback(text: str, defaults: Dict[str, Any]) -> Dict[str, Any]`: Keyword matcher parsing sorting rules ("cheapest", "rating"), operator brands ("VRL", "KSRTC", "SRS", etc.), and seat placement preferences ("window", "aisle").

---

## 3. Reflection & Self-Repair Agent

### File: [`agents/reflection/reflection_agent.py`](file:///d:/TravelOps%20AI%20%E2%80%93%20Autonomous%20Travel%20Operations%20Agent/agents/reflection/reflection_agent.py)
Inspects failing nodes in the task graph and modifies parameters in SQLite to restart threads automatically.

#### Classes & Methods:
* **`ReflectionAgent`**
  * **Role:** Implements graph self-repair and replanning.
  * **Methods:**
    * `__init__(model_router: ModelRouter, prompt_loader: PromptLoader)`: Binds service components.
    * `reflect_and_repair(session_id: str, failed_task_id: str, error_msg: str) -> bool`: Collects the database status of all session tasks. Renders the reflection template context (parameters: `failed_task_name`, `failed_task_id`, `error_message`, `graph_state`). Queries the LLM reasoning agent for a repair JSON decision:
      * **`action: "retry"` or `"replan"`**: Patches inputs in `TaskStateModel` for the specified tasks, resets status to `"PENDING"`, clears output logs, and appends any newly generated task nodes. Returns `True` (signaling orchestrator retry).
      * **`action: "abort"`**: Returns `False` (signaling permanent failure).

---

## 4. Concurrent DAG Workflow Orchestrator

### File: [`backend/workflows/orchestrator.py`](file:///d:/TravelOps%20AI%20%E2%80%93%20Autonomous%20Travel%20Operations%20Agent/backend/workflows/orchestrator.py)
Implements topological dependency solvers to schedule execution waves concurrently.

#### Classes & Methods:
* **`WorkflowOrchestrator`**
  * **Role:** Manages async task dependency schedules.
  * **Methods:**
    * `execute_graph(session_id: str) [staticmethod]`: Main loop resolving DAG steps. Evaluates dependencies case-by-case:
      * Identifies ready tasks (status is `"PENDING"`, and all parent task dependencies are `"COMPLETED"`).
      * Transitions ready tasks to `"RUNNING"` and schedules execution waves in parallel using `asyncio.gather`.
      * Propagates completed outputs to descendent task inputs.
      * Includes a 1.2-second sleep step between waves to support visual transition animations on the React client.
    * `_execute_single_task(session_id: str, db_task_id: int, tool_name: str, arguments: Dict[str, Any]) [staticmethod]`: Dispatches tool runs to worker pools using `asyncio.to_thread`. If tool fails, sets task state to `"FAILED"` and triggers `ReflectionAgent`. If repaired, resets back to `"PENDING"`. If repair fails, updates session state to `"FAILED"`. If successful, sets status to `"COMPLETED"` and advances milestones in `WorkflowStateModel` (e.g. `search_buses` ➔ `OPTIONS_FOUND`, `hold_seat` ➔ `PAYMENT_PENDING`).

---

## 5. Gateway Endpoints

### File: [`backend/api/main.py`](file:///d:/TravelOps%20AI%20%E2%80%93%20Autonomous%20Travel%20Operations%20Agent/backend/api/main.py)
Modified routes to integrate Phase 3 agents and background tasks.

#### Modified & Added Endlines:
* **`send_message(session_id, req, db)` [Modified]**:
  * Saves passenger preferences using `MemoryAgent.save_preference`.
  * Instantiates the `PlannerAgent` class to build the JSON dependency graph using active preferences.
  * Clears old sessions and saves new task nodes.
  * Updates `mock_planner` fallback to use dynamic seat allocation (letting `HoldSeatTool` pick the first available seat) and provides a valid test credit card format to pass payment check filters.
* **`run_session_workflow(session_id, background_tasks, db)` [New]**:
  * Endpoint `POST /api/sessions/{session_id}/run`.
  * Resets tasks to `"PENDING"` for fresh execution runs if they were previously completed or failed.
  * Starts `WorkflowOrchestrator.execute_graph` as an asynchronous FastAPI `BackgroundTasks` thread.

---

## 6. Frontend Execution & Polling

### File: [`frontend/src/App.jsx`](file:///d:/TravelOps%20AI%20%E2%80%93%20Autonomous%20Travel%20Operations%20Agent/frontend/src/App.jsx)
Hooked client-side control to backend background execution loops.

#### Modified Handlers & Hooks:
* **`handleSimulateExecution()` [Modified]**: Triggers the backend background worker by issuing a `POST` request to `/api/sessions/{session_id}/run`.
* **Polling Hook (`useEffect`) [Modified]**: Starts a 2-second background polling interval loading `fetchSessionDetails()` whenever `currentSessionId` changes, updating task progress colors (Pending ➔ Running ➔ Completed) reactively as database records update.

---

## 7. Verification & Testing Suite

### File: [`tests/test_phase3.py`](file:///d:/TravelOps%20AI%20%E2%80%93%20Autonomous%20Travel%20Operations%20Agent/tests/test_phase3.py)
Establishes Phase 3 unit testing logic inside the virtual environment.

#### Test Cases:
* `test_planner_agent()`: Mock-patches LLM response to assert Planner Agent maps structured graph nodes.
* `test_memory_agent_heuristics()`: Validates parsing heuristics for operator name matches, cheapest fare rules, and window seat keywords.
* `test_memory_agent_llm()`: Mock-patches LLM preference extraction and asserts database persistence.
* `test_reflection_agent()`: Seeds a failing task, mock-patches LLM correction rules, and validates inputs are updated and status reset back to `"PENDING"`.
* `test_orchestrator_execution()`: Boots in-memory database records, registers dependencies, and validates `WorkflowOrchestrator` execution loop synchronously via `asyncio.run` to confirm task waves complete.
