# Database Design Document (DDD) - TravelOps AI

This document specifies the database schema design, indexing strategy, and storage configurations for the TravelOps AI platform.

---

## 1. Schema Tables & Data Types

Below is the database table configuration implemented in SQLite (and ready for PostgreSQL).

```
   ┌─────────────────┐           ┌──────────────────────┐
   │    sessions     │           │   workflow_states    │
   ├─────────────────┤           ├──────────────────────┤
   │ PK  id          │◄─────────┐│ PK  id               │
   │     created_at  │          └│ FK  session_id       │
   │     updated_at  │           │     current_state    │
   │     preferences │           │     context_data     │
   └────────┬────────┘           └──────────────────────┘
            │
            │  ┌──────────────────────┐
            ├─►│     chat_messages    │
            │  ├──────────────────────┤
            │  │ PK  id               │
            │  │ FK  session_id       │
            │  │     role             │
            │  │     content          │
            │  │     intent           │
            │  └──────────────────────┘
            │  ┌──────────────────────┐
            ├─►│      task_states     │
            │  ├──────────────────────┤
            │  │ PK  id               │
            │  │ FK  session_id       │
            │  │     name             │
            │  │     dependencies     │
            │  │     status           │
            │  └──────────────────────┘
            │  ┌──────────────────────┐
            ├─►│      audit_logs      │
            │  ├──────────────────────┤
            │  │ PK  id               │
            │  │ FK  session_id       │
            │  │     agent_name       │
            │  │     action           │
            │  │     reasoning_summary│
            │  └──────────────────────┘
            │  ┌──────────────────────┐
            └─►│       bookings       │
               ├──────────────────────┤
               │ PK  pnr              │
               │ FK  session_id       │
               │     passenger_name   │
               │     status           │
               └──────────────────────┘
```

---

## 2. Table Specifications

### A. Table: `sessions`
- **id**: `VARCHAR(36)` [PRIMARY KEY, NOT NULL] - Session UUID.
- **created_at**: `TIMESTAMP` [DEFAULT: UTC Now].
- **updated_at**: `TIMESTAMP` [DEFAULT: UTC Now].
- **preferences**: `TEXT` [DEFAULT: '{}'] - Serialized JSON of user preferences (favorite operators, window/aisle choice, budget caps) updated by the Memory Agent.

### B. Table: `workflow_states`
- **id**: `INTEGER` [PRIMARY KEY, AUTOINCREMENT]
- **session_id**: `VARCHAR(36)` [FOREIGN KEY -> sessions.id, NOT NULL]
- **current_state**: `VARCHAR(50)` [NOT NULL] - Active state (e.g. `WAITING_APPROVAL`, `DISRUPTED`).
- **context_data**: `TEXT` - Serialized JSON of data in flight (e.g., currently selected bus details, prices).

### C. Table: `task_states`
- **id**: `VARCHAR(50)` [PRIMARY KEY] - Task identifier (e.g. `task_search_01`).
- **session_id**: `VARCHAR(36)` [FOREIGN KEY -> sessions.id, NOT NULL]
- **name**: `VARCHAR(100)` [NOT NULL]
- **dependencies**: `TEXT` - JSON array of dependencies (e.g. `["task_search_01"]`).
- **status**: `VARCHAR(20)` [DEFAULT: 'pending'] - `pending`, `running`, `completed`, `failed`.
- **input_data**: `TEXT` - JSON input parameters.
- **output_data**: `TEXT` - JSON outputs.

### D. Table: `audit_logs`
- **id**: `INTEGER` [PRIMARY KEY, AUTOINCREMENT]
- **session_id**: `VARCHAR(36)` [FOREIGN KEY -> sessions.id, NOT NULL]
- **agent_name**: `VARCHAR(100)` [NOT NULL] - Originating agent (e.g. `ReflectionAgent`).
- **action**: `VARCHAR(100)` [NOT NULL] - e.g. `replan_routes`.
- **reasoning_summary**: `TEXT` - Summary explaining the AI decision.
- **payload**: `TEXT` - Raw JSON context parameter log.
- **timestamp**: `TIMESTAMP` [DEFAULT: UTC Now].

### E. Table: `event_store`
- **id**: `VARCHAR(36)` [PRIMARY KEY] - Event UUID.
- **event_type**: `VARCHAR(100)` [NOT NULL] - e.g. `BusCancelled`, `PaymentSucceeded`.
- **session_id**: `VARCHAR(36)`
- **payload**: `TEXT` - JSON payload containing telemetry parameters.
- **timestamp**: `TIMESTAMP` [DEFAULT: UTC Now].

### F. Table: `cache`
- **key**: `VARCHAR(256)` [PRIMARY KEY] - MD5 or SHA256 hash of search query variables.
- **value**: `TEXT` [NOT NULL] - JSON cached response.
- **expires_at**: `TIMESTAMP` [NOT NULL] - Expiry threshold (typically 10 minutes for inventory queries).

---

## 3. Indexing Strategy

To maintain low latency under concurrent user queries:
- **`idx_session_messages`**: Create index on `chat_messages(session_id, timestamp)` to load histories quickly.
- **`idx_task_session`**: Create index on `task_states(session_id, status)` to query active DAG nodes.
- **`idx_audit_session`**: Create index on `audit_logs(session_id, timestamp)` to load agent trace pages.
- **`idx_event_type`**: Create index on `event_store(event_type)` for subscriber query optimization.
- **`idx_cache_expires`**: Create index on `cache(expires_at)` to support automatic purge cron jobs.
