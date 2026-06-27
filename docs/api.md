# API Reference & Security Gateway

TravelOps AI exposes an asynchronous HTTP gateway using FastAPI. Security and session validation occur at the gateway layer before routing payloads down to agents or tool executors.

---

## 🔒 Security & Session Isolation

1. **Authentication Protocol**: JWT (JSON Web Tokens) with HS256 encryption.
2. **Access Control**: Users must send an `Authorization: Bearer <JWT_TOKEN>` header to access protected endpoints.
3. **Session Isolation**: Sessions are isolated by the authenticated user's ID. Users cannot read or execute workflows of other active sessions.

---

## 🚦 Rate Limiting Gateway

The gateway features a built-in **Token-Bucket Rate Limiter**:
* **Rule**: Limits calls based on user ID and client IP address.
* **Headers**: Exposes `X-RateLimit-Limit`, `X-RateLimit-Remaining`, and `X-RateLimit-Reset` on response headers.
* **HTTP Error**: If limits are exceeded, the gateway short-circuits execution and returns a `429 Too Many Requests` code.

---

## 📡 REST API Endpoint Schema

The backend automatically generates interactive Swagger docs under `/docs`. The core routes include:

### User & Authentication
* `POST /api/auth/register`: Create a new user profile.
* `POST /api/auth/login`: Authenticate and receive a JWT access token.

### Interactive Chat Engine
* `POST /api/chat/message`: Send user input, run PII guardrails, identify intent, customize plans, and trigger workflow runtimes.
* `GET /api/chat/history`: Fetch conversation history for a given session.

### Workflow & Task Orchestration
* `GET /api/sessions`: List active workflows, overall status, and current task metrics.
* `GET /api/sessions/{session_id}/tasks`: Fetch detailed execution status of all nodes in a DAG.
* `POST /api/sessions/{session_id}/approve`: Operator manual approval trigger to release paused gates.
* `POST /api/sessions/{session_id}/cancel`: Force cancellation and trigger Saga rollback.

### Observability & Platform Telemetry
* `GET /metrics`: Exposes Prometheus-formatted metrics (active session volume, LLM latency, cost calculations, circuit breaker states).
* `GET /api/audit-logs`: Query internal audit files for historical agent decisions and reasoning reports.
