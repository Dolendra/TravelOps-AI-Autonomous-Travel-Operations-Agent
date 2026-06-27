import json
import logging
from typing import Dict, Any, List

from backend.services.llm import ModelRouter
from backend.services.prompt_loader import PromptLoader
from backend.database.db import SessionLocal
from backend.database.models import TaskStateModel

logger = logging.getLogger("travelops.agents.reflection")

class ReflectionAgent:
    def __init__(self, model_router: ModelRouter, prompt_loader: PromptLoader):
        self.model_router = model_router
        self.prompt_loader = prompt_loader

    def reflect_and_repair(self, session_id: str, failed_task_id: str, error_msg: str) -> bool:
        """
        Analyzes a failed task node in the session's DAG graph.
        - Loads the reflection prompt template.
        - Sends the failed task description, error messages, and full graph state to the reasoning LLM.
        - Parses the repair action ('retry', 'replan', or 'abort').
        - Modifies SQLite task records (resetting states to PENDING and updating inputs) to retry execution.
        """
        db = SessionLocal()
        try:
            # 1. Extract current state of all tasks for this session
            db_tasks = db.query(TaskStateModel).filter(TaskStateModel.session_id == session_id).all()
            graph_state_list = []
            failed_task_name = ""
            
            for t in db_tasks:
                if t.task_id == failed_task_id:
                    failed_task_name = t.name
                graph_state_list.append({
                    "task_id": t.task_id,
                    "name": t.name,
                    "status": t.status,
                    "input_data": t.get_input(),
                    "output_data": t.get_output()
                })
                
            # 2. Render Prompt context
            reflection_prompt = self.prompt_loader.load_prompt("reflection", {
                "failed_task_name": failed_task_name,
                "failed_task_id": failed_task_id,
                "error_message": error_msg,
                "graph_state": json.dumps(graph_state_list, indent=2)
            })
            
            messages = [
                {"role": "system", "content": reflection_prompt},
                {"role": "user", "content": "Analyze the failed task graph and generate the JSON repair action."}
            ]
            
            response = self.model_router.generate(
                messages=messages,
                capability="reasoning",
                response_format={"type": "json_object"}
            )
            
            if not response["success"]:
                logger.error(f"Reflection LLM request failed: {response.get('error')}")
                return False
                
            repair_data = json.loads(response["content"])
            action = repair_data.get("action", "abort")
            reasoning = repair_data.get("reasoning_summary", "")
            logger.info(f"Reflection Agent determined action: '{action}'. Reason: {reasoning}")
            
            if action in ["retry", "replan"]:
                new_tasks = repair_data.get("new_tasks", [])
                
                # Apply changes to task records
                for nt in new_tasks:
                    task_id = nt.get("task_id")
                    
                    # Find task in db
                    existing_task = db.query(TaskStateModel).filter(
                        TaskStateModel.session_id == session_id,
                        TaskStateModel.task_id == task_id
                    ).first()
                    
                    if existing_task:
                        # Reset task to PENDING and update parameters
                        existing_task.set_input(nt.get("input_data", {}))
                        existing_task.status = "PENDING"
                        existing_task.set_output({})  # Reset previous errors
                        logger.info(f"Reflection Agent: Reset task '{task_id}' with status 'PENDING'")
                    else:
                        # Append a new task node
                        new_node = TaskStateModel(
                            session_id=session_id,
                            task_id=task_id,
                            name=nt.get("name"),
                            status="PENDING"
                        )
                        new_node.set_dependencies(nt.get("dependencies", []))
                        new_node.set_input(nt.get("input_data", {}))
                        db.add(new_node)
                        logger.info(f"Reflection Agent: Added new task node '{task_id}' ('{nt.get('name')}')")
                        
                db.commit()
                return True
                
            return False
            
        except Exception as e:
            db.rollback()
            logger.error(f"Error in reflect_and_repair: {e}")
            return False
        finally:
            db.close()
