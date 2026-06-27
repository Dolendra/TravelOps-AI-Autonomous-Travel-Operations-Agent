# TravelOps AI — Phase 2: Single-Agent Intelligence (Operations) Documentation

This document contains a comprehensive breakdown of the files, classes, methods, and functions created or modified during **Phase 2: Single-Agent Intelligence (Operations)**. In this phase, we implemented database-backed bus searching, recommendations, seat reservation holds, payment processing, deterministic business policies, and input safety guardrails.

---

## System Architecture

The workflow diagram below represents the single-agent operational intelligence pipeline of Phase 2, illustrating how user inputs are checked for safety, classified for intent, validated, and run sequentially through the relational database-backed API tools.

```mermaid
graph TD
    User["User Message"] -->|Submit| GR_Input["GuardrailsProcessor (Sanitize Input)"]
    GR_Input -->|Mask PII & Scan Injection| Intent["IntentAgent (Parse Intent)"]
    Intent -->|Match Intent & Extract Entities| Exec["REST Tool Gateway (main.py)"]
    
    subgraph Tools ["Operations Tools & Policies"]
        direction TB
        T1["SearchBusTool (search_buses)"] -->|Cache check / Query DB| T2["RecommendOptionsTool (recommend_options)"]
        T2 -->|Multi-criteria rating score| T3["HoldSeatTool (hold_seat)"]
        T3 -->|Inventory seat block| T4["ProcessPaymentTool (process_payment)"]
        T4 -->|Luhn check card verification| T5["ConfirmBookingTool (confirm_booking)"]
        T5 -->|Generate PNR ticket| T6["SendNotificationTool (send_notification)"]
        
        PE["PolicyEngine (Upgrades & Refunds)"] -.->|Enforces rules| T5
    end

    Exec -->|Validate arguments (GuardrailsProcessor.validate_args)| T1
```

---

## 1. Directory & File Overview

The new and modified files in Phase 2 include:

