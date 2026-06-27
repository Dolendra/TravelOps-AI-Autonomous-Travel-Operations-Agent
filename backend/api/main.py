import os
import json
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional
from fastapi import FastAPI, Depends, HTTPException, BackgroundTasks, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session
import time
import uuid
import contextvars

from backend.database.db import init_db, SessionLocal, get_db
from backend.database.models import (
    SessionModel, WorkflowStateModel, TaskStateModel, AuditLogModel, EventStoreModel, UserModel
)
from backend.api.auth import router as auth_router, get_current_user, require_role
from backend.services.llm import ModelRouter
from backend.services.prompt_loader import PromptLoader
from backend.events.event_bus import EventBus
from backend.tools.registry import ToolRegistry
from agents.intent.intent_agent import IntentAgent
from agents.planner.planner_agent import PlannerAgent
from agents.memory.memory_agent import MemoryAgent
from backend.runtime.workflow.executor import WorkflowExecutor as WorkflowOrchestrator
from backend.runtime.context.builder import PromptContextBuilder
from backend.services.guardrails import GuardrailsProcessor
from backend.services.rag import RAGEngine
import backend.tools.travel_tools

# Logging setup
logger = logging.getLogger("travelops.api.main")
logging.basicConfig(level=logging.INFO)

app = FastAPI(
    title="TravelOps AI – Autonomous Travel Operations Platform (Production v2.0)",
    description=(
        "Enterprise-grade production release gateway for TravelOps AI. "
        "Includes Intent Runtime, Declarative Workflows, Saga Transaction rollbacks, "
        "Real-World Integrations (Maps & Weather API), SMTP/Twilio Notifications Gateway, "
        "and LLM-powered context cached generation with explanation engine."
    ),
    version="2.0.0",
    license_info={
        "name": "Apache 2.0",
        "url": "https://www.apache.org/licenses/LICENSE-2.0.html",
    },
    openapi_tags=[
        {
            "name": "Auth",
            "description": "User authentication, JWT login/registration, role management, and validation.",
        },
        {
            "name": "Core",
            "description": "Autonomous travel planner, intent resolution engine, memory context manager, and dynamic prompt orchestration.",
        },
        {
            "name": "Workflow",
            "description": "DAG Compiler, task-level execution graph runner, reflection agent, and manual operator approval portals.",
        },
        {
            "name": "Telemetry",
            "description": "Audit trail events logs, real-time status feeds, database transactional diagnostics, and Prometheus runtime metrics.",
        }
    ]
)

# CORS middleware for React + Vite Frontend connection
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Custom Rate Limiter
class RateLimiter:
    def __init__(self, requests_limit: int = 150, window_seconds: int = 60):
        self.requests_limit = requests_limit
        self.window_seconds = window_seconds
        self.client_records = {}

    def check_rate_limit(self, client_ip: str):
        now = time.time()
        if client_ip not in self.client_records:
            self.client_records[client_ip] = []
        
        timestamps = [t for t in self.client_records[client_ip] if now - t < self.window_seconds]
        self.client_records[client_ip] = timestamps
        
        if len(timestamps) >= self.requests_limit:
            raise HTTPException(
                status_code=429,
                detail="Rate limit exceeded. Please wait before retrying."
            )
        self.client_records[client_ip].append(now)

limiter = RateLimiter(requests_limit=150, window_seconds=60)
request_counter = 0
request_trace_id = contextvars.ContextVar("trace_id", default="")

@app.middleware("http")
async def add_trace_id_and_count_middleware(request: Request, call_next):
    global request_counter
    if request.url.path not in ["/metrics", "/health"]:
        request_counter += 1
    
    trace_id = request.headers.get("X-Trace-ID") or f"trace_{uuid.uuid4().hex[:12]}"
    token = request_trace_id.set(trace_id)
    
    logger.info(f"[{trace_id}] Incoming request: {request.method} {request.url.path}")
    
    response = await call_next(request)
    response.headers["X-Trace-ID"] = trace_id
    
    logger.info(f"[{trace_id}] Outgoing response: {response.status_code}")
    
    request_trace_id.reset(token)
    return response

