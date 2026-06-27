import asyncio
import logging
from typing import Dict, Any, List

from backend.database.db import SessionLocal
from backend.database.models import TaskStateModel, WorkflowStateModel
from backend.tools.registry import ToolRegistry

logger = logging.getLogger("travelops.runtime.workflow.executor")

class WorkflowExecutor:
    @classmethod
    async def execute_graph(cls, session_id: str):
        """
        Executes the task dependency graph for a session asynchronously.
        Resolves ready tasks concurrently, merges parent outputs, and records status.
        """
        logger.info(f"Starting workflow executor loop for session: {session_id}")
        
        max_iterations = 20
        iteration = 0
        
        while iteration < max_iterations:
            db = SessionLocal()
            try:
                # Load all tasks for the session
                tasks = db.query(TaskStateModel).filter(TaskStateModel.session_id == session_id).all()
                if not tasks:
                    logger.warning(f"No tasks found for session {session_id}. Exiting executor.")
                    break

                # Check if there are any failed tasks
                failed_tasks = [t for t in tasks if t.status == "FAILED"]
                if failed_tasks:
                    logger.error(f"Execution graph is blocked due to failed task: {[t.name for t in failed_tasks]}")
                    break

                # Count remaining unfinished tasks
                pending_or_running = [t for t in tasks if t.status in ["PENDING", "RUNNING", "PAUSED"]]
                if not pending_or_running:
                    logger.info(f"All tasks completed successfully for session {session_id}!")
                    break

                # Filter completed task IDs to check dependencies
                completed_task_ids = {t.task_id for t in tasks if t.status == "COMPLETED"}
                ready_tasks = []
                for t in tasks:
                    if t.status == "PENDING":
                        deps = t.get_dependencies()
                        # Task is ready if all dependencies are COMPLETED
                        if all(dep_id in completed_task_ids for dep_id in deps):
                            ready_tasks.append(t)

                if not ready_tasks:
                    # If we have paused tasks waiting for approvals, just stop the loop and wait
                    paused_tasks = [t for t in tasks if t.status == "PAUSED"]
                    if paused_tasks:
                        logger.info(f"Workflow execution paused waiting for human approval on tasks: {[t.name for t in paused_tasks]}")
                    elif any(t.status == "PENDING" for t in tasks):
                        logger.error(f"Deadlock or circular dependency detected for session {session_id}.")
                    break

                logger.info(f"Launching ready tasks wave: {[t.name for t in ready_tasks]}")
                
                execution_futures = []
                for r_task in ready_tasks:
                    config = r_task.get_input().get("_config", {})
                    
                    # Check human approval gate configuration
                    if config.get("approval_required") and not r_task.get_input().get("approved"):
                        logger.info(f"Task '{r_task.name}' requires operator approval. Pausing execution.")
                        r_task.status = "PAUSED"
                        db.commit()
                        
                        # Transition session workflow state to APPROVAL_REQUIRED
                        state_entry = WorkflowStateModel(session_id=session_id, state="APPROVAL_REQUIRED")
                        db.add(state_entry)
                        db.commit()
                        continue

                    # Transition task to RUNNING status
                    r_task.status = "RUNNING"
                    db.commit()
                    
                    # Prepare inputs by merging task static input with dependency outputs
                    merged_inputs = r_task.get_input()
                    for dep_id in r_task.get_dependencies():
                        dep_task = next((t for t in tasks if t.task_id == dep_id), None)
                        if dep_task:
                            dep_output = dep_task.get_output()
                            if isinstance(dep_output, dict):
                                merged_inputs.update(dep_output)
                                
                    execution_futures.append(
                        cls._execute_single_task(session_id, r_task.id, r_task.name, merged_inputs)
                    )

                db.close()
                
                if execution_futures:
                    await asyncio.gather(*execution_futures)
                    await asyncio.sleep(1.2)
                else:
                    break

            except Exception as e:
                logger.error(f"Error in executor run loop: {e}")
                break
            finally:
                iteration += 1

    @classmethod
    async def _execute_single_task(cls, session_id: str, db_task_id: int, tool_name: str, arguments: Dict[str, Any]):
        """Runs a single tool task in a thread, handles logs, retry loops, timeouts, and triggers reflection upon failure."""
        config = arguments.get("_config", {})
        
        # Resolve retry count limits
        retry_limit = config.get("retry", 0)
        
        # Resolve execution timeout limits
        timeout_val = config.get("timeout")
        timeout_seconds = None
        if timeout_val:
            if isinstance(timeout_val, str) and timeout_val.endswith("s"):
                timeout_seconds = float(timeout_val[:-1])
            else:
                timeout_seconds = float(timeout_val)

        def run():
            return ToolRegistry.execute_tool(tool_name, session_id, **arguments)

        attempts = 0
        result = None
        success = False
        
        while attempts <= retry_limit:
            attempts += 1
            try:
                if timeout_seconds:
                    result = await asyncio.wait_for(asyncio.to_thread(run), timeout=timeout_seconds)
                else:
                    result = await asyncio.to_thread(run)
                
                # If tool returns a structured failed status dictionary
                if isinstance(result, dict) and result.get("success") is False:
                    raise ValueError(result.get("error", "Task returned success=False"))
                
                success = True
                break
            except asyncio.TimeoutError:
                err_msg = f"Task execution timed out after {timeout_seconds} seconds."
                logger.warning(f"Attempt {attempts}/{retry_limit + 1} timed out for task '{tool_name}'")
                result = {"success": False, "error": err_msg}
                if attempts <= retry_limit:
                    await asyncio.sleep(0.5)
            except Exception as e:
                err_msg = str(e)
                logger.warning(f"Attempt {attempts}/{retry_limit + 1} failed for task '{tool_name}': {err_msg}")
                result = {"success": False, "error": err_msg}
                if attempts <= retry_limit:
                    await asyncio.sleep(0.5)

        db = SessionLocal()
        try:
            task = db.query(TaskStateModel).filter(TaskStateModel.id == db_task_id).first()
            if not task:
                return

            if not success:
                # Retries exhausted. Mark task status as FAILED in database
                task.status = "FAILED"
                task.set_output(result)
                db.commit()
                
                logger.warning(f"Task '{tool_name}' failed after {attempts} attempts. Initiating Reflection...")
                
                from backend.api.main import agent_runtime
                reflector = agent_runtime.get_agent_by_capability("reflection")
                
                repaired = reflector.reflect_and_repair(session_id, task.task_id, result.get("error", "Unknown error"))
                if repaired:
                    logger.info(f"Reflection Agent successfully self-repaired task '{tool_name}'! Retrying task...")
                    task.status = "PENDING"
                    db.commit()
                else:
                    logger.error(f"Reflection Agent could not repair task '{tool_name}'.")
                    # Transition session workflow state to FAILED
                    db.add(WorkflowStateModel(session_id=session_id, state="FAILED"))
                    db.commit()
                    
                    # Trigger compensating rollbacks via WorkflowRuntime
                    from backend.runtime.workflow.runtime import WorkflowRuntime
                    asyncio.create_task(WorkflowRuntime.rollback_workflow(session_id))
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

# Alias pointing to WorkflowExecutor for backward compatibility
WorkflowOrchestrator = WorkflowExecutor
