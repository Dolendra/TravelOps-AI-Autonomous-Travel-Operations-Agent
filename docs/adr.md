# Architectural Decision Records (ADR)

This document contains the Architectural Decision Records outlining why specific abstractions, technologies, and designs were chosen for the TravelOps AI platform.

---

## 🏛️ ADR 1: Local SQLite State Storage vs. PostgreSQL

### Context
The platform needs to store session states, conversation memory, workflow execution graphs, and Prometheus metrics. During local developer execution and unit testing, requiring a full PostgreSQL instance makes onboarding and local testing complex.

### Decision
We chose a **switchable SQLAlchemy Database Engine** defaulting to a local **SQLite** file-based database (`travelops.db` / `test_travelops.db`).

### Consequences
* **Pros**:
  - No database service installation required to demo the project locally.
  - Performance is high for single-user scenarios and testing.
  - Automated tests can run in-memory or create temporary file databases, maintaining speed.
* **Cons**:
  - SQLite does not support highly concurrent writes under heavy stress.
* **Migration Path**: The code uses SQLAlchemy ORM models, making it compatible with PostgreSQL. For production deployments, change `DATABASE_URL` in the `.env` file to a postgres connection string (`postgresql://user:pass@host:port/dbname`).

---

## 🏛️ ADR 2: Declarative YAML DSL vs. Agentic Frameworks (LangGraph/LangChain)

### Context
Early iterations of agent systems often rely on dynamic LLM routing loops (like LangChain or LangGraph), where the LLM decides the next tool to run in a loop. In travel operations, this approach can lead to unpredictable loops, double charges, and infinite retries.

### Decision
We chose a **Declarative YAML Workflow compilation model**. The LLM (Planner Agent) compiles the user's intent into a static Directed Acyclic Graph (DAG) specified in a YAML/JSON workflow template. The **Workflow Executor** then runs this graph deterministically.

### Consequences
* **Pros**:
  - **Predictability**: Execution follows a defined path.
  - **Auditable**: Workflows are fully versionable and logged.
  - **Parallelism**: The engine schedules execution waves concurrently.
  - **Saga Safety**: If a step fails, the system executes compensation rollbacks (releasing seats, refunding cards) in reverse order.
* **Cons**:
  - Less dynamic mid-execution changes, but offset by the **Reflection Agent** which can replan or edit the graph dynamically if a failure occurs.