@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    client_ip = request.client.host if request.client else "unknown"
    if request.url.path in ["/metrics", "/health"]:
        return await call_next(request)
    try:
        limiter.check_rate_limit(client_ip)
    except HTTPException as exc:
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
    return await call_next(request)

app.include_router(auth_router)

# Startup DB initialization
@app.on_event("startup")
def startup_event():
    logger.info("Initializing SQLite database tables...")
    init_db()
    logger.info("Database initialization complete.")
    
    # Register Phase 4 autonomous event subscribers on the EventBus
    import asyncio
    from agents.monitor.journey_monitor import JourneyMonitor
    from agents.recovery.recovery_agent import RecoveryAgent
    from backend.events.webhooks import WebhookDispatcher
    
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.get_event_loop()
        
    loop.create_task(EventBus.subscribe("BusCancelled", JourneyMonitor.handle_bus_cancelled))
    loop.create_task(EventBus.subscribe("BusDelayed", JourneyMonitor.handle_bus_delayed))
    loop.create_task(EventBus.subscribe("DisruptionDetected", RecoveryAgent.handle_disruption))
    
    # Subscribe webhook alert dispatches
    loop.create_task(EventBus.subscribe("BusCancelled", WebhookDispatcher.dispatch_event_to_all))
    loop.create_task(EventBus.subscribe("BusDelayed", WebhookDispatcher.dispatch_event_to_all))
    loop.create_task(EventBus.subscribe("DisruptionDetected", WebhookDispatcher.dispatch_event_to_all))
    
    logger.info("Successfully registered Phase 4 and Webhook autonomous event subscribers.")


# Instantiations
model_router = ModelRouter()
prompt_loader = PromptLoader()

from backend.runtime.agent_runtime import AgentRuntime
from agents.intent.intent_agent import IntentAgent
from agents.planner.planner_agent import PlannerAgent
from agents.memory.memory_agent import MemoryAgent
from agents.monitor.journey_monitor import JourneyMonitor
from agents.recovery.recovery_agent import RecoveryAgent
from agents.reflection.reflection_agent import ReflectionAgent

agent_runtime = AgentRuntime(model_router, prompt_loader)
agent_runtime.register_agent("IntentAgent", "2.0.0", ["intent"], IntentAgent(model_router, prompt_loader))
agent_runtime.register_agent("PlannerAgent", "2.0.0", ["plan", "compile"], PlannerAgent(model_router, prompt_loader))
agent_runtime.register_agent("MemoryAgent", "2.0.0", ["memory"], MemoryAgent(model_router, prompt_loader))
agent_runtime.register_agent("JourneyMonitor", "2.0.0", ["monitor"], JourneyMonitor)
agent_runtime.register_agent("RecoveryAgent", "2.0.0", ["recovery"], RecoveryAgent)
agent_runtime.register_agent("ReflectionAgent", "2.0.0", ["reflection"], ReflectionAgent(model_router, prompt_loader))

# Helper to convert naive UTC datetimes to timezone-explicit strings
def to_iso_utc(dt):
    if dt is None:
        return None
    return dt.isoformat() + "Z"

# Request/Response Schemas
class SessionCreate(BaseModel):
    session_id: Optional[str] = None

class MessageRequest(BaseModel):
    message: str

class ExecuteTaskRequest(BaseModel):
    tool_name: str
    arguments: Dict[str, Any]

class PublishEventRequest(BaseModel):
    event_type: str
    payload: Dict[str, Any]

class ApproveRequest(BaseModel):
    task_id: str


# 1. Health Endpoint
@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "api_key_configured": model_router.api_key is not None
    }


