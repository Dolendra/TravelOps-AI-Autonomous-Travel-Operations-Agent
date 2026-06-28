# ADR 0002: Declarative Workflow DSL and Saga Rollback Engine

## Status
Accepted

## Context
Travel booking operations involve multiple multi-step transactional sequences (Search, Hold Ticket, Charge Payment, Confirm Ticket). A failure in any mid-chain step (e.g. billing failure after holding a seat) leads to orphaned locks and database inconsistencies if the preceding modifications are not undone.

## Decision
We implemented a **Declarative YAML DSL Workflow Engine** backed by a **Saga Compensating Transaction Rollback** mechanism:
1. Workflows are defined as Directed Acyclic Graphs (DAGs) in YAML, specifying task nodes, parameters, retry limits, and rollback triggers.
2. The `WorkflowCompiler` validates constraints and topologically orders execution waves.
3. The `WorkflowExecutor` executes task waves concurrently.
4. If a task fails and exceeds retries, the executor halts forward progress and invokes the Saga engine. The engine executes registered compensating rollbacks (e.g. `release_seat`) in reverse order to return the system to its initial consistent state.

## Alternatives Considered
- **Imperative Python Workflows**: Hardcoding booking flows in python `try-except` blocks. *Rejected* due to difficulty in visualizing graphs, re-running tasks from failure points, or dynamically compiling user instructions.
- **Temporal/Airflow Integration**: Using an external orchestrator. *Rejected* to keep TravelOps AI lightweight, zero-dependency, and execution-fast.

## Consequences
- **Positive**: Complete transactional consistency. Clear visualization of tasks DAGs.
- **Negative**: Workflow creation requires learning a custom YAML configuration layout.
