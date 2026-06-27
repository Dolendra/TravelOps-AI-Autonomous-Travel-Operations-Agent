import logging
import asyncio
from typing import Dict, Any

from backend.database.db import SessionLocal
from backend.database.models import TaskStateModel, WorkflowStateModel, BookingModel, BusInventoryModel
from backend.runtime.workflow.executor import WorkflowExecutor

logger = logging.getLogger("travelops.runtime.workflow.runtime")

class WorkflowRuntime:
    @classmethod
    async def trigger_workflow(cls, session_id: str):
        """Triggers execution of the task dependency graph for a session."""
        logger.info(f"WorkflowRuntime: Triggering workflow execution for session {session_id}")
        await WorkflowExecutor.execute_graph(session_id)

    @classmethod
    async def approve_task(cls, session_id: str, task_id: str):
        """Approves a paused task and resumes workflow execution."""
        db = SessionLocal()
        try:
            task = db.query(TaskStateModel).filter(
                TaskStateModel.session_id == session_id,
                TaskStateModel.task_id == task_id
            ).first()
            if task:
                inp = task.get_input()
                inp["approved"] = True
                task.set_input(inp)
                task.status = "PENDING"
                db.commit()
                logger.info(f"WorkflowRuntime: Task '{task_id}' approved. Resuming execution for session {session_id}...")
                
                # Resume execution in background
                asyncio.create_task(WorkflowExecutor.execute_graph(session_id))
                return {"success": True, "message": f"Task '{task_id}' approved. Execution resumed."}
            else:
                logger.warning(f"WorkflowRuntime: Task '{task_id}' not found for approval in session {session_id}.")
                return {"success": False, "error": f"Task '{task_id}' not found."}
        finally:
            db.close()

    @classmethod
    async def rollback_workflow(cls, session_id: str):
        """
        Executes compensation steps (Saga Rollback) for all completed steps in a failed session.
        E.g. Releases seats held by hold_seat, cancels charges, etc.
        """
        logger.warning(f"WorkflowRuntime: Initiating compensation rollback for session {session_id}...")
        db = SessionLocal()
        try:
            # 1. Transition workflow state to ROLLBACK_IN_PROGRESS
            db.add(WorkflowStateModel(session_id=session_id, state="ROLLBACK_IN_PROGRESS"))
            db.commit()

            # 2. Query all task states for this session
            tasks = db.query(TaskStateModel).filter(TaskStateModel.session_id == session_id).all()
            completed_task_names = {t.name for t in tasks if t.status == "COMPLETED"}

            # 3. Check if 'hold_seat' was completed and needs rollback
            if "hold_seat" in completed_task_names:
                # Find all held or confirmed bookings created in this session and cancel them
                bookings = db.query(BookingModel).filter(
                    BookingModel.session_id == session_id,
                    BookingModel.status.in_(["HELD", "CONFIRMED"])
                ).all()
                
                from backend.providers.router import ProviderRouter
                router = ProviderRouter()
                for booking in bookings:
                    logger.info(f"WorkflowRuntime Rollback: Routing cancellation via ProviderRouter for booking {booking.id}")
                    router.cancel_booking(booking.id, session_id)

            # 4. Check if 'process_payment' was completed and needs rollback
            if "process_payment" in completed_task_names:
                # Simulate refunding transaction charges
                logger.info("WorkflowRuntime Rollback: Refunding transaction charges...")

            # 5. Transition final state to ROLLBACK_COMPLETE
            db.add(WorkflowStateModel(session_id=session_id, state="ROLLBACK_COMPLETE"))
            db.commit()
            logger.info(f"WorkflowRuntime: Rollback completed successfully for session {session_id}.")
        except Exception as e:
            db.rollback()
            logger.error(f"WorkflowRuntime: Rollback failed for session {session_id}: {e}")
            db.add(WorkflowStateModel(session_id=session_id, state="ROLLBACK_FAILED"))
            db.commit()
        finally:
            db.close()
