# Agent Design Document (ADD) - TravelOps AI

This document details the responsibilities, input/output schemas, prompt strategies, memory scopes, and failure recovery modes for the specialized agents in the TravelOps AI platform.

---

## 1. Cognitive Agents (Reasoning)

Cognitive agents analyze, plan, and recommend actions. They require reasoning capabilities (`llama3-70b-8192`).

### A. Intent Agent
- **Responsibility**: Parse user natural language and resolve relative dates against system local time.
- **Inputs**: User message string, current system datetime.
- **Outputs**:
  - `primary_intent`: enum (`search_bus`, `book_bus`, `cancel_bus`, `monitor_journey`, `get_status`, `general_chat`)
  - `entities`: JSON object (origin, destination, travel_date, PNR, seat, passenger list)
  - `confidence`: float (0.0 to 1.0)
- **Memory**: Working Memory (current message context).
- **Failure Mode**: Defaults to `general_chat` with confidence `0.0` if parsing fails.

### B. Planner Agent
- **Responsibility**: Generate a dependency-based Task Graph to fulfill the user's travel goal.
- **Inputs**: User intent schema, active state history.
- **Outputs**:
  - `tasks`: List of task objects (id, name, depend_on_ids, status, input_parameters)
- **Memory**: Working Memory + Semantic Memory (to respect user preferences during plan design).
- **Failure Mode**: If graph contains circular dependencies, falls back to a linear search-then-book task graph template.

### C. Recommendation Agent
- **Responsibility**: Filter, rank, and score available buses by combining raw features with user history.
- **Inputs**: Search results list, User Semantic Memory.
- **Outputs**: Ranked list of top 3 options with written explanation tags (pros, cons).
- **Memory**: Semantic Memory (reads user seat type, operator preference, budget threshold).
- **Failure Mode**: If user preferences are missing, ranks purely by operator rating.

### D. Reflection Agent
- **Responsibility**: Intervene when a plan fails (e.g. no direct buses found) and recommend alternative travel options.
- **Inputs**: Failed task state, target origin/destination, date.
- **Outputs**: Replanned Task Graph (e.g. suggesting connecting cities or date adjustments).
- **Memory**: Working Memory + Episodic Memory.
- **Failure Mode**: Escales to human operator support request if connecting route planner fails.

### E. Memory Agent
- **Responsibility**: Parse conversation chat history to extract and save persistent preferences (Semantic) or trip outcomes (Episodic).
- **Inputs**: Chat log list, session ID.
- **Outputs**: Updated preferences JSON.
- **Memory**: Summarizes raw conversation logs to update Semantic & Episodic DB stores.
- **Failure Mode**: Skips updates if confidence in user preference extraction is $< 0.8$.

---

## 2. Operational Agents (Execution)

Operational agents perform deterministic actions. They use fast capabilities (`llama3-8b-8192`) or direct code.

### A. Search Agent
- **Responsibility**: Query the Tool Registry for route availability, boarding/dropping points, and seat maps.
- **Inputs**: Origin, destination, date.
- **Outputs**: JSON list of matches.
- **Failure Mode**: Returns empty list and prompts the Reflection Agent to replan.

### B. Booking Agent
- **Responsibility**: Collect passenger profiles, check seat maps, and coordinate seat locks.
- **Inputs**: Passenger details, selected seat ID, bus ID.
- **Outputs**: Reserved status payload.
- **Failure Mode**: Unlocks locked seats if transaction times out.

### C. Cancellation Agent
- **Responsibility**: Cancel confirmed bookings, calculate policy-driven refund values, and trigger gateway refunds.
- **Inputs**: PNR number.
- **Outputs**: Cancelled status and refund receipt.
- **Failure Mode**: Halts cancellation if PNR is not found or is within 2 hours of departure.

### D. Recovery Agent
- **Responsibility**: Execute re-booking and ticketing transfer during bus disruptions.
- **Inputs**: Disruption event details (e.g. cancelled PNR).
- **Outputs**: Newly booked PNR and transfer confirmation.
- **Failure Mode**: Cancels the recovery step and marks state as `FAILED` if no alternative buses can be booked.

### E. Notification Agent
- **Responsibility**: Dispatch alerts across SMS, WhatsApp, and Email.
- **Inputs**: Alert template ID, recipient address, PNR/Ticket data.
- **Outputs**: Send receipt status.
- **Failure Mode**: Retries sending once; if failures persist, logs delivery failure to the system observability index.

---

## 3. Platform Services & Middleware (Deterministic Logic)

These components govern business rules, security compliance, event orchestration, and job timing. They execute deterministic code blocks without relying on LLM reasoning.

### A. Policy Service
- **Responsibility**: Compute refund splits, upgrade costs, and fare differences. Runs purely deterministic business rules.
- **Inputs**: Booking details, cancellation time metrics.
- **Outputs**: Accurate fare credit and adjustment metrics.

### B. Guardrails Middleware
- **Responsibility**: Intercept raw chat strings, scan for prompt injection patterns, and mask sensitive PII (emails, credentials, credit cards).
- **Inputs**: Raw user message string.
- **Outputs**: Sanitized string and validation status.

### C. Journey Monitor Service
- **Responsibility**: Watch telemetry schedules and active passenger bookings to publish real-time disruption updates to the event bus.
- **Inputs**: Active passenger booking records.
- **Outputs**: Broadcasts Event Bus events (e.g. `BusCancelled`, `BusDelayed`).

### D. Scheduler Service
- **Responsibility**: Orchestrate delay triggers and cron jobs for future notifications or status polls.
- **Inputs**: Delayed execution callbacks and time-delta configs.
- **Outputs**: Job execution handles and trigger outputs.

