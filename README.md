# TravelOps AI v2.0 — Enterprise Travel Operations Platform

TravelOps AI is a production-grade, event-driven travel operations platform. Designed as an AI Operating System for Travel, it continuously monitors bookings, dynamically generates task dependency graphs, resolves disruptions, caches API responses, and routes tasks to specialized cognitive, operational, and infrastructure agents.

---

## 🏗️ 7-Layer Architecture Overview

```
┌────────────────────────────────────────────────────────┐
│ 1. PRESENTATION LAYER (VITE React Client Dashboard)    │
├────────────────────────────────────────────────────────┤
│ 2. CONVERSATION & CONTEXT LAYER (Session & TTL Leases) │
├────────────────────────────────────────────────────────┤
│ 3. PLANNING & WORKFLOW LAYER (DSL DAG Compiler)        │
├────────────────────────────────────────────────────────┤
│ 4. AGENT RUNTIME LAYER (Registry & Health Checkers)    │
├────────────────────────────────────────────────────────┤
│ 5. TOOL EXECUTION LAYER (Circuit Breakers & Idempotency)│
├────────────────────────────────────────────────────────┤
│ 6. EVENT & AUTOMATION LAYER (Async Event Bus)          │
├────────────────────────────────────────────────────────┤
│ 7. STORAGE & OBSERVABILITY LAYER (Prometheus & SQL DB) │
└────────────────────────────────────────────────────────┘
```

