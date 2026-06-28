# ADR 0004: Event Bus and Event-Driven Recovery

## Status
Accepted

## Context
Transit booking operations do not end at ticket confirmation. Real-world disruptions (e.g. bus cancellations, route delays) occur long after the initial booking transaction. The system needs to monitor active runs and execute auto-recoveries on the fly.

## Decision
We implemented a decoupled **Event Bus** architecture for event-driven recovery:
1. Created an asynchronous `EventBus` that handles subscribing to and publishing events.
2. Built a persistent `EventStoreModel` in SQLite to record a complete log of events (`BusCancelled`, `BusDelayed`).
3. Registered the `JourneyMonitor` and `RecoveryAgent` as subscribers to cancellation events. When a cancellation event is published, the subscribers intercept it, look up alternative runs, and compile a new rebooking workflow.

## Alternatives Considered
- **Synchronous Polling Loops**: Running constant SQL queries to verify run statuses. *Rejected* as it strains database connections and leads to high resource utilization.
- **External Message Brokers**: Integrating RabbitMQ or Apache Kafka. *Rejected* to avoid setup complexities in single-instance local developer deployments.

## Consequences
- **Positive**: Complete loose coupling. Asynchronous, non-blocking disruption recovery. Audit trail of all platform events.
- **Negative**: Adds event ordering constraints. Requires handling potential race conditions when publishing concurrent cancellations.
