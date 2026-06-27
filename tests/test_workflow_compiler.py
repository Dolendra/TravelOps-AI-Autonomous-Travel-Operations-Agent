import os
import sys
import unittest
from typing import Dict, Any

# Add root folder to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.workflows.compiler import WorkflowCompiler

class TestWorkflowCompiler(unittest.TestCase):
    def test_search_and_recommend_compilation(self):
        variables = {
            "origin": "Bangalore",
            "destination": "Hyderabad",
            "travel_date": "2026-07-01",
            "preferences": "cheapest"
        }
        
        # Compile search_and_recommend workflow
        tasks = WorkflowCompiler.compile_workflow("search_and_recommend", variables)
        
        self.assertEqual(len(tasks), 2)
        
        # Verify first task
        t1 = tasks[0]
        self.assertEqual(t1["task_id"], "search_1")
        self.assertEqual(t1["name"], "search_buses")
        self.assertEqual(t1["dependencies"], [])
        self.assertEqual(t1["input_data"]["origin"], "Bangalore")
        self.assertEqual(t1["input_data"]["destination"], "Hyderabad")
        self.assertEqual(t1["input_data"]["travel_date"], "2026-07-01")
        
        # Verify second task
        t2 = tasks[1]
        self.assertEqual(t2["task_id"], "recommend_1")
        self.assertEqual(t2["name"], "recommend_options")
        self.assertEqual(t2["dependencies"], ["search_1"])
        self.assertEqual(t2["input_data"]["preferences"], "cheapest")

    def test_full_booking_parameter_substitution(self):
        variables = {
            "origin": "Delhi",
            "destination": "Jaipur",
            "travel_date": "2026-07-02",
            "preferences": "highest_rating",
            "bus_id": "bus_101",
            "seat_number": "12B",
            "amount": 750.50,
            "idempotency_key": "idem_12345",
            "booking_id": "book_9876",
            "email": "traveler@example.com"
        }
        
        tasks = WorkflowCompiler.compile_workflow("full_booking", variables)
        self.assertEqual(len(tasks), 6)
        
        # Verify that hold_seat resolved parameters
        hold_task = next(t for t in tasks if t["name"] == "hold_seat")
        self.assertEqual(hold_task["input_data"]["bus_id"], "bus_101")
        self.assertEqual(hold_task["input_data"]["seat_number"], "12B")
        
        # Verify that process_payment resolved float amount
        payment_task = next(t for t in tasks if t["name"] == "process_payment")
        self.assertEqual(payment_task["input_data"]["amount"], 750.50)
        self.assertEqual(payment_task["input_data"]["idempotency_key"], "idem_12345")
        
        # Verify nested string interpolation in notification
        notify_task = next(t for t in tasks if t["name"] == "send_notification")
        self.assertEqual(notify_task["input_data"]["recipient"], "traveler@example.com")
        self.assertIn("Bus bus_101", notify_task["input_data"]["message"])
        self.assertIn("Seat 12B", notify_task["input_data"]["message"])

    def test_cycle_detection(self):
        # Construct task graph with circular dependency: task_1 -> task_2 -> task_1
        circular_tasks = [
            {
                "task_id": "task_1",
                "name": "search_buses",
                "dependencies": ["task_2"],
                "input_data": {}
            },
            {
                "task_id": "task_2",
                "name": "recommend_options",
                "dependencies": ["task_1"],
                "input_data": {}
            }
        ]
        
        with self.assertRaises(ValueError) as ctx:
            WorkflowCompiler._validate_acyclic(circular_tasks)
        
        self.assertIn("Circular dependency detected", str(ctx.exception))

    def test_nonexistent_workflow_failure(self):
        with self.assertRaises(FileNotFoundError):
            WorkflowCompiler.compile_workflow("non_existent_journey_flow", {})

if __name__ == "__main__":
    unittest.main()
