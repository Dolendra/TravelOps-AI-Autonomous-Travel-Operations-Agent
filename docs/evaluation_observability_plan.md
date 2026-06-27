# Evaluation & Observability Plan (EOP) - TravelOps AI

This document establishes the telemetry, metric schemas, dashboard architectures, and evaluation frameworks required to assess, optimize, and safely operate the TravelOps AI platform.

---

## 1. Observability Metrics Schema

To monitor system cost and latency, the platform tracks metrics at the Model Router and Tool Execution layers.

### A. LLM Gateway Metrics (Model Router Logs)
Every model call logs the following metrics to the `AuditLogModel` / observability collector:
- **`model_name`**: Name of the execution model.
- **`capability`**: `reasoning` or `fast`.
- **`time_to_first_token_ms`**: Latency to initial token (important for streaming UX).
- **`total_latency_ms`**: End-to-end inference latency.
- **`input_tokens`**: Count of prompt tokens.
- **`output_tokens`**: Count of generation tokens.
- **`total_cost_usd`**: Calculated cost using dynamic token pricing tables (e.g. Llama3-70b: \$0.59 per million input, \$0.79 per million output).

### B. Tool Metrics
- **`tool_name`**: Name of the tool executed (e.g., `SearchBusTool`).
- **`latency_ms`**: Execution latency.
- **`status`**: `success` or `failure`.
- **`retry_count`**: Number of attempts before resolving.

---

## 2. Platform Observability Dashboard Design

The Presentation Layer visualizes the metrics in a dedicated **Developer Observability Panel**:

```
┌────────────────────────────────────────────────────────────────────────┐
│                        SYSTEM TELEMETRY SUMMARY                        │
├───────────────────────────────────┬────────────────────────────────────┤
│ Total Tokens: 184,500             │ Cumulative Cost: $0.114            │
│ Avg LLM Latency: 420ms            │ Avg API Latency: 120ms             │
├───────────────────────────────────┴────────────────────────────────────┤
│                    AGENT EXECUTION PATH TRACING                        │
│                                                                        │
│ IntentUnderstandingAgent [llama3-70b-8192] ──► 320ms ──► Success        │
│ ToolRegistry:SearchBusTool                 ──► 180ms ──► Success        │
│ RecommendationAgent      [llama3-70b-8192] ──► 510ms ──► Success        │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Automated Evaluation Framework (Eval Swarm)

Production AI requires objective scoring models rather than qualitative assessments. We define the following metrics evaluated using a test runner:

### A. Intent Extraction Accuracy (Classification Test)
- **Method**: Run 50 pre-defined user test prompts (e.g. "I want to go to Bangalore tomorrow") against the `IntentAgent`.
- **Target**: $>95\%$ classification accuracy across intents and exact extraction of location entities.
- **Score Calculation**:
  $$\text{Accuracy} = \frac{\text{Correct Intent \& Entities Matches}}{\text{Total Test Queries}} \times 100$$

### B. Planning Quality (Task Graph Validation)
- **Method**: Assert topological sorting rules on Planner outputs.
- **Rules**:
  1. No circular dependencies.
  2. Search task must complete before ranking recommendations task.
  3. Booking task must depend on seat selection and user payment confirmation tasks.
- **Target**: $100\%$ validation pass rate.

### C. Hallucination Evaluation (LLM-as-a-Judge)
- **Method**: Use a secondary evaluator model to compare search outputs with the recommended recommendations presented in chat responses.
- **Assertion**: Prompt the evaluator LLM: "Does the summary text mention any operator, fare, or schedule that is NOT present in the raw query output JSON?"
- **Target**: $0\%$ hallucination rate.
