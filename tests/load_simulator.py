import os
import sys
import time
import asyncio
import argparse
from typing import List, Dict, Any
import httpx

# Add project root directory to path to resolve imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.api.main import app

class LoadSimulator:
    def __init__(self, concurrency_levels: List[int]):
        self.concurrency_levels = concurrency_levels
        self.base_url = "http://testserver"

    async def run_single_user_workflow(self, client: httpx.AsyncClient, user_idx: int) -> Dict[str, Any]:
        """Simulates the full user journey: Register -> Login -> Session -> Message -> Poll Finish."""
        email = f"load_user_{user_idx}_{int(time.time())}@travelops.com"
        password = "Password123!"
        name = f"Load User {user_idx}"
        
        start_time = time.time()
        metrics = {
            "success": False,
            "latency": 0.0,
            "steps_completed": 0,
            "error": None
        }

        try:
            # Step 1: Register User
            reg_res = await client.post(
                "/api/auth/register",
                json={"email": email, "password": password, "name": name}
            )
            if reg_res.status_code != 201:
                raise Exception(f"Registration failed: {reg_res.text}")
            metrics["steps_completed"] += 1

            # Step 2: Login User
            login_res = await client.post(
                "/api/auth/login",
                json={"email": email, "password": password}
            )
            if login_res.status_code != 200:
                raise Exception(f"Login failed: {login_res.text}")
            tokens = login_res.json()
            headers = {"Authorization": f"Bearer {tokens['access_token']}"}
            metrics["steps_completed"] += 1

            # Step 3: Create Operations Session
            session_id = f"load_sess_{user_idx}_{int(time.time())}"
            sess_res = await client.post(
                "/api/sessions",
                json={"session_id": session_id},
                headers=headers
            )
            if sess_res.status_code != 200:
                raise Exception(f"Session creation failed: {sess_res.text}")
            metrics["steps_completed"] += 1

            # Step 4: Send Journey Request Message
            msg_res = await client.post(
                f"/api/sessions/{session_id}/message",
                json={"message": "I prefer SRS Travels and want the cheapest bus from Bangalore to Hyderabad tomorrow."},
                headers=headers
            )
            if msg_res.status_code != 200:
                raise Exception(f"Sending message failed: {msg_res.text}")
            metrics["steps_completed"] += 1

            # Step 5: Start Concurrent Workflow Orchestrator Execution
            run_res = await client.post(
                f"/api/sessions/{session_id}/run",
                headers=headers
            )
            if run_res.status_code != 200:
                raise Exception(f"Launching workflow failed: {run_res.text}")
            metrics["steps_completed"] += 1

            # Step 6: Poll for completion
            # (In memory, the background task runs on the same loop. We await/sleep and poll)
            max_polls = 10
            completed = False
            for _ in range(max_polls):
                await asyncio.sleep(0.5)
                detail_res = await client.get(f"/api/sessions/{session_id}", headers=headers)
                if detail_res.status_code == 200:
                    data = detail_res.json()
                    wf_state = data.get("workflow_state")
                    if wf_state in ["OPTIONS_FOUND", "BOOKED", "COMPLETED"]:
                        completed = True
                        metrics["steps_completed"] += 1
                        break
                    elif wf_state == "FAILED":
                        raise Exception("Orchestrator state transitioned to FAILED.")
            
            if not completed:
                raise Exception("Workflow execution timed out during polling.")

            metrics["success"] = True
            metrics["latency"] = time.time() - start_time

        except Exception as e:
            metrics["error"] = str(e)
            metrics["latency"] = time.time() - start_time
            
        return metrics

    async def execute_concurrency_tier(self, tier: int):
        """Spawns concurrent user workers for a given load tier."""
        print(f"\n--- Testing Concurrency Level: {tier} Users ---")
        
        # We use httpx AsyncClient with app routing directly in-memory to prevent actual network socket limits
        async with httpx.AsyncClient(app=app, base_url=self.base_url, timeout=30.0) as client:
            tasks = [self.run_single_user_workflow(client, idx) for idx in range(tier)]
            
            start_tier_time = time.time()
            results = await asyncio.gather(*tasks)
            total_tier_time = time.time() - start_tier_time

            # Compute tier metrics
            successful = [r for r in results if r["success"]]
            latencies = [r["latency"] for r in results if r["success"]]
            
            avg_latency = sum(latencies) / len(latencies) if latencies else 0.0
            p95_latency = sorted(latencies)[int(len(latencies) * 0.95)] if latencies else 0.0
            error_count = len(results) - len(successful)
            error_rate = (error_count / tier) * 100
            throughput = len(successful) / total_tier_time if total_tier_time > 0 else 0.0

            print(f"  Total Time:     {total_tier_time:.2f}s")
            print(f"  Successful:     {len(successful)}/{tier}")
            print(f"  Throughput:     {throughput:.2f} journeys/sec")
            print(f"  Avg Latency:    {avg_latency:.2f}s")
            print(f"  P95 Latency:    {p95_latency:.2f}s")
            print(f"  Error Rate:     {error_rate:.1f}%")
            
            if error_count > 0:
                print("  Sample errors:")
                errors = list(set([r["error"] for r in results if r["error"]]))[:3]
                for err in errors:
                    print(f"    - {err}")

    async def run(self):
        print("==================================================")
        print("     TravelOps AI - Production Load Simulator     ")
        print("==================================================")
        for tier in self.concurrency_levels:
            await self.execute_concurrency_tier(tier)
            await asyncio.sleep(1.0)
        print("\n==================================================")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="TravelOps AI Load Simulator")
    parser.add_argument("--concurrency", type=str, default="20,50", help="Comma-separated load tiers (e.g. 20,50,100)")
    args = parser.parse_url_args = parser.parse_args()
    
    tiers = [int(x.strip()) for x in args.concurrency.split(",")]
    asyncio.run(LoadSimulator(tiers).run())
