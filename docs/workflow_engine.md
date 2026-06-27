# Workflow Engine & Orchestration

The **Workflow Engine** coordinates execution of compiled transaction graphs. Rather than hardcoding sequences in Python, the engine compiles structured YAML blueprints into Directed Acyclic Graphs (DAGs) and enforces step-level reliability constraints.

---

## 📄 Declarative YAML Workflow DSL

Workflows are defined as YAML files under `backend/workflows/definitions/`. The compiler validates dependency shapes, checking for circular structures.

### Key Step Parameters
* `depend_on_ids`: IDs of prior tasks that must complete successfully before this task runs.
* `parallel`: When set to `true`, the task will run concurrently with other tasks in the same dependency level.
* `timeout`: The maximum execution time in seconds. If exceeded, the engine aborts the step.
* `retry`: Maximum retry attempts and retry delay rules.
* `approval_required`: When set to `true`, pauses execution and waits for human operator clearance.
* `rollback`: Specifies the compensating transaction step to execute if the workflow fails.

---

## ⚡ Concurrency & Wave Scheduling

The **Workflow Executor** processes tasks in concurrent waves:
1. Resolves all tasks with empty `depend_on_ids` and schedules them in **Wave 1**.
2. Tasks marked `parallel: true` run in concurrent execution threads.
3. Once all tasks in Wave 1 complete successfully, tasks in **Wave 2** (whose dependencies are now resolved) are queued.
4. Execution proceeds wave by wave until the final target node is resolved.

---

## 👥 Human-in-the-Loop Approval Gates

For high-cost transactions or modifications (e.g. issuing a manual refund or upgrades), tasks can require authorization:
* **Workflow Suspension**: When a task with `approval_required: true` is reached, the executor changes its state to `PAUSED` and suspends the thread.
* **Gateway State**: The main session transitions to `APPROVAL_REQUIRED`.
* **Resume Trigger**: Once an operator triggers `/api/sessions/{session_id}/approve`, the task status changes to `COMPLETED` or `RESUMING`, and the executor resumes subsequent waves.

---

## 🔄 Saga Pattern Compensation Rollbacks

If a task fails and cannot be self-repaired by the Reflection Agent, the engine halts forward progress and triggers a **Saga Rollback**:

```
Forward Execution:
[Search Buses] ──► [Hold Seat] ──► [Process Payment (FAIL)]
                                           │
                                           ▼ (Halts)
Compensating Saga:
[Release Seat Hold] ◄──────────────────────┘
```

The executor traverses the list of successfully completed steps in reverse order and executes their corresponding `rollback` actions (e.g., releasing a hold or cancelling a payment authorization) to return the platform state to its original consistency.