@app.get("/metrics")
def get_metrics_endpoint(db: Session = Depends(get_db)):
    metrics_list = []
    
    # 1. Active sessions count
    session_count = db.query(SessionModel).count()
    metrics_list.append(f"# HELP travelops_active_sessions_total Total number of active operations sessions.")
    metrics_list.append(f"# TYPE travelops_active_sessions_total gauge")
    metrics_list.append(f"travelops_active_sessions_total {session_count}")

    # 2. LLM Calls metrics
    llm_metrics = model_router.get_metrics()
    total_calls = len(llm_metrics)
    success_calls = sum(1 for m in llm_metrics if m.get("status") == "success")
    error_calls = sum(1 for m in llm_metrics if m.get("status") == "error")
    total_cost = sum(m.get("estimated_cost_usd", 0.0) for m in llm_metrics)
    
    metrics_list.append(f"# HELP travelops_llm_calls_total Total number of LLM calls made.")
    metrics_list.append(f"# TYPE travelops_llm_calls_total counter")
    metrics_list.append(f"travelops_llm_calls_total {total_calls}")

    metrics_list.append(f"# HELP travelops_llm_calls_success_total Total successful LLM calls.")
    metrics_list.append(f"# TYPE travelops_llm_calls_success_total counter")
    metrics_list.append(f"travelops_llm_calls_success_total {success_calls}")

    metrics_list.append(f"# HELP travelops_llm_calls_error_total Total failed LLM calls.")
    metrics_list.append(f"# TYPE travelops_llm_calls_error_total counter")
    metrics_list.append(f"travelops_llm_calls_error_total {error_calls}")

    metrics_list.append(f"# HELP travelops_llm_cost_usd_total Accumulated USD token cost of LLM routing.")
    metrics_list.append(f"# TYPE travelops_llm_cost_usd_total counter")
    metrics_list.append(f"travelops_llm_cost_usd_total {total_cost:.6f}")

    # 3. Tool execution failures
    failed_tasks = db.query(TaskStateModel).filter(TaskStateModel.status == "FAILED").count()
    metrics_list.append(f"# HELP travelops_tool_execution_failures_total Total number of tool tasks that transitioned to FAILED status.")
    metrics_list.append(f"# TYPE travelops_tool_execution_failures_total counter")
    metrics_list.append(f"travelops_tool_execution_failures_total {failed_tasks}")

    # 4. HTTP requests count
    metrics_list.append(f"# HELP travelops_api_requests_total Total number of HTTP gateway API requests processed.")
    metrics_list.append(f"# TYPE travelops_api_requests_total counter")
    metrics_list.append(f"travelops_api_requests_total {request_counter}")

    return PlainTextResponse("\n".join(metrics_list) + "\n")


# 2. Session Management
@app.post("/api/sessions")
def create_session(session_req: SessionCreate, db: Session = Depends(get_db), current_user: UserModel = Depends(get_current_user)):
    # Generate session ID if not provided
    s_id = session_req.session_id or f"sess_{int(datetime.utcnow().timestamp())}"
    
    # Check if session already exists
    exists = db.query(SessionModel).filter(SessionModel.session_id == s_id).first()
    if exists:
        return {"session_id": s_id, "created_at": to_iso_utc(exists.created_at), "status": "existing"}
    
    # Create session
    new_sess = SessionModel(session_id=s_id, user_id=current_user.id)
    db.add(new_sess)
    
    # Create initial workflow state
    init_state = WorkflowStateModel(session_id=s_id, state="NEW")
    db.add(init_state)
    
    # Audit log
    audit = AuditLogModel(
        session_id=s_id,
        agent_name="System",
        action="session_created",
        reasoning_summary="Session created and workflow state initialized to NEW."
    )
    db.add(audit)
    
    db.commit()
    db.refresh(new_sess)
    return {"session_id": s_id, "created_at": to_iso_utc(new_sess.created_at), "status": "created"}


@app.get("/api/sessions")
def list_sessions(db: Session = Depends(get_db), current_user: UserModel = Depends(get_current_user)):
    if current_user.role == "admin":
        sessions = db.query(SessionModel).order_by(SessionModel.created_at.desc()).all()
    else:
        sessions = db.query(SessionModel).filter(SessionModel.user_id == current_user.id).order_by(SessionModel.created_at.desc()).all()
    return [{"session_id": s.session_id, "created_at": to_iso_utc(s.created_at)} for s in sessions]