| File Path | Description |
| :--- | :--- |
| [`backend/database/models.py`](file:///d:/TravelOps%20AI%20%E2%80%93%20Autonomous%20Travel%20Operations%20Agent/backend/database/models.py) | **[Modified]** Added `BusInventoryModel` and `BookingModel` ORM schemas. |
| [`backend/database/db.py`](file:///d:/TravelOps%20AI%20%E2%80%93%20Autonomous%20Travel%20Operations%20Agent/backend/database/db.py) | **[Modified]** Implemented auto-seeding logic in `init_db()` to generate default routes on startup. |
| [`agents/intent/intent_agent.py`](file:///d:/TravelOps%20AI%20%E2%80%93%20Autonomous%20Travel%20Operations%20Agent/agents/intent/intent_agent.py) | **[New]** Created the `IntentAgent` class to query Groq LLM for entity extraction and intent mapping. |
| [`backend/tools/travel_tools.py`](file:///d:/TravelOps%20AI%20%E2%80%93%20Autonomous%20Travel%20Operations%20Agent/backend/tools/travel_tools.py) | **[New]** Created 6 database-backed tools representing individual agent actions: Search, Recommend, Hold Seat, Payment, Ticket Confirm, and Notify. |
| [`backend/services/policy.py`](file:///d:/TravelOps%20AI%20%E2%80%93%20Autonomous%20Travel%20Operations%20Agent/backend/services/policy.py) | **[New]** Created the `PolicyEngine` class to enforce deterministic business rules (refund percentages and seat upgrades). |
| [`backend/services/guardrails.py`](file:///d:/TravelOps%20AI%20%E2%80%93%20Autonomous%20Travel%20Operations%20Agent/backend/services/guardrails.py) | **[New]** Created the `GuardrailsProcessor` class to sanitize text logs (PII masks, prompt injections) and validate tool args. |
| [`backend/api/main.py`](file:///d:/TravelOps%20AI%20%E2%80%93%20Autonomous%20Travel%20Operations%20Agent/backend/api/main.py) | **[Modified]** Registered the new tools, integrated `IntentAgent` parsing, and wired up guardrail validations. |
| [`tests/test_phase2.py`](file:///d:/TravelOps%20AI%20%E2%80%93%20Autonomous%20Travel%20Operations%20Agent/tests/test_phase2.py) | **[New]** Created the Phase 2 test suite containing unit tests for policies, guardrails, and tools. |

---

## 2. Relational Schema Extensions

### File: [`backend/database/models.py`](file:///d:/TravelOps%20AI%20%E2%80%93%20Autonomous%20Travel%20Operations%20Agent/backend/database/models.py)
Extended to include support for persistent inventories and booking details.

#### Classes & Methods:
* **`BusInventoryModel`**
  * **Role:** Stores the inventory of bus runs available for booking.
  * **Fields:**
    * `id` (Integer PK)
    * `operator_name` (String: e.g. "VRL Travels")
    * `bus_type` (String: e.g. "A/C Sleeper (2+1)")
    * `departure_time` (String: e.g. "21:30")
    * `arrival_time` (String: e.g. "06:30")
    * `duration` (String: e.g. "9h 00m")
    * `origin` (String Index)
    * `destination` (String Index)
    * `fare` (Float)
    * `rating` (Float)
    * `available_seats` (Integer)
    * `seat_layout_raw` (Text JSON)
  * **Methods:**
    * `set_seat_layout(seats: List[str])`: Serializes seat designations (e.g. `["1A", "1B"]`) to JSON text.
    * `get_seat_layout() -> List[str]`: Deserializes raw text back to a list of seat strings.

* **`BookingModel`**
  * **Role:** Persists passenger reservation transaction records.
  * **Fields:**
    * `id` (Integer PK)
    * `session_id` (String Index)
    * `bus_id` (Integer ForeignKey)
    * `pnr` (String Unique Index)
    * `seat_number` (String)
    * `status` (String: `HELD`, `CONFIRMED`, `CANCELLED`)
    * `passenger_name` (String)
    * `passenger_email` (String)
    * `price_paid` (Float)
    * `created_at` (DateTime)

---

## 3. Database Inventory Seeding

### File: [`backend/database/db.py`](file:///d:/TravelOps%20AI%20%E2%80%93%20Autonomous%20Travel%20Operations%20Agent/backend/database/db.py)
Modified the database initializer to bootstrap the SQLite instance.

#### Modified Functions:
* **`init_db()`**
  * **Role:** Standard database initialization and data bootstrap.
  * **What it does:** Builds SQLAlchemy tables. Then, checks if `BusInventoryModel` contains any records. If empty, imports `json` and inserts 9 default bus inventory records spanning three popular intercity routes:
    * `Bangalore ➔ Hyderabad` (VRL Travels, IntrCity SmartBus)
    * `Hyderabad ➔ Bangalore` (Orange Tours & Travels, SRS Travels)
    * `Delhi ➔ Jaipur` (Zingbus, Gujarat Travels)
    * `Jaipur ➔ Delhi` (Zingbus)
    * `Mumbai ➔ Pune` (Neeta Tours, MSRTC Shivneri)

---

## 4. Intent Classification Agent

### File: [`agents/intent/intent_agent.py`](file:///d:/TravelOps%20AI%20%E2%80%93%20Autonomous%20Travel%20Operations%20Agent/agents/intent/intent_agent.py)
Modularized user intent understanding using Groq LLM API queries.

### Classes & Methods:
* **`IntentAgent`**
  * **Methods:**
    * **`__init__(model_router: ModelRouter, prompt_loader: PromptLoader)`**: Binds services.
    * **`parse_intent(message: str) -> Dict[str, Any]`**: Computes current date details, loads prompt templates under `intent.md`, issues a structured JSON completion request to the Llama 3 fast model, and returns the parsed dictionary structure (or an empty dictionary if the LLM call fails).

---

## 5. Concrete Database-Backed Tools

### File: [`backend/tools/travel_tools.py`](file:///d:/TravelOps%20AI%20%E2%80%93%20Autonomous%20Travel%20Operations%20Agent/backend/tools/travel_tools.py)
Implements tools decorated with `@register_tool` to execute bus search and reservation steps.

#### Helper Functions:
* **`luhn_check(card_num: str) -> bool`**
  * **Role:** Validates payment card authenticity.
  * **What it does:** Applies the Luhn algorithm (Modulo 10 check) on credit card numbers to verify they conform to payment provider formatting standards.
* **`get_task_output_helper(db, session_id: str, task_name: str) -> Dict[str, Any]`**
  * **Role:** Contextual parameter lookup.
  * **What it does:** Queries the database `TaskStateModel` for a matching `task_name` and returns its cached `output_raw` data. This allows subsequent tasks to dynamically retrieve input variables (like `booking_id` or `buses` list) when they are omitted in direct executions.

#### Tool Classes & Methods:

* **`SearchBusTool`**
  * **Name:** `search_buses`
  * **`execute(session_id, origin, destination, travel_date)`**: Checks Cache table for the key `search:{origin}:{destination}:{travel_date}`. If found, returns deserialized cached results (Cache Hit). Otherwise, queries `BusInventoryModel` case-insensitively, maps the travel date dynamically, saves the list to the Cache database (with a 5-minute expiration), marks the task `COMPLETED`, saves output results, and returns the list (Cache Miss).

* **`RecommendOptionsTool`**
  * **Name:** `recommend_options`
  * **`execute(session_id, preference, buses)`**: Pulls search results from database history if the `buses` list is omitted. Applies a multi-criteria score: `Score = Rating * 15 - Fare * 0.05`. Sorts options descending (or by `fare` ascending if preference is `'cheapest'`), updates the task output in DB, and returns the top 3 buses.

* **`HoldSeatTool`**
  * **Name:** `hold_seat`
  * **`execute(session_id, bus_id, seat_number, passenger_name, passenger_email)`**: Pulls the top recommended bus and first available seat from history if parameters are omitted. Verifies that the target seat layout is not already booked in `BookingModel`. Creates a new `BookingModel` record under the status `'HELD'`, decrements `available_seats` in `BusInventoryModel`, updates task state output, and returns booking keys.

* **`ProcessPaymentTool`**
  * **Name:** `process_payment`
  * **`execute(session_id, card_number, booking_id)`**: Resolves `booking_id` from hold history if omitted. Validates the `card_number` using `luhn_check()`. If valid, updates the booking status to `'CONFIRMED'`, writes a transaction ID, updates task output, and returns success logs. If validation fails, returns card validation error.

* **`ConfirmBookingTool`**
  * **Name:** `confirm_booking`
  * **`execute(session_id, booking_id)`**: Confirms the booking status. Generates a unique 6-character PNR code, writes it to the database booking record, aggregates bus operator detail models, saves ticket outputs to DB, and returns the passenger ticket confirmation.

* **`SendNotificationTool`**
  * **Name:** `send_notification`
  * **`execute(session_id, channels)`**: Retrieves passenger details and confirms booking dispatch statuses across SMS and Email delivery channels.

---

## 6. Business Policies & Safety Guardrails

### File: [`backend/services/policy.py`](file:///d:/TravelOps%20AI%20%E2%80%93%20Autonomous%20Travel%20Operations%20Agent/backend/services/policy.py)
Enforces business rule specifications.

#### Classes & Methods:
* **`PolicyEngine`**
  * **`calculate_refund_percentage(departure_time: datetime, request_time: datetime) -> float [staticmethod]`**: Deterministically calculates refund percentage rates based on time remaining before bus departure:
    * `Time difference >= 24 hours` ➔ `1.0` (100% refund)
    * `Time difference between 12-24 hours` ➔ `0.75` (75% refund)
    * `Time difference between 2-12 hours` ➔ `0.50` (50% refund)
    * `Time difference < 2 hours` ➔ `0.0` (0% refund)
  * **`validate_upgrade_eligibility(current_class: str, loyalty_points: int) -> bool [staticmethod]`**: Validates whether upgrade is allowed based on passenger class and loyalty status (minimum 1000 points).

---

### File: [`backend/services/guardrails.py`](file:///d:/TravelOps%20AI%20%E2%80%93%20Autonomous%20Travel%20Operations%20Agent/backend/services/guardrails.py)
Ensures security sanitization and argument checking.

#### Classes & Methods:
* **`GuardrailsProcessor`**
  * **`sanitize_input(text: str) -> str [staticmethod]`**: Checks input text for security concerns:
    * Replaces credit card numbers (13–19 digits) with `[MASKED_CARD]`.
    * Replaces email patterns with `[MASKED_EMAIL]`.
    * Scans for prompt injection keywords (e.g. `'ignore previous instruction'`). Throws `ValueError` if a threat signature is matching.
  * **`validate_args(tool_name: str, args: Dict) -> bool [staticmethod]`**: Enforces type and format validation before tool execution (e.g. validating string lengths for locations, verifying travel dates match `YYYY-MM-DD`, checking seat alphanumeric match rules like `^\d{1,2}[A-Z]$`). Throws `ValueError` if validation fails.

---

## 7. API Gateway Integration

### File: [`backend/api/main.py`](file:///d:/TravelOps%20AI%20%E2%80%93%20Autonomous%20Travel%20Operations%20Agent/backend/api/main.py)
Integrates new agents and validation filters into FastAPI routes.

#### Key Changes:
* **Tool Auto-Registration:** Importing `backend.tools.travel_tools` registers the 6 tools with `ToolRegistry` automatically.
* **Message Endpoint Modifications (`send_message`)**: Sanitizes incoming user messages through `GuardrailsProcessor.sanitize_input` (raising HTTP 400 if blocked). Uses `IntentAgent.parse_intent` to determine intent, falling back to keyword logic if the LLM is unavailable.
* **Task Endpoint Modifications (`execute_session_task`)**: Sanitizes tool execution parameter dictionaries using `GuardrailsProcessor.validate_args` before invoking `ToolRegistry.execute_tool`.

---

## 8. Unit Testing Suite

### File: [`tests/test_phase2.py`](file:///d:/TravelOps%20AI%20%E2%80%93%20Autonomous%20Travel%20Operations%20Agent/tests/test_phase2.py)
Establishes testing assertions run inside the virtual environment.

#### Testing Methods:
* `test_policy_engine()`: Validates refund calculation matrix boundaries and loyalty point thresholds.
* `test_guardrails_sanitizer()`: Asserts card masking, email masking, and prompt injection blocks.
* `test_guardrails_argument_validation()`: Verifies date validations and seat pattern checking.
* `test_search_and_recommend_tools()`: Validates Search cache hits and Recommend ranking sorting rules.
* `test_booking_transactional_flow()`: Exercises hold operations, Luhn card verification failures, payment approvals, and confirmed PNR ticket output generation.
