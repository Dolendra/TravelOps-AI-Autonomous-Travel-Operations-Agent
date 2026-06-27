import asyncio
import logging
from typing import Dict, Any, List

from backend.database.db import SessionLocal
from backend.database.models import TaskStateModel, WorkflowStateModel
from backend.tools.registry import ToolRegistry

logger = logging.getLogger("travelops.workflows.orchestrator")

class WorkflowOrchestrator:
    @classmethod
    async def execute_graph(cls, session_id: str):
        """
        Executes the task dependency graph for a session asynchronously.
        Resolves ready tasks concurrently, merges parent outputs, and records status.
        """
        logger.info(f"Starting orchestration execution loop for session: {session_id}")
        
        # Guard against infinite loops in graph solving
        max_iterations = 20
        iteration = 0
        
        while iteration < max_iterations:
            db = SessionLocal()
            try:
                # Load all tasks for the session
                tasks = db.query(TaskStateModel).filter(TaskStateModel.session_id == session_id).all()
                if not tasks:
                    logger.warning(f"No tasks found for session {session_id}. Exiting orchestrator.")
                    break

                # Check if there are any failed tasks
                failed_tasks = [t for t in tasks if t.status == "FAILED"]
                if failed_tasks:
                    logger.error(f"Execution graph is blocked due to failed task: {[t.name for t in failed_tasks]}")
                    break

                # Count remaining unfinished tasks
                pending_or_running = [t for t in tasks if t.status in ["PENDING", "RUNNING"]]
                if not pending_or_running:
                    logger.info(f"All tasks completed successfully for session {session_id}!")
                    break

                # Filter completed task IDs to check dependencies
                completed_task_ids = {t.task_id for t in tasks if t.status == "COMPLETED"}
                ready_tasks = []
                for t in tasks:
                    if t.status == "PENDING":
                        deps = t.get_dependencies()
                        # Task is ready if all its dependencies are COMPLETED
                        if all(dep_id in completed_task_ids for dep_id in deps):
                            ready_tasks.append(t)

                if not ready_tasks:
                    if any(t.status == "PENDING" for t in tasks):
                        logger.error(f"Deadlock or circular dependency detected for session {session_id}.")
                    break

                logger.info(f"Launching ready tasks wave: {[t.name for t in ready_tasks]}")
                
                # Execute ready tasks in parallel
                execution_futures = []
                for r_task in ready_tasks:
                    # 1. Transition task to RUNNING status
                    r_task.status = "RUNNING"
                    db.commit()
                    
                    # 2. Prepare inputs by merging task static input with dependency outputs
                    merged_inputs = r_task.get_input()
                    for dep_id in r_task.get_dependencies():
                        dep_task = next((t for t in tasks if t.task_id == dep_id), None)
                        if dep_task:
                            dep_output = dep_task.get_output()
                            # If dependency returned a nested dictionary (e.g. recommend_options returning recommended_buses list)
                            # or processed ticket output, merge them.
                            if isinstance(dep_output, dict):
                                merged_inputs.update(dep_output)
                                
                    # 3. Schedule task execution in background thread pool to avoid blocking asyncio event loop
                    execution_futures.append(
                        cls._execute_single_task(session_id, r_task.id, r_task.name, merged_inputs)
                    )

                db.close() # Close session while awaiting execution wave to avoid long locked transactions
                
                # Wait for this wave to finish executing
                await asyncio.gather(*execution_futures)
                
                # Slight sleep delay to ensure polling client visualizes status transitions (PENDING -> RUNNING -> COMPLETED)
                await asyncio.sleep(1.2)

            except Exception as e:
                logger.error(f"Error in orchestrator run loop: {e}")
                break
            finally:
                iteration += 1

    @classmethod
    async def _execute_single_task(cls, session_id: str, db_task_id: int, tool_name: str, arguments: Dict[str, Any]):
        """Runs a single tool task in a thread, handles logs, and triggers reflection upon failure."""
        def run():
            return ToolRegistry.execute_tool(tool_name, session_id, **arguments)
            
        try:
            result = await asyncio.to_thread(run)
            
            db = SessionLocal()
            try:
                task = db.query(TaskStateModel).filter(TaskStateModel.id == db_task_id).first()
                if not task:
                    return

                # If the tool returns a failed status indicator dict
                if isinstance(result, dict) and result.get("success") is False:
                    # Mark task status as FAILED in database
                    task.status = "FAILED"
                    task.set_output(result)
                    db.commit()
                    
                    logger.warning(f"Task '{tool_name}' failed. Initiating Reflection Agent self-repair loop...")
                    
                    # Dynamically load agents to prevent circular dependency imports
                    from agents.reflection.reflection_agent import ReflectionAgent
                    from backend.services.prompt_loader import PromptLoader
                    from backend.services.llm import ModelRouter
                    
                    router = ModelRouter()
                    loader = PromptLoader()
                    reflector = ReflectionAgent(router, loader)
                    
                    # Try to self-correct task inputs in SQLite database
                    repaired = reflector.reflect_and_repair(session_id, task.task_id, result.get("error", "Unknown error"))
                    if repaired:
                        logger.info(f"Reflection Agent successfully self-repaired task '{tool_name}'! Retrying task...")
                        task.status = "PENDING"
                        db.commit()
                    else:
                        logger.error(f"Reflection Agent could not repair task '{tool_name}'.")
                        # Mark session workflow state as FAILED
                        db.add(WorkflowStateModel(session_id=session_id, state="FAILED"))
                        db.commit()
                else:
                    # Update status to COMPLETED and save result outputs
                    task.status = "COMPLETED"
                    task.set_output(result)
                    
                    # Transition workflow states dynamically as milestones are completed
                    state_mapping = {
                        "search_buses": "OPTIONS_FOUND",
                        "hold_seat": "PAYMENT_PENDING",
                        "process_payment": "BOOKING",
                        "confirm_booking": "BOOKED",
                    }
                    if tool_name in state_mapping:
                        db.add(WorkflowStateModel(session_id=session_id, state=state_mapping[tool_name]))
                        
                    db.commit()
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"Unhandled execution exception in task '{tool_name}': {e}")
            db = SessionLocal()
            try:
                task = db.query(TaskStateModel).filter(TaskStateModel.id == db_task_id).first()
                if task:
                    task.status = "FAILED"
                    task.set_output({"success": False, "error": str(e)})
                    db.commit()
            finally:
                db.close()
