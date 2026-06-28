import os
import sys
import time
import asyncio

# Add root folder to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.runtime.workflow.compiler import WorkflowCompiler
from backend.runtime.workflow.executor import WorkflowExecutor
from backend.database.db import init_db, SessionLocal
from backend.database.models import TaskStateModel
from backend.tools import travel_tools

async def run_benchmark():
    print("[*] Starting TravelOps AI Engine benchmark profile...")
    init_db()
    
    # 1. Compile DSL Workflow
    print("[*] Compiling full_booking.yaml DSL Graph (Dry run test)...")
    test_vars = {
        "origin": "Bangalore",
        "destination": "Hyderabad",
        "travel_date": "2026-06-29",
        "passenger_name": "Test",
        "passenger_email": "test@test.com",
        "seat_number": "1A",
        "bus_id": 1,
        "amount": 950.0,
        "recipient": "test@test.com",
        "message": "Confirmed",
        "operator_preference": "VRL Travels"
    }
    start_compile = time.time()
    test_tasks = WorkflowCompiler.compile_workflow("full_booking", test_vars)
    compile_time_ms = (time.time() - start_compile) * 1000
    print(f"[OK] Compiled {len(test_tasks)} nodes in {compile_time_ms:.2f} ms")
    
    # 2. Concurrent execution wave benchmark (5 sessions)
    concurrency_limit = 5
    print(f"\n[*] Executing {concurrency_limit} concurrent workflows...")
    db = SessionLocal()
    session_ids_run = []
    tasks_futures = []
    
    start_exec = time.time()
    for i in range(concurrency_limit):
        s_id = f"bench_sess_{i}_{int(time.time())}"
        session_ids_run.append(s_id)
        
        # Build unique session variables
        session_variables = {
            "origin": "Bangalore",
            "destination": "Hyderabad",
            "travel_date": "2026-06-29",
            "passenger_name": f"Passenger {i}",
            "passenger_email": f"passenger{i}@example.com",
            "seat_number": f"{i+1}A",  # Unique seat per session!
            "bus_id": 1,
            "amount": 950.0,
            "card_number": "4111 1111 1111 1111",
            "idempotency_key": f"idem_bench_{i}_{int(time.time())}",
            "recipient": f"passenger{i}@example.com",
            "message": "Booking confirmed",
            "operator_preference": "VRL Travels"
        }
        
        compiled_tasks = WorkflowCompiler.compile_workflow("full_booking", session_variables)
        
        # Prepare execution tasks records in database
        for t in compiled_tasks:
            db_task = TaskStateModel(
                session_id=s_id,
                task_id=t["task_id"],
                name=t["name"],
                status="PENDING"
            )
            db_task.set_dependencies(t["dependencies"])
            db_task.set_input(t["input_data"])
            db.add(db_task)
        
        db.commit()
        
        # Stagger executor starts to prevent SQLite write lock collisions
        async def run_staggered(sess_id, delay):
            await asyncio.sleep(delay)
            return await WorkflowExecutor.execute_graph(sess_id)
        
        tasks_futures.append(run_staggered(s_id, i * 0.6))
        
    db.close()
    
    # Wait for all runs
    await asyncio.gather(*tasks_futures, return_exceptions=True)
    total_exec_time = time.time() - start_exec
    
    # Verify outcomes via database query
    db = SessionLocal()
    from backend.database.models import WorkflowStateModel
    success_count = 0
    for s_id in session_ids_run:
        ws = db.query(WorkflowStateModel).filter(WorkflowStateModel.session_id == s_id).order_by(WorkflowStateModel.updated_at.desc()).first()
        if ws and ws.state in ["BOOKED", "COMPLETED"]:
            success_count += 1
    db.close()
    
    failure_count = concurrency_limit - success_count
    
    throughput = concurrency_limit / total_exec_time
    avg_latency = total_exec_time / concurrency_limit
    
    print("\n==================================================")
    print(" TRAVELOPS AI RUNTIME BENCHMARK REPORT")
    print("==================================================")
    print(f"Concurrency Count  : {concurrency_limit} concurrent runs")
    print(f"Total Execution Time: {total_exec_time:.2f} seconds")
    print(f"Throughput         : {throughput:.2f} completed workflows/sec")
    print(f"Average Latency    : {avg_latency:.2f} seconds/workflow")
    print(f"Succeeded Runs     : {success_count}")
    print(f"Failed Runs        : {failure_count}")
    print("--------------------------------------------------")
    print("[OK] Benchmark profiling complete!")

if __name__ == "__main__":
    asyncio.run(run_benchmark())
