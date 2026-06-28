# ADR 0003: Context Builder, Leased Context Caching, and Token Budgets

## Status
Accepted

## Context
AI agents require localized session variables and prompt templates to perform cognitive tasks. Frequent LLM queries can lead to redundant network lookups, prompt inflation, high execution latency, and unexpected token expenses.

## Decision
We implemented a **Context Assembly Pipeline** with integrated performance controls:
1. Implemented a centralized **Context Builder** that compiles active prompts and session variables.
2. Built a **Leased Context Cache** storing LLM summaries under sliding time-to-live (TTL) leases to prevent duplicate reasoning calls.
3. Implemented a **Token Budget Circuit Breaker** that monitors cumulative token expenditures per session. If a session exceeds the budgeted ceiling, the circuit trips to block API billing runs.

## Alternatives Considered
- **Direct System Prompt Injection**: Injecting the raw user preferences into every individual agent call. *Rejected* due to rapid context window exhaustions and excessive Groq API billing charges.
- **Vector Database RAG**: Storing preferences in a vector index. *Rejected* because session operations require exact parameter values (e.g. seat number) rather than semantic text similarity matching.

## Consequences
- **Positive**: Optimizes token consumption. Drastically decreases latency. Safe guardrails against runaway agent loops.
- **Negative**: Adds caching TTL overhead; stale data must be cleared manually during quick operations adjustments.
