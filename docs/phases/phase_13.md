# Phase 13: Release Candidate 1 (RC1)

This phase focuses on **Release Engineering** and transitioning TravelOps AI from a sophisticated architecture into an enterprise-grade open-source candidate. RC1 is divided into four distinct developer sprints.

---

## 📅 Sprint Breakdown & Status

| Sprint | Description | Status |
| --- | --- | --- |
| **Sprint 1** | Developer Experience (DX files, packaging, Docker configurations) | **IN PROGRESS** |
| **Sprint 2** | Demo Environment (seeding, resets, disruption simulations, runtime benchmarks) | **COMPLETED** |
| **Sprint 3** | Python SDK (`travelops-sdk/` client module) | **NOT STARTED** |
| **Sprint 4** | API Documentation (OpenAPI, Postman, curl guides) | **NOT STARTED** |

---

## 🛠️ Sprint 2 Deliverables: Demo Environment (Completed)

To ensure that the **AI Operations Studio v2.2** dashboard is fully populated upon first launch, we built a complete scripting toolset under the `scripts/` directory:

1. **`reset_db.py`**:
   - Safely registers models with SQLAlchemy's `Base.metadata` and drops all active database tables.
   - Invokes `init_db()` to seed raw bus runs and seat layouts.
2. **`seed_demo_dataset.py`**:
   - Seeds the database with **100 Bookings** (containing 20 cancellations, 5 payment failures, 3 rebooking recoveries).
   - Generates **50 conversation sessions** representing realistic passenger searches.
   - Populates **300+ Audit Logs** containing LLM token profiles, estimated costs, and provider health router events.
3. **`simulate_disruption.py`**:
   - Queries the database for the latest confirmed booking and publishes a `BusCancelled` event to the `EventBus`.
   - Triggers `JourneyMonitor` and `RecoveryAgent` to automatically rebook the impacted passenger.
4. **`benchmark_runtime.py`**:
   - Compiles the `full_booking.yaml` DSL and runs 5 parallel worker loops.
   - Employs a staggered async delay (600ms stagger) to prevent SQLite concurrency connection locking.

---

## 🚀 Sprint 1 Targets: Developer Experience (Starting)

Sprint 1 builds the foundational guides and configurations for developer onboarding:

* **Repository Guides**:
  - `ARCHITECTURE.md`: Technical breakdown of runtime, event bus, context building, and database schema layers.
  - `QUICKSTART.md`: Rapid 5-minute setup instructions using virtual environments or Docker.
  - `CONTRIBUTING.md`: Style guidelines, branch naming conventions, and testing commands.
  - `CHANGELOG.md` & `LICENSE`.
* **Packaging & Configuration**:
  - `pyproject.toml` / `setup.py` configurations.
  - `requirements.txt` listing decoupled dependency layers.
  - `.env.example` template.
