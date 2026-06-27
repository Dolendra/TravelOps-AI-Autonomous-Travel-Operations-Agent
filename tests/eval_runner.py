import os
import sys
import json
import time
from typing import List, Dict, Any

# Resolve project import paths
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.services.llm import ModelRouter
from backend.services.prompt_loader import PromptLoader
from agents.intent.intent_agent import IntentAgent
from agents.planner.planner_agent import PlannerAgent


# Evaluation Dataset containing mock user requests
EVAL_DATASET = [
    {
        "query": "I want to search for sleeper buses from Bangalore to Chennai on 2026-06-29",
        "expected_intent": "search_bus",
        "expected_entities": {
            "origin": "Bangalore",
            "destination": "Chennai",
            "travel_date": "2026-06-29"
        },
        "required_tasks": ["search_buses", "recommend_options"]
    },
    {
        "query": "Please confirm my held booking 123",
        "expected_intent": "confirm_booking",
        "expected_entities": {
            "booking_id": 123
        },
        "required_tasks": []
    },
    {
        "query": "Cancel my booking with PNR B12345",
        "expected_intent": "cancel_bus",
        "expected_entities": {
            "pnr": "B12345"
        },
        "required_tasks": []
    },
    {
        "query": "Is my bus on time for PNR AX9212?",
        "expected_intent": "monitor_journey",
        "expected_entities": {
            "pnr": "AX9212"
        },
        "required_tasks": []
    },
    {
        "query": "Hello there, can you help me?",
        "expected_intent": "general_chat",
        "expected_entities": {},
        "required_tasks": []
    }
]


class EvaluationRunner:
    def __init__(self):
        self.model_router = ModelRouter()
        self.prompt_loader = PromptLoader()
        self.intent_agent = IntentAgent(self.model_router, self.prompt_loader)
        self.planner_agent = PlannerAgent(self.model_router, self.prompt_loader)

    def run_eval(self) -> Dict[str, Any]:
        print("==================================================")
        print("    TravelOps AI - Swarm Evaluation Pipeline     ")
        print("==================================================")
        
        results = []
        intent_matches = 0
        entity_matches = 0
        successful_workflows = 0
        total_latency = 0.0
        total_cost = 0.0

        for idx, item in enumerate(EVAL_DATASET):
            print(f"\n[Case {idx+1}] Input: \"{item['query']}\"")
            start_time = time.time()
            
            # 1. Intent Parsing Evaluation
            intent_res = self.intent_agent.parse_intent(item["query"])
            latency = time.time() - start_time
            total_latency += latency
            
            # Read LLM metrics
            metrics = self.model_router.get_metrics()
            case_cost = sum(m.get("estimated_cost_usd", 0.0) for m in metrics[-2:]) if metrics else 0.0
            total_cost += case_cost

            # Check matches
            parsed_intent = intent_res.get("primary_intent")
            parsed_entities = intent_res.get("entities", {})
            
            intent_ok = parsed_intent == item["expected_intent"]
            if intent_ok:
                intent_matches += 1

            # Validate key entity matching (like origin and destination check if expected)
            entity_ok = True
            for k, val in item["expected_entities"].items():
                parsed_val = parsed_entities.get(k)
                # Handle cases where parsed val is string or cast string
                if str(parsed_val).lower() != str(val).lower():
                    entity_ok = False
            
            if entity_ok:
                entity_matches += 1

            # 2. Workflow Validation (only for search_bus task graphs)
            workflow_ok = True
            if parsed_intent == "search_bus":
                pref_str = "highest_rating"
                plan = self.planner_agent.generate_plan(
                    parsed_entities.get("origin", "Bangalore"),
                    parsed_entities.get("destination", "Chennai"),
                    parsed_entities.get("travel_date", "2026-06-29"),
                    pref_str
                )
                
                # Check graph shape
                tasks = plan.get("tasks", [])
                task_names = [t.get("name") for t in tasks]
                
                # Fallback graphs can also satisfy requirements
                if tasks:
                    for req in item["required_tasks"]:
                        if req not in task_names:
                            workflow_ok = False
                else:
                    workflow_ok = False
                
                if workflow_ok:
                    successful_workflows += 1
            else:
                successful_workflows += 1 # Auto pass for non-planning intents
                
            print(f"  -> Parsed Intent: '{parsed_intent}' (Expected: '{item['expected_intent']}') -> {'PASS' if intent_ok else 'FAIL'}")
            print(f"  -> Entities OK:  {entity_ok} (Expected Match: {item['expected_entities']})")
            print(f"  -> Workflow OK:  {workflow_ok} (Required Tasks: {item['required_tasks']})")
            print(f"  -> Latency:      {latency:.3f}s | Cost: ${case_cost:.6f}")
            
            results.append({
                "query": item["query"],
                "intent_ok": intent_ok,
                "entity_ok": entity_ok,
                "workflow_ok": workflow_ok,
                "latency_sec": latency,
                "estimated_cost_usd": case_cost
            })

        # Calculate percentages
        dataset_size = len(EVAL_DATASET)
        intent_accuracy = (intent_matches / dataset_size) * 100
        entity_accuracy = (entity_matches / dataset_size) * 100
        workflow_success_rate = (successful_workflows / dataset_size) * 100
        avg_latency = total_latency / dataset_size

        summary = {
            "timestamp": time.time(),
            "total_cases": dataset_size,
            "intent_accuracy_pct": intent_accuracy,
            "entity_accuracy_pct": entity_accuracy,
            "workflow_success_rate_pct": workflow_success_rate,
            "avg_latency_sec": round(avg_latency, 3),
            "total_cost_usd": round(total_cost, 6)
        }

        print("\n==================================================")
        print("             WORKFLOW EVALUATION SUMMARY          ")
        print("==================================================")
        print(f"  Total Cases:           {summary['total_cases']}")
        print(f"  Intent Accuracy:       {summary['intent_accuracy_pct']:.1f}%")
        print(f"  Entity Accuracy:       {summary['entity_accuracy_pct']:.1f}%")
        print(f"  Workflow Success Rate: {summary['workflow_success_rate_pct']:.1f}%")
        print(f"  Avg Case Latency:      {summary['avg_latency_sec']:.3f}s")
        print(f"  Total Run Cost:        ${summary['total_cost_usd']:.6f}")
        print("==================================================")

        # Write results to JSON
        os.makedirs("observability", exist_ok=True)
        with open("observability/eval_results.json", "w") as f:
            json.dump({"summary": summary, "cases": results}, f, indent=2)
        print("Results exported successfully to 'observability/eval_results.json'")
        
        return summary


if __name__ == "__main__":
    runner = EvaluationRunner()
    runner.run_eval()
