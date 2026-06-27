# API & Tool Specification (ATS) - TravelOps AI

This document specifies the REST API endpoints and tool schemas (Tool Marketplace metadata) for the TravelOps AI platform.

---

## 1. Gateway REST API Endpoints

### A. Session Management
- **POST `/api/sessions`**
  - **Description**: Initialize a new conversation and workflow session.
  - **Response (200 OK)**:
    ```json
    {
      "session_id": "8c4fa9ad-f06b-4e08-9dfb-10f7457788cb",
      "created_at": "2026-06-27T10:40:00Z"
    }
    ```

- **GET `/api/sessions/{session_id}/messages`**
  - **Description**: Fetch all conversation logs for the session.
  - **Response (200 OK)**:
    ```json
    {
      "session_id": "8c4fa9ad-f06b-4e08-9dfb-10f7457788cb",
      "messages": [
        {"role": "user", "content": "Book a ticket", "timestamp": "2026-06-27T10:40:10Z"}
      ]
    }
    ```

### B. Chat & Execution Channel
- **POST `/api/sessions/{session_id}/chat`**
  - **Description**: Process a user message through the intent agent, planner, and workflow engine.
  - **Request Body**:
    ```json
    {
      "message": "I need to reach Bangalore tomorrow."
    }
    ```
  - **Response (200 OK)**:
    ```json
    {
      "reply": "I have found 3 sleeper buses. Proceed to select a seat?",
      "session_id": "8c4fa9ad-f06b-4e08-9dfb-10f7457788cb",
      "intent": {
        "primary_intent": "search_bus",
        "entities": {"origin": "Hyderabad", "destination": "Bangalore", "travel_date": "2026-06-28"},
        "confidence": 0.95
      },
      "metrics": [
        {"model": "llama3-70b-8192", "latency_sec": 0.42, "total_tokens": 1050}
      ],
      "audit_logs": [
        {"agent_name": "IntentAgent", "action": "parse_intent", "reasoning": "Extracted destination Bangalore"}
      ],
      "tasks": [
        {"id": "task_search_01", "name": "SearchBuses", "status": "completed"}
      ]
    }
    ```

- **POST `/api/sessions/{session_id}/approve`**
  - **Description**: Provide user approval for a pending human-in-the-loop task.
  - **Request Body**:
    ```json
    {
      "task_id": "task_payment_01",
      "approved": true,
      "metadata": {"payment_method": "UPI"}
    }
    ```

---

## 2. Tool Marketplace Schema

Every tool in the Tool Registry exports metadata defining its inputs, schemas, latencies, and operational costs.

```json
{
  "name": "SearchBusTool",
  "version": "1.0.0",
  "description": "Searches for intercity buses running between origin and destination on a target date.",
  "latency_limit_ms": 1000,
  "cost_est_usd": 0.0001,
  "health_status": "healthy",
  "input_schema": {
    "type": "object",
    "properties": {
      "origin": {"type": "string"},
      "destination": {"type": "string"},
      "date": {"type": "string", "format": "date"}
    },
    "required": ["origin", "destination", "date"]
  },
  "output_schema": {
    "type": "array",
    "items": {
      "type": "object",
      "properties": {
        "bus_id": {"type": "string"},
        "operator": {"type": "string"},
        "departure": {"type": "string", "format": "date-time"},
        "fare": {"type": "number"},
        "available_seats": {"type": "integer"}
      }
    }
  }
}
```

---

## 3. Core Tool Catalog Specifications

### A. SearchBusTool
- **Parameters**: `origin` (str), `destination` (str), `date` (str: YYYY-MM-DD).
- **Function**: Queries inventory provider.
- **Circuit Breaker Rule**: If inventory API experiences timeouts ($>1.5\text{s}$) 3 times consecutively, trips the circuit, routing searches to cached databases.

### B. ReserveSeatTool
- **Parameters**: `bus_id` (str), `seat_number` (str), `passenger` (dict).
- **Function**: Lock a seat. Locks are temporary ($15\text{ mins}$) until confirmation.

### C. ConfirmBookingTool
- **Parameters**: `lock_id` (str), `payment_ref` (str).
- **Function**: Convert lock to confirmed ticket and issue PNR.

### D. CancelBookingTool
- **Parameters**: `pnr` (str).
- **Function**: Releases booking and returns refund amount calculated by the Policy Engine.

### E. SendAlertTool
- **Parameters**: `channel` (sms/whatsapp/email), `recipient` (str), `body` (str).
- **Function**: Multi-channel user notifications.
