import time
import sys
import os

# Add the SDK folder to path for import
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "travelops-sdk")))

from travelops_sdk import TravelOpsClient, TravelOpsError, AuthError


def main():
    print("==================================================")
    print("TravelOps AI — Python Client SDK Integration Demo")
    print("==================================================")

    # 1. Initialize Client
    client = TravelOpsClient(base_url="http://localhost:8000")

    # 2. Check Health
    try:
        health = client.get_health()
        print(f"[*] API Health: {health['status']} (Configured: {health.get('api_key_configured')})")
    except TravelOpsError as e:
        print(f"[!] Health check failed: {e}")
        print("[!] Ensure the backend FastAPI server is running on http://localhost:8000.")
        sys.exit(1)

    # 3. Create unique credentials
    timestamp = int(time.time())
    email = f"admin_sdk_{timestamp}@travelops.ai"
    password = f"SecurePass_{timestamp}"
    name = f"SDK Admin {timestamp}"

    # 4. Register new Admin
    print(f"[*] Registering admin account: {email}")
    try:
        reg_res = client.register(email=email, password=password, name=name, role="admin")
        print(f"[*] Registration response: {reg_res}")
    except TravelOpsError as e:
        print(f"[!] Registration failed: {e}")
        sys.exit(1)

    # 5. Log in to get Authorization context
    print("[*] Logging in...")
    try:
        client.login(email=email, password=password)
        print("[*] Authorization token successfully retrieved.")
    except AuthError as e:
        print(f"[!] Login failed: {e}")
        sys.exit(1)

    # 6. Create Session
    session_id = f"sess_sdk_{timestamp}"
    print(f"[*] Initializing operations session: {session_id}")
    try:
        session = client.create_session(session_id=session_id)
        print(f"[*] Session created: {session}")
    except TravelOpsError as e:
        print(f"[!] Session creation failed: {e}")
        sys.exit(1)

    # 7. Send Message (Search Query)
    print("[*] Sending bus search message...")
    try:
        msg_res = client.send_message(
            session_id=session_id,
            message="Search for a sleeper bus from Bangalore to Chennai tomorrow"
        )
        print(f"[*] Assistant response: {msg_res['response']}")
        print(f"[*] Intent parsed: {msg_res['intent']['primary_intent']} (Confidence: {msg_res['intent']['confidence']})")
    except TravelOpsError as e:
        print(f"[!] Sending message failed: {e}")
        sys.exit(1)

    # 8. Check Session Details
    try:
        details = client.get_session_details(session_id)
        print(f"[*] Session Current State: {details.workflow_state}")
        print(f"[*] Session Tasks Generated: {len(details.tasks)}")
        for t in details.tasks:
            print(f"    - Task [{t.task_id}]: {t.name} (Status: {t.status})")
    except TravelOpsError as e:
        print(f"[!] Fetching details failed: {e}")
        sys.exit(1)

    # 9. Run Session Workflow Orchestration
    print("[*] Running planned task DAG...")
    try:
        run_res = client.run_session_workflow(session_id)
        print(f"[*] Run response: {run_res}")
    except TravelOpsError as e:
        print(f"[!] Running workflow failed: {e}")
        sys.exit(1)

    # Poll status for a few seconds to see execution progress
    print("[*] Polling task execution status...")
    for i in range(5):
        time.sleep(1.5)
        try:
            details = client.get_session_details(session_id)
            print(f"    State at poll #{i+1}: {details.workflow_state}")
            completed_tasks = [t.name for t in details.tasks if t.status == "COMPLETED"]
            print(f"    Completed tasks: {', '.join(completed_tasks) or 'None'}")
            if details.workflow_state in ["BOOKED", "FAILED"]:
                break
        except TravelOpsError:
            pass

    # 10. Publish Disruption (Event Bus telemetry test)
    print("[*] Simulating bus cancelled disruption telemetry...")
    try:
        event_payload = {
            "session_id": session_id,
            "operator_name": "VRL Travels",
            "route_id": "route_blr_che_1",
            "cancelled_at": "2026-06-29T20:00:00Z"
        }
        pub_res = client.publish_event(event_type="BusCancelled", payload=event_payload)
        print(f"[*] Disruption event published: {pub_res}")
    except TravelOpsError as e:
        print(f"[!] Event publishing failed: {e}")
        sys.exit(1)

    # 11. Query Observability Telemetry
    print("[*] Fetching platform metrics...")
    try:
        metrics = client.get_observability_metrics()
        print(f"[*] Global total LLM cost (USD): {metrics.total_cost_usd}")
        print(f"[*] Total registered tools: {metrics.registered_tools_count}")
    except TravelOpsError as e:
        print(f"[!] Fetching metrics failed: {e}")
        sys.exit(1)

    # 12. Query live AI Evaluation accuracies
    print("[*] Fetching dynamic evaluation accuracies...")
    try:
        eval_metrics = client.get_evaluation_metrics()
        print(f"[*] Intent Accuracy: {eval_metrics.intent_accuracy}%")
        print(f"[*] Entity Parsing Accuracy: {eval_metrics.entity_accuracy}%")
        print(f"[*] Auto-Recovery Success Rate: {eval_metrics.recovery_success_rate}%")
        print(f"[*] Average Latency (sec): {eval_metrics.avg_latency_sec}")
    except TravelOpsError as e:
        print(f"[!] Fetching evaluation failed: {e}")
        sys.exit(1)

    print("\n[+] SUCCESS: SDK Verification walkthrough completed successfully!")
    print("==================================================")


if __name__ == "__main__":
    main()