@app.get("/api/sessions/{session_id}")
def get_session_details(session_id: str, db: Session = Depends(get_db), current_user: UserModel = Depends(get_current_user)):
    # Verify session exists
    session = db.query(SessionModel).filter(SessionModel.session_id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
        
    # Enforce user/session ownership
    if current_user.role != "admin" and session.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied: You do not own this session.")
        
    # Get current state
    state_entry = db.query(WorkflowStateModel).filter(
        WorkflowStateModel.session_id == session_id
    ).order_by(WorkflowStateModel.updated_at.desc()).first()
    current_state = state_entry.state if state_entry else "NEW"
    
    # Get tasks
    tasks = db.query(TaskStateModel).filter(TaskStateModel.session_id == session_id).all()
    task_list = []
    for t in tasks:
        task_list.append({
            "task_id": t.task_id,
            "name": t.name,
            "status": t.status,
            "dependencies": t.get_dependencies(),
            "input_data": t.get_input(),
            "output_data": t.get_output()
        })
        
    # Get conversation audit logs (messages)
    logs = db.query(AuditLogModel).filter(
        AuditLogModel.session_id == session_id
    ).order_by(AuditLogModel.created_at.asc()).all()
    
    conversation = []
    for log in logs:
        if log.agent_name in ["User", "Assistant", "System"]:
            conversation.append({
                "sender": log.agent_name,
                "message": log.reasoning_summary,
                "timestamp": to_iso_utc(log.created_at),
                "payload": log.get_payload()
            })
            
    return {
        "session_id": session_id,
        "created_at": to_iso_utc(session.created_at),
        "workflow_state": current_state,
        "tasks": task_list,
        "conversation": conversation
    }


# 3. Message Processing & Agent Orchestration
@app.post("/api/sessions/{session_id}/message")
def send_message(session_id: str, req: MessageRequest, db: Session = Depends(get_db), current_user: UserModel = Depends(get_current_user)):
    # Verify session exists
    session = db.query(SessionModel).filter(SessionModel.session_id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
        
    # Enforce user/session ownership
    if current_user.role != "admin" and session.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied: You do not own this session.")
        
    # Apply guardrails input sanitization (credit card/email masking, prompt injection block)
    try:
        sanitized_message = GuardrailsProcessor.sanitize_input(req.message)
    except ValueError as val_err:
        raise HTTPException(status_code=400, detail=str(val_err))

    # 1. Log User message
    user_log = AuditLogModel(
        session_id=session_id,
        agent_name="User",
        action="message",
        reasoning_summary=sanitized_message
    )
    db.add(user_log)
    db.commit()
    
    context_builder = PromptContextBuilder(model_router, prompt_loader)
    
    # Extract and save user preferences to Memory
    memory_agent = agent_runtime.get_agent_by_capability("memory")
    memory_agent.save_preference(session_id, sanitized_message)

    # Get current time for prompt resolution
    now = datetime.now()
    curr_date = now.strftime("%Y-%m-%d")
    
    # 2. Run Modular Intent Agent
    intent_agent = agent_runtime.get_agent_by_capability("intent")
    intent_data = intent_agent.parse_intent(sanitized_message)
    
    # Fallback to local parsing if LLM call yields empty dict
    if not intent_data or "primary_intent" not in intent_data:
        intent_data = mock_intent_parser(sanitized_message, curr_date)
        logger.info(f"Using mock intent parsing fallback: {intent_data}")
            
    # Audit log intent parsing
    intent_log = AuditLogModel(
        session_id=session_id,
        agent_name="IntentAgent",
        action="parse_intent",
        reasoning_summary=intent_data.get("reasoning_summary", "Parsed user intent.")
    )
    intent_log.set_payload(intent_data)
    db.add(intent_log)
    
    # 3. Update workflow state based on intent
    primary_intent = intent_data.get("primary_intent", "general_chat")
    state_mapping = {
        "search_bus": "SEARCHING",
        "book_bus": "BOOKING",
        "cancel_bus": "CANCELLED",
        "monitor_journey": "MONITORING",
        "get_status": "NEW"
    }
    new_state = state_mapping.get(primary_intent, "NEW")
    
    state_entry = WorkflowStateModel(session_id=session_id, state=new_state)
    db.add(state_entry)
    db.commit()
    
    # 4. Generate Response and potentially create Task Dependency Graph
    assistant_response = ""
    task_graph = None
    
    if primary_intent == "search_bus":
        # Create Task Dependency Graph using Planner Agent
        entities = intent_data.get("entities", {})
        origin = entities.get("origin")
        destination = entities.get("destination")
        travel_date = entities.get("travel_date")
        
        if not origin or not destination:
            assistant_response = "I noticed you want to search for a bus, but could you please specify the origin and destination?"
        else:
            # Retrieve saved preferences to customize planning
            prefs = memory_agent.retrieve_preferences(session_id)
            pref_list = []
            if prefs.get("operator_preference"):
                pref_list.append(f"operator: {prefs['operator_preference']}")
            if prefs.get("sorting_preference"):
                pref_list.append(f"sort: {prefs['sorting_preference']}")
            if prefs.get("seat_preference"):
                pref_list.append(f"seat: {prefs['seat_preference']}")
            pref_str = ", ".join(pref_list) if pref_list else "highest_rating"

            planner = agent_runtime.get_agent_by_capability("plan")
            task_graph = planner.generate_plan(origin, destination, travel_date or curr_date, pref_str, session_id=session_id)
            
            if not task_graph or "tasks" not in task_graph:
                logger.warning("Planner Agent yielded empty graph, falling back to mock planner.")
                task_graph = mock_planner(entities)
                # Inject sorting preference from memory into the mock recommend_options task input
                sorting_pref = prefs.get("sorting_preference") or "highest_rating"
                for task in task_graph.get("tasks", []):
                    if task.get("name") == "recommend_options":
                        task.setdefault("input_data", {})["preference"] = sorting_pref
            
            # Save task graph to database
            # Clear old tasks first
            db.query(TaskStateModel).filter(TaskStateModel.session_id == session_id).delete()
            
            for task in task_graph.get("tasks", []):
                t_model = TaskStateModel(
                    session_id=session_id,
                    task_id=task.get("task_id"),
                    name=task.get("name"),
                    status="PENDING"
                )
                t_model.set_dependencies(task.get("dependencies", []))
                t_model.set_input(task.get("input_data", {}))
                db.add(t_model)
                
            assistant_response = f"Sure! I've created a task dependency graph to search and book a bus from {origin} to {destination} on {travel_date or curr_date}."
            
            # Transition state to options found once graph is saved
            state_entry = WorkflowStateModel(session_id=session_id, state="OPTIONS_FOUND")
            db.add(state_entry)
            db.commit()
            
    elif primary_intent == "general_chat":
        # Search the local Knowledge Base FAQ first using RAG token Jaccard matching
        context = RAGEngine.get_matching_context(sanitized_message, top_k=1)
        
        if not model_router.api_key:
            if context:
                assistant_response = f"Based on our FAQ policies:\n\n{context}\n\nLet me know if you need help with anything else!"
            else:
                assistant_response = "Hello! I am TravelOps AI, your travel assistant. How can I help you check bus availability, book tickets, or track your journey today?"
        else:
            try:
                # Retrieve conversation history logs for Working Memory context
                history_logs = db.query(AuditLogModel).filter(
                    AuditLogModel.session_id == session_id,
                    AuditLogModel.action == "message"
                ).order_by(AuditLogModel.created_at.asc()).all()
                
                chat_history = []
                for log in history_logs:
                    role = "Assistant" if log.agent_name == "Assistant" else "User"
                    chat_history.append({"sender": role, "message": log.reasoning_summary or ""})

                # Build support messages using PromptContextBuilder
                context_bundle = context_builder.build_context("support", session_id, sanitized_message, chat_history)
                chat_messages = context_bundle.messages

                c_res = model_router.generate(
                    messages=chat_messages,
                    capability="fast"
                )
                assistant_response = c_res["content"]
            except Exception as ex:
                if context:
                    assistant_response = f"Here is the details from our policy FAQ:\n\n{context}"
                else:
                    assistant_response = "Hello! I am your TravelOps AI virtual assistant. Let me know if you want to book or cancel a journey."
    else:
        assistant_response = f"I parsed your intent as '{primary_intent.replace('_', ' ')}'. Let me assist you with that!"
        
    # Log assistant response to database
    assistant_log = AuditLogModel(
        session_id=session_id,
        agent_name="Assistant",
        action="message",
        reasoning_summary=assistant_response
    )
    if task_graph:
        assistant_log.set_payload({"task_graph": task_graph})
    db.add(assistant_log)
    db.commit()
    
    return {
        "session_id": session_id,
        "workflow_state": db.query(WorkflowStateModel).filter(WorkflowStateModel.session_id == session_id).order_by(WorkflowStateModel.updated_at.desc()).first().state,
        "response": assistant_response,
        "intent": intent_data
    }


# 4. Tool Execution Endpoint
@app.get("/api/tools")
def list_registered_tools():
    return {"tools": ToolRegistry.list_tools()}


@app.post("/api/sessions/{session_id}/approve")
async def approve_session_task(session_id: str, req: ApproveRequest, current_user: UserModel = Depends(require_role("operator"))):
    from backend.runtime.workflow.runtime import WorkflowRuntime
    res = await WorkflowRuntime.approve_task(session_id, req.task_id)
    if res.get("success"):
        return res
    else:
        raise HTTPException(status_code=400, detail=res.get("error"))


@app.post("/api/sessions/{session_id}/execute-task")
def execute_session_task(session_id: str, req: ExecuteTaskRequest, db: Session = Depends(get_db), current_user: UserModel = Depends(require_role("operator"))):
    # Verify session exists
    session = db.query(SessionModel).filter(SessionModel.session_id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
        
    # Apply guardrails validation checks
    try:
        GuardrailsProcessor.validate_args(req.tool_name, req.arguments)
    except ValueError as val_err:
        raise HTTPException(status_code=400, detail=str(val_err))

    # Execute tool through registry (which audits automatically)
    result = ToolRegistry.execute_tool(req.tool_name, session_id, **req.arguments)
    return {"result": result}


@app.post("/api/sessions/{session_id}/run")
def run_session_workflow(session_id: str, background_tasks: BackgroundTasks, db: Session = Depends(get_db), current_user: UserModel = Depends(get_current_user)):
    # Verify session exists
    session = db.query(SessionModel).filter(SessionModel.session_id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
        
    # Enforce user/session ownership
    if current_user.role != "admin" and session.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied: You do not own this session.")
        
    tasks = db.query(TaskStateModel).filter(TaskStateModel.session_id == session_id).all()
    if not tasks:
        raise HTTPException(status_code=400, detail="No tasks found for this session. Please search and generate a plan first.")
        
    # Check if we should reset (e.g. if we have any failed tasks or if all are completed)
    all_completed = all(t.status == "COMPLETED" for t in tasks)
    any_failed = any(t.status == "FAILED" for t in tasks)
    if all_completed or any_failed:
        logger.info(f"Resetting task states for session {session_id} to trigger fresh run.")
        for t in tasks:
            t.status = "PENDING"
            t.set_output({})
            
    # Set workflow state to SEARCHING
    db.add(WorkflowStateModel(session_id=session_id, state="SEARCHING"))
    db.commit()
    
    background_tasks.add_task(WorkflowOrchestrator.execute_graph, session_id)
    return {"status": "started", "session_id": session_id}


# 5. Async Event Bus Integration
@app.post("/api/events/publish")
async def publish_event(req: PublishEventRequest, current_user: UserModel = Depends(require_role("operator"))):
    session_id = req.payload.get("session_id", "system")
    await EventBus.publish(req.event_type, session_id, req.payload)
    return {"status": "event_published", "event_type": req.event_type}


# 6. Observability Metrics
@app.get("/api/observability/metrics")
def get_observability_metrics(current_user: UserModel = Depends(require_role("admin"))):
    metrics = model_router.get_metrics()
    total_cost = sum(m.get("estimated_cost_usd", 0.0) for m in metrics)
    return {
        "llm_calls": metrics,
        "total_cost_usd": round(total_cost, 6),
        "registered_tools_count": len(ToolRegistry._registry)
    }


# Mock Helpers for Robust Fallback
def mock_intent_parser(message: str, current_date: str) -> Dict[str, Any]:
    msg = message.lower()
    
    # Default entities
    entities = {
        "origin": None,
        "destination": None,
        "travel_date": current_date,
        "pnr": None,
        "seat_preference": None,
        "passenger_details": None
    }
    
    # Simplistic keyword parsing
    if "from" in msg and "to" in msg:
        # Extract from / to
        try:
            parts = msg.split("from")
            subparts = parts[1].split("to")
            entities["origin"] = subparts[0].strip().title()
            # extract destination (take first word)
            entities["destination"] = subparts[1].strip().split()[0].title()
        except Exception:
            pass
            
    if "pnr" in msg:
        # extract PNR (simple uppercase word)
        words = msg.split()
        for w in words:
            if w.startswith("pnr") or len(w) == 6 and w.isalnum():
                entities["pnr"] = w.upper()
                
    if "tomorrow" in msg:
        # dummy resolve
        entities["travel_date"] = "2026-06-28"
        
    primary_intent = "general_chat"
    if "search" in msg or "bus" in msg or "go to" in msg or "travel" in msg or ("from" in msg and "to" in msg):
        primary_intent = "search_bus"
    elif "book" in msg or "seat" in msg:
        primary_intent = "book_bus"
    elif "cancel" in msg or "refund" in msg:
        primary_intent = "cancel_bus"
    elif "track" in msg or "delay" in msg or "where is" in msg or "delayed" in msg:
        primary_intent = "monitor_journey"
    elif "status" in msg or "booking" in msg:
        primary_intent = "get_status"
        
    return {
        "primary_intent": primary_intent,
        "entities": entities,
        "confidence": 0.9,
        "reasoning_summary": "Extracted intent using fallback keyword parser."
    }

def mock_planner(entities: Dict[str, Any]) -> Dict[str, Any]:
    origin = entities.get("origin", "Hyderabad")
    destination = entities.get("destination", "Bangalore")
    travel_date = entities.get("travel_date", "2026-06-28")
    
    return {
        "tasks": [
            {
                "task_id": "search_1",
                "name": "search_buses",
                "dependencies": [],
                "input_data": {
                    "origin": origin,
                    "destination": destination,
                    "travel_date": travel_date
                }
            },
            {
                "task_id": "route_1",
                "name": "get_route_details",
                "dependencies": [],
                "input_data": {
                    "origin": origin,
                    "destination": destination
                }
            },
            {
                "task_id": "weather_1",
                "name": "get_weather_forecast",
                "dependencies": [],
                "input_data": {
                    "destination": destination,
                    "travel_date": travel_date
                }
            },
            {
                "task_id": "recommend_1",
                "name": "recommend_options",
                "dependencies": ["search_1", "route_1", "weather_1"],
                "input_data": {
                    "preference": "highest_rating"
                }
            },
            {
                "task_id": "hold_1",
                "name": "hold_seat",
                "dependencies": ["recommend_1"],
                "input_data": {}
            },
            {
                "task_id": "pay_1",
                "name": "process_payment",
                "dependencies": ["hold_1"],
                "input_data": {
                    "amount": 750,
                    "card_number": "4111 1111 1111 1111"
                }
            },
            {
                "task_id": "confirm_1",
                "name": "confirm_booking",
                "dependencies": ["pay_1"],
                "input_data": {}
            },
            {
                "task_id": "notify_1",
                "name": "send_notification",
                "dependencies": ["confirm_1"],
                "input_data": {
                    "channels": ["SMS", "Email"]
                }
            }
        ]
    }
