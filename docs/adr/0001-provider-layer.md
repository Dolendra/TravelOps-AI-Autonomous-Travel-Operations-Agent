# ADR 0001: Provider Integration Layer and Health Router

## Status
Accepted

## Context
TravelOps AI integrates with multiple external bus transit providers (e.g. VRL Travels, IntrCity SmartBus, and mock vendors). Each provider has distinct API endpoints, response schemas, and variable latencies. If a preferred provider undergoes an outage, transaction requests fail, resulting in lost bookings and degraded system reliability.

## Decision
We implemented a decoupled **Provider Abstraction Layer** alongside a dynamic **Provider Health Router**:
1. Defined a uniform `BaseTravelProvider` interface that exposes standard methods (`search_buses`, `hold_seat`, `confirm_booking`, `cancel_booking`).
2. Created a singleton `ProviderRouter` that intercepts tool calls and selects the active provider.
3. Implemented a sliding window error accumulator inside the router. If a provider registers `3` consecutive failures, its health status trips to `UNHEALTHY`, automatically routing downstream execution requests to backup providers.

## Alternatives Considered
- **Direct Integration in Tools**: Hardcoding vendor API logic inside the python tool blocks. *Rejected* due to tight coupling and lack of failover capabilities.
- **Microservices Routing**: Offloading failovers to an external API gateway (e.g. Kong or Envoy). *Rejected* to avoid additional infrastructure management overhead.

## Consequences
- **Positive**: High resilience. Zero downtime during provider outages. Real-time health metrics.
- **Negative**: Adds a layer of indirection. Requires syncing vendor inventory configurations across multiple adapter implementations.
