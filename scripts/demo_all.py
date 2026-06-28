import os
import sys
import asyncio
import time

# Add root folder to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.database.db import init_db
from scripts.reset_db import reset_database
from scripts.simulate_booking import run_success_booking
from scripts.simulate_provider_failure import run_provider_failover
from scripts.simulate_payment_failure import run_payment_failure
from scripts.simulate_disruption import run_disruption
from scripts.seed_demo_dataset import seed_dataset
from scripts.generate_metrics import print_evaluation_report

async def run_master_demo():
    print("==================================================")
    print(" STARTING MASTER DEMO SCENARIO PIPELINE")
    print("==================================================")
    start_time = time.time()
    
    # 1. Reset database schemas
    reset_database()
    
    # 2. Run Scenario 1: Standard Success Booking
    await run_success_booking()
    
    # 3. Run Scenario 2: Provider Outage Failover
    await run_provider_failover()
    
    # 4. Run Scenario 3: Payment Luhn failure & compensating Saga
    await run_payment_failure()
    
    # 5. Run Scenario 4: Journey cancel detection and autonomous rebooking
    await run_disruption()
    
    # 6. Seed remaining records for Studio history dashboard logs
    print("\n[*] Populating historical database records for Studio dashboards...")
    seed_dataset()
    
    # 7. Print final evaluation report metrics
    print_evaluation_report()
    
    duration = time.time() - start_time
    print(f"\n[OK] Master Demo Pipeline completed successfully in {duration:.2f} seconds!")
    print("     Access the TravelOps AI Studio at http://localhost:5173 to review sessions.")
    print("==================================================")

if __name__ == "__main__":
    init_db()
    asyncio.run(run_master_demo())
