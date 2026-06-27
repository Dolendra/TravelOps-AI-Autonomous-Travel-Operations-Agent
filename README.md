# TravelOps AI: Workflow-Centric Multi-Agent Travel Operations Platform

TravelOps AI is a production-grade, event-driven travel operations orchestration engine. It coordinates cognitive planning agents, deterministic workflow state machines, concurrent executors, and recovery triggers to deliver a resilient, multi-user travel booking experience.

---

## 🏗️ Architectural Layers

```
┌────────────────────────────────────────────────────────┐
│               PRESENTATION LAYER (VITE React)          │
│          (Chat Interface, Task Graphs, Telemetry)      │
└───────────────────────────┬────────────────────────────┘
                            │ (OAuth2 JWT Bearer Tokens)
┌───────────────────────────▼────────────────────────────┐
│              AUTHENTICATION & SESSION GATEWAY          │
│            (Multi-User Isolation, Rate Limiting)       │
└───────────────────────────┬────────────────────────────┘
                            │
┌───────────────────────────▼────────────────────────────┐
│                PLANNING & WORKFLOW ENGINE              │
│    (Task Graphs, State Machine, Reflection & Repair)   │
└───────────────────────────┬────────────────────────────┘
                            │
┌───────────────────────────▼────────────────────────────┐
│             TOOL ENGINE & RELIABILITY GATEWAY          │
│       (Circuit Breakers, Idempotency, Cache)          │
└───────────────────────────┬────────────────────────────┘
                            │
┌───────────────────────────▼────────────────────────────┐
│                STORAGE & OBSERVABILITY                 │
│      (PostgreSQL/SQLite Engine, Prometheus Metrics)    │
└────────────────────────────────────────────────────────┘
```

The system is organized into 7 distinct architectural layers:
1. **Presentation Layer**: Tailwind & glassmorphism dark-theme React interface displaying live task execution status, graphs, and cost counters.
2. **Conversation & Context Layer**: Controls active sessions, applying **PII Guardrails** to sanitize data and **Memory Heuristics** to extract sorting preferences.
3. **Planning & Workflow Layer**: Translates user goals into task dependency graphs (Directed Acyclic Graphs) and runs them in the **Workflow State Machine**.
4. **Agent Execution Layer**: Couples reasoning cognitive agents (Intent, Planner, Memory, Reflection, Recommendation) through the **Model Router**.
5. **Tool Execution Layer**: Houses concrete service wrappers (Search, Hold, Pay, Confirm, Notify) governed by **Circuit Breakers** and **Idempotency Keys**.
6. **Event & Automation Layer**: Publishes schedule telemetry (e.g. `BusCancelled`) to trigger autonomous recovery rebookings.
7. **Storage & Observability Layer**: Provides central connection engines switchable to SQLite or PostgreSQL, request tracing logs, and **Prometheus metrics**.

---

## 🛠️ Taxonomy & System Boundaries

Unlike basic AI chat apps, TravelOps AI draws a strict line between reasoning agents and deterministic software services:

### 🧠 Cognitive Agents (LLM Reasoning)
* **Intent Agent**: Evaluates user goals and extracts origin/destination/dates.
* **Planner Agent**: Synthesizes custom execution plans as Directed Acyclic Graphs.
* **Reflection Agent**: Auto-corrects failed tasks and schedules graph retries.
* **Memory Agent**: Condenses sorting preferences and operator favorites.
* **Recommendation Agent**: Ranks options by combining search data with memory context.

### 🛡️ Platform Services (Deterministic Logic)
* **Policy Service**: Calculates refund metrics based on reservation dates.
* **Guardrails Middleware**: Sanitizes incoming payloads to prevent prompt injections.
* **Scheduler Service**: Controls delay triggers and cron jobs for future notifications or status polls.
* **Workflow Engine**: Concurrently executes task waves and solves graph dependencies.
* **Tool Registry**: Manages execution hooks, auditing logs, and error catching.
* **Model Router**: Tracks token usage, model capacities, and estimated run costs.
* **Observability Service**: Exposes Prometheus metrics and compiles trace telemetry.

---

## 🚀 Getting Started

### 1. Prerequisite Environments
* Python 3.11+
* Node.js 18+

### 2. Installation & Setup
Clone the repository and run the setup steps:
```bash
# Setup python environment
python -m venv .venv
.venv/Scripts/activate
pip install -r backend/requirements.txt

# Seed the database and stamp migrations
python backend/database/db.py
alembic stamp head
```

### 3. Run Backend Server
```bash
uvicorn backend.api.main:app --host 127.0.0.1 --port 8000 --reload
```

---

## 📊 Verification & Tests

### Automated Unit Testing
Run the complete unittest suite to verify storage engines, Auth APIs, schedulers, and recovery rules:
```bash
.venv/Scripts/python -m unittest discover tests
```

### AI Evaluation Runner (CI Pipeline)
Run the AI performance and regression evaluation dataset to measure intent and planner accuracy:
```bash
.venv/Scripts/python tests/eval_runner.py
```

### Multi-User Load Simulator
To run concurrent stress simulation across 20, 50, and 100 threads:
```bash
.venv/Scripts/python tests/load_simulator.py --concurrency 20,50
```

---

## 🛡️ Reliability & Security
* **Circuit Breakers**: Tripped when external services fail, fast-failing subsequent transactions to protect platform load.
* **Idempotency keys**: Payment and booking tools track `Idempotency-Key` parameter scopes to prevent double charging.
* **Rate Limiting**: Custom token-bucket rate limiter middleware defends gateway endpoints against API abuse.
* **Prometheus metrics**: `/metrics` endpoint exposes real-time active sessions, LLM costs, and error rates.