Detailed architectural diagrams and layer descriptions are available in the [System Architecture Guide](file:///d:/TravelOps%20AI%20%E2%80%93%20Autonomous%20Travel%20Operations%20Agent/docs/architecture.md).

---

## 🚀 Key Feature Matrix

* **Declarative Workflow DSL**: Define operational flows in YAML/JSON. The compiler validates DAG shapes, prevents circular references, and schedules execution waves in parallel.
* **Central Agent Runtime Registry**: Decouples agent implementations. Routes goals based on capability tags, handles version constraints, and tracks agent health with automatic circuit-breaking checks.
* **Context Caching & Leases**: Assembles prompt contexts using token budgets, signs payloads with SHA-256 hashes, and uses TTL leases to cache LLM results and avoid duplicate calls.
* **Saga Compensation Rollbacks**: Ensures database transactional integrity. If a step fails, the system executes compensation rollbacks (releasing seats, refunding cards) in reverse order.
* **Human-in-the-Loop Gates**: Halts execution for critical steps (like high payments or manual refunds) until an operator approves via the API dashboard.
* **Production API Integrations**: Interfaces with real external services (Google Distance Matrix, Open-Meteo, Twilio, SMTP servers) with built-in geodistance and local logger fallbacks.

---

## ⚡ Concurrency & Parallel Wave Execution

TravelOps AI groups workflow steps into **execution waves** to process independent tasks (e.g. searching routes, fetching weather, and mapping geodistance) concurrently:

```
                  ┌──► get_route_details (Maps) ────┐
                  │                                 │
[Start Workflow] ─┼──► search_buses (Inventory) ────┼──► recommend_options
                  │                                 │
                  └──► get_weather_forecast (Meteo) ┘
```

Learn more in the [Workflow Engine & Orchestration Guide](file:///d:/TravelOps%20AI%20%E2%80%93%20Autonomous%20Travel%20Operations%20Agent/docs/workflow_engine.md).

---

## 💻 Tech Stack & Infrastructure

* **Backend**: FastAPI, SQLAlchemy ORM, Uvicorn, Python 3.11+
* **Frontend**: React (Vite), Tailwind CSS, Lucide Icons, SVG Graph Viewers
* **Database**: SQLite (local testing default), PostgreSQL (production-ready)
* **Observability**: Prometheus Metrics `/metrics` & Structured JSON Tracing
* **DevOps**: Docker Compose & Kubernetes manifest deployment specs

---

## 🧭 Developer Onboarding & Quick Start

### 1. Configure the Environment
Create a `.env` file at the root of the workspace using the default configuration template:
```env
DATABASE_URL=sqlite:///travelops.db
JWT_SECRET=travelops-auth-secret-super-key-2026
GROQ_API_KEY=gsk_your_groq_api_key_here
```
*(Optionally include Twilio and SMTP configuration keys. If left blank, the platform defaults to mock console logging fallback loops).*

### 2. Install and Setup
```bash
# Initialize Python virtual environment
python -m venv .venv
.venv/Scripts/activate
pip install -r backend/requirements.txt

# Seed the database schemas and migrations
python -c "from backend.database.manager import DatabaseManager; DatabaseManager.initialize_db()"
```

### 3. Run Backend & Frontend Servers
```bash
# Terminal 1: Run FastAPI Gateway Server
uvicorn backend.api.main:app --host 127.0.0.1 --port 8000 --reload

# Terminal 2: Run Vite React Client (from /frontend directory)
npm install
npm run dev
```

---

## 📊 Verification, Benchmarks & Demos

### Run Full Test Discovery Suite
Run the 55-test unit and integration test suite locally to verify the compiler, context cache, agent runtime, and Sagas:
```bash
.venv/Scripts/python -m unittest discover -s tests -p "test_*.py"
```

### Run Interactive CLI Scenarios
The developer experience package includes a CLI tool to run and observe complex operations in the terminal:
```bash
# Run all scenarios (Success flow, Saga rollback flow, and Disruption recovery flow)
.venv/Scripts/python demo_scenarios.py all
```

---

## 📂 Documentation Index

Browse the complete documentation portal:
* 🗺️ **[System Architecture](file:///d:/TravelOps%20AI%20%E2%80%93%20Autonomous%20Travel%20Operations%20Agent/docs/architecture.md)** — Architectural layers and data pipelines.
* 📦 **[Context Runtime](file:///d:/TravelOps%20AI%20%E2%80%93%20Autonomous%20Travel%20Operations%20Agent/docs/runtime.md)** — Fragment caches, token budgets, and TTL leases.
* 🤖 **[Agent Runtime](file:///d:/TravelOps%20AI%20%E2%80%93%20Autonomous%20Travel%20Operations%20Agent/docs/agents.md)** — Capability registries, versioning, and circuit breakers.
* 🔌 **[Provider Integration & Routing](file:///d:/TravelOps%20AI%20%E2%80%93%20Autonomous%20Travel%20Operations%20Agent/docs/phases/phase_11.md)** — Abstract travel providers, dynamic failovers, and registry failover rules.
* ⚙️ **[Workflow Engine](file:///d:/TravelOps%20AI%20%E2%80%93%20Autonomous%20Travel%20Operations%20Agent/docs/workflow_engine.md)** — YAML compiler specs, approvals, and Sagas.
* 🎛️ **[API Reference](file:///d:/TravelOps%20AI%20%E2%80%93%20Autonomous%20Travel%20Operations%20Agent/docs/api.md)** — FastAPI endpoints, JWT auth, and rate limits.
* ☸️ **[Deployment Guide](file:///d:/TravelOps%20AI%20%E2%80%93%20Autonomous%20Travel%20Operations%20Agent/docs/deployment.md)** — Docker-compose and Kubernetes cluster manifests.
* ✍️ **[Contributing Guidelines](file:///d:/TravelOps%20AI%20%E2%80%93%20Autonomous%20Travel%20Operations%20Agent/docs/contributing.md)** — Registering tools, testing conventions, and commits.
* 📄 **[ADR Records](file:///d:/TravelOps%20AI%20%E2%80%93%20Autonomous%20Travel%20Operations%20Agent/docs/adr.md)** — Key technical decisions and design trade-offs.
* 📣 **[Release Notes](file:///d:/TravelOps%20AI%20%E2%80%93%20Autonomous%20Travel%20Operations%20Agent/docs/release_notes.md)** — Changelog from v1.0 (MVP) to v2.1 (Production Release).
