# Changelog

All notable changes to the TravelOps AI project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [2.2.0] — 2026-06-28
### Added
- **Interactive SVG DAG Visualizer**: Connects tasks dynamically based on compiled dependency layers. Shows color-coded states and execution flows.
- **Execution Replay Engine**: In-browser simulator to step through past DAG executions sequentially with inspector pane updates.
- **Agent Context Viewer**: Displays active system prompts and extracted passenger preferences.
- **Operations Dashboard Home**: Graph grids and telemetry reporting LLM cost projections, tokens consumed, cache hit rates, and provider router health indices.
- **Seeding & Simulation Toolsets**: Built seeder scripts for 100+ bookings, logs, event timelines, and concurrent performance benchmarks.

## [2.1.0] — 2026-06-25
### Added
- **Provider Abstraction Layer**: Establishes standard interfaces for multi-vendor integrations.
- **Provider Health Router**: Introduces real-time latency profiling and failover routing logic for transit providers.
- **Dynamic Agent Registry**: Connects the FastAPI gateway to resolve cognitive agent roles based on tags.

## [2.0.0] — 2026-06-20
### Added
- **Declarative Workflow DSL**: Graph-based task waves compiler.
- **Context Caching & Budgets**: Implements token lease scopes.
- **Saga compensating rollbacks**: Reverts tickets upon failure.
- **Human-in-the-Loop gates**: Pauses executor waves until admin approval.
