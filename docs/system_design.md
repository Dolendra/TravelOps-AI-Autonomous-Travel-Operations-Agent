# System Design Document (SDD) - TravelOps AI
### Workflow-Centric Multi-Agent Travel Operations Platform

TravelOps AI is designed as a workflow-centric, event-driven travel operations platform. This document outlines the overall system architecture, 7-layer organization, non-functional requirements (NFRs), and strategies for production scalability and deployment.

---

## 1. 7-Layer Architecture Description

The platform separates responsibilities into distinct layers, allowing modular scaling and technology swapping:

1. **Presentation Layer**:
   - Web interface built in React (using Vite) with custom dark theme CSS.
   - Provides real-time chat interface, reactive UI cards (showing active tasks, recommended buses, booking states), and a metrics dashboard visualizing LLM latencies and model selections.
2. **Conversation & Context Layer**:
   - Manages user sessions and constructs optimized prompts via the Context Builder.
   - Merges recent conversation history (Working Memory) with persistent user preferences (Semantic Memory) and past trip histories (Episodic Memory).
3. **Planning & Workflow Layer**:
   - Extracts intent from raw user inputs.
   - Dynamically builds Task Dependency Graphs using the Planner Agent.
   - Feeds the graph into the Workflow Engine, which executes states within the Workflow State Machine.
4. **Agent Execution Layer**:
   - Coordinates specialized Cognitive (reasoning), Operational (execution), and Infrastructure (system health) agents.
   - Routes agent logic calls to target LLMs through the Model Router.
5. **Tool Execution Layer**:
   - Dispatches execution tasks to registered tools (e.g. search, booking, payment gateways).
   - Enforces Caching rules, retry strategies, and circuit breakers.
6. **Event & Automation Layer**:
   - Facilitates reactive, asynchronous triggers using the Async Event Bus (e.g. initiating rebooking when a cancellation event is received).
   - Manages time-based tasks via the Automation Engine (Scheduler).
7. **Storage & Observability Layer**:
   - SQLite DB (for local dev) representing the state store, audit logs, and event store.
   - Observability API compiling runtime metrics (token usage, latency, error counts) for downstream analysis.

---

## 2. Non-Functional Requirements (NFRs)

### A. Latency Targets
- **Intent Parsing**: $< 500\text{ ms}$ (routed to reasoning model on Groq).
- **Core Orchestration overhead**: $< 100\text{ ms}$ (local state transition logic).
- **Tool executions**:
  - Cached search: $< 50\text{ ms}$.
  - Live APIs (mocked): $< 200\text{ ms}$.
- **End-to-End response time**: $< 1.5\text{ seconds}$ total round-trip.

### B. Cost Targets
- **Fast operations** (70-80% of traffic): $< \$0.001$ per API call utilizing Groq's fast model.
- **Complex reasoning** (planning, rebooking): $< \$0.02$ per execution utilizing Groq's reasoning model.
- **Average cost per completed trip lifecycle**: $< \$0.05$ (highly optimized compared to using monolithic model chains).

### C. Reliability & Fault Tolerance
- **Circuit Breakers**: Injected into the Tool Registry. If external bus APIs fail 3 times consecutively, the registry trips the breaker for 60 seconds, returning a fallback response ("Inventory API temporarily unavailable") and raising an alert to the Reflection Agent.
- **Retry Policies**: Standard exponential backoff ($2^n \times 100\text{ ms}$) up to 3 retries for transient HTTP errors.
- **Fallback Models**: If Groq's reasoning model fails, the Model Router automatically switches to an alternative reasoning endpoint.

### D. Security & Privacy
- **PII Guardrails**: Intercepts input/output payloads in the Guardrails layer. Masks phone numbers, emails, names, and credit card patterns before they are sent to external LLM providers.
- **State Isolation**: User sessions are strictly isolated in SQLite by `session_id` tokens.

---

## 3. Deployment & Scalability Plan

```
                           [ Internet Traffic ]
                                    │
                                    ▼
                         [ ALB / Ingress Controller ]
                                    │
                  ┌─────────────────┴─────────────────┐
                  ▼                                   ▼
        [ FastAPI Instance 1 ]              [ FastAPI Instance 2 ]
        (Stateless REST API)                (Stateless REST API)
                  │                                   │
                  └─────────────────┬─────────────────┘
                                    │
        ┌───────────────────────────┼───────────────────────────┐
        ▼                           ▼                           ▼
[ Shared Redis Cache ]      [ Message Broker ]         [ DB Cluster ]
(State/Query Caching)       (Kafka / RabbitMQ)         (Postgres DB)
                                    │
                  ┌─────────────────┴─────────────────┐
                  ▼                                   ▼
        [ Journey Worker 1 ]                [ Journey Worker 2 ]
        (Subscribers & Cron)                (Subscribers & Cron)
```

### A. Stateless Gateway Horizontal Scaling
The FastAPI gateway maintains no local state. Session details, workflow graphs, and audit logs are persisted in a centralized Database (SQLite locally, PostgreSQL in production). Multiple replicas of the FastAPI gateway can run behind an Application Load Balancer (ALB).

### B. Event Bus Scaling (Apache Kafka / RabbitMQ)
- In production, the simple in-memory `asyncio.Queue` event bus is replaced with **Apache Kafka** or **RabbitMQ**.
- Background workers (consumers) subscribe to specific topics (e.g. `disruptions.bus-cancelled`).
- Worker groups process recovery workflows in parallel, ensuring high throughput.

### C. Containerization & Orchestration
- Dockerfiles compile the backend (FastAPI) and frontend (React build) into lightweight containers.
- Kubernetes manifests define deployment limits, liveness/readiness probes, and horizontal pod autoscalers based on CPU and request rates.
