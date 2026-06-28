# Phase 12: TravelOps AI Studio (v2.2 Operations Portal)

This phase introduces **TravelOps AI Studio v2.2**, moving the platform from a conversational chatbot interface to a visual Operations Control Center. It encapsulates real-time execution pipelines, dynamic SVG task DAGs, event timelines, metrics dashboards, and debugging playback simulators.

---

## 1. Unified Studio API Telemetry

To supply the frontend studio panels with live runtime statistics, a unified backend endpoint was added to [main.py](file:///d:/TravelOps%20AI%20%E2%80%93%20Autonomous%20Travel%20Operations%20Agent/backend/api/main.py):

* **Endpoint**: `GET /api/sessions/{session_id}/studio-details`
* **Payload returned**:
  - **Timeline Logs**: Full array of `AuditLogModel` items for the session, detailing cognitive reasoning and tools execution summaries.
  - **Aggregated Metrics**: Session token metrics, dynamic LLM API cost calculations, and sliding-window cache hit rates.
  - **Agent Registry**: Active statuses, capabilities, and latency averages derived from the dynamic `AgentRuntime` registry.
  - **Provider Health matrix**: Real-time latencies and consecutive failure counters from the `ProviderRouter`.

---

## 2. Interactive SVG DAG Canvas & Node Inspector

Rather than relying on heavy third-party rendering frameworks, we built a light, reactive SVG-based DAG canvas:

* **Layout Coordinates**: Automatically positions tasks vertically and horizontally based on dependency layers (e.g. splitting `get_route_details` and `get_weather_forecast` into sibling branches before merging back to `recommend_options`).
* **Visual Connections**: Connections are drawn as SVG lines, styled to glow and pulse dynamically when parent tasks execute.
* **Inspectability**: Clicking on any node rect focuses the node inside the React state, rendering its raw JSON input parameters, output results, latency metrics, and retries count in the inspector panel.

---

## 3. Visual Playback Replay Engine

To improve developers and operators debugging experience, we introduced a client-side **Replay playback engine**:

* In the Operations Console, clicking **"▶ Replay"** pauses live session polling, clones the current task state, and sets all statuses to `PENDING`.
* A recursive timeout steps through the tasks sequentially (every `1200ms`), updating their status, drawing the green connection flow, and updating the inspector block.

---

## 4. Live Agent Context Viewer

We exposed a protected prompts reader endpoint to view the filesystem's system prompts in the UI:

* **Endpoint**: `GET /api/prompts/{name}`
* **Function**: Reads and sanitizes markdown prompt templates (e.g. `intent.md`, `planner.md`, `memory.md`, `reflection.md`, `support.md`) directly from the workspace `prompts/` directory.
* **Studio Panel**: Renders raw prompt instructions inside a clean code panel alongside cognitive memory preferences.

---

## 5. Verification & Tests Status

* **Production Builds**: Frontend compiles cleanly via Vite production compiler in `868ms`.
* **Telemetry Endpoints**: Verified that standard passenger and administrator sessions correctly resolve `/studio-details` and `/prompts/` routes.
