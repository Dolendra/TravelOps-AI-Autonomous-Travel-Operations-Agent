# Workflow Design Document (WDD) - TravelOps AI

This document details the mechanics of the Workflow Engine, State Machine transitions, Task Dependency Graphs, and the event-driven sequence flows that govern TravelOps AI.

---

## 1. Workflow State Machine Mechanics

The Workflow Engine manages session execution states. The current state is updated in the database `workflow_states` table.

```
       ┌───────┐
       │  NEW  │
       └───┬───┘
           │ Intent Parsing
           ▼
  ┌─────────────────┐
  │  INTENT_PARSED  │
  └────────┬────────┘
           │
     ┌─────┴──────────────┐
     ▼ Search             ▼ Cancel
┌───────────┐       ┌───────────┐
│ SEARCHING │       │ CANCELLED │
└─────┬─────┘       └───────────┘
      │ Matches found
      ▼
┌───────────────┐
│ OPTIONS_FOUND │
└─────┬─────────┘
      │ Select & Reserve
      ▼
┌──────────────────┐
│ WAITING_APPROVAL │
└─────┬────────────┘
      │ User Approved
      ▼
┌─────────────────┐
│ PAYMENT_PENDING │
└─────┬───────────┘
      │ Success
      ▼
┌───────────┐
│  BOOKING  │
└─────┬─────┘
      │ PNR Issued
      ▼
┌───────────┐
│  BOOKED   │
└─────┬─────┘
      │ Monitor Initiated
      ▼
┌──────────────┐
│  MONITORING  ├────────────────────────┐
└─────┬────────┘                        │
      │ Journey Complete                │ Disruption detected
      ▼                                 ▼
┌───────────────┐              ┌─────────────────┐
│   COMPLETED   │              │    DISRUPTED    │
└───────────────┘              └────────┬────────5
                                        │ Recovery active
                                        ▼
                               ┌─────────────────┐
                               │   RECOVERING    │
                               └────────┬────────┘
                                        │ Re-booked & Confirmed
                                        ▼
                               ┌─────────────────┐
                               │     BOOKED      │
                               └─────────────────┘
```

---

## 2. Task Dependency Graph Structure

The Planner Agent generates tasks as a Directed Acyclic Graph (DAG). The Workflow Engine executes these tasks in order of their dependencies.

```json
{
  "session_id": "session_8899aacc",
  "tasks": [
    {
      "id": "task_search_01",
      "name": "SearchBuses",
      "dependencies": [],
      "status": "completed",
      "input_data": {
        "origin": "Hyderabad",
        "destination": "Bangalore",
        "date": "2026-06-28"
      },
      "output_data": {
        "buses_found": 12
      }
    },
    {
      "id": "task_recommend_01",
      "name": "RankRecommendations",
      "dependencies": ["task_search_01"],
      "status": "pending",
      "input_data": {},
      "output_data": {}
    },
    {
      "id": "task_notify_01",
      "name": "SendSearchReport",
      "dependencies": ["task_recommend_01"],
      "status": "pending",
      "input_data": {},
      "output_data": {}
    }
  ]
}
```

---

## 3. Disruption Recovery Sequence Flow (Sequence Diagram)

Below is the execution flow when a bus cancellation event triggers the autonomous recovery loop:

```mermaid
sequenceDiagram
    autonumber
    participant Telemetry as Telemetry Feed
    participant Monitor as Journey Monitor Agent
    participant Bus as Event Bus
    participant Store as Event Store
    participant Recovery as Recovery Agent
    participant DB as SQLite DB
    participant UI as React UI (User)

    Telemetry->>Monitor: PNR AB1234 Cancelled by Operator
    Activate Monitor
    Monitor->>Bus: Publish: "BusCancelled" Event
    Deactivate Monitor

    Bus->>Store: Save event record
    Bus->>Recovery: Trigger subscriber hook
    Activate Recovery

    Recovery->>DB: Set workflow state to "DISRUPTED"
    Recovery->>DB: Set PNR AB1234 status to "cancelled"
    
    Note over Recovery: Querying search tool for alternate buses
    Recovery->>DB: Execute Search Tool (Hyderabad -> Bangalore, 2026-06-28)
    DB-->>Recovery: 3 alternate operators found

    Note over Recovery: Compare fares and operators
    Recovery->>DB: Call Policy Engine (check price difference limit)
    DB-->>Recovery: Difference is +₹100 (within limits)

    Note over Recovery: Reserve seat on alternate bus to lock inventory
    Recovery->>DB: Execute Reserve Seat (VRL Travels, Seat 14)
    DB-->>Recovery: Seat Locked for 15 mins (Temp Booking ID: TX789)

    Recovery->>DB: Save recovery tasks to DB Task Store
    Recovery->>DB: Transition state to "WAITING_APPROVAL"

    Recovery->>UI: Notify Disruption & Present New Option (Confirm payment of +₹100)
    Deactivate Recovery
    
    UI->>Recovery: User Clicks "Approve & Re-book"
    Activate Recovery
    
    Recovery->>DB: Transition state to "PAYMENT_PENDING"
    Recovery->>DB: Execute Payment Gateway (charge diff ₹100)
    DB-->>Recovery: Payment Succeeded

    Recovery->>DB: Transition state to "BOOKING"
    Recovery->>DB: Confirm Seat (VRL Travels, TX789)
    DB-->>Recovery: Booking Confirmed (New PNR: CD5678)
    
    Recovery->>DB: Log Recovery execution audit trail
    Recovery->>DB: Transition state to "BOOKED"
    Recovery->>UI: Send updated ticket PDF with PNR CD5678
    Deactivate Recovery
```
