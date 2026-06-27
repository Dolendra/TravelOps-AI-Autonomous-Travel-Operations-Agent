from typing import Any
from backend.database.db import SessionLocal
from backend.database.models import WorkflowStateModel, TaskStateModel
from backend.runtime.context.models import ContextFragment

class WorkflowProvider:
    def get_fragment(self, session_id: str) -> ContextFragment:
        """Retrieves active workflow state and current execution tasks progress."""
        db = SessionLocal()
        content_lines = []
        session_state = "NEW"
        tasks = []
        try:
            # Get latest session status
            state_model = db.query(WorkflowStateModel).filter(
                WorkflowStateModel.session_id == session_id
            ).order_by(WorkflowStateModel.updated_at.desc()).first()
            
            session_state = state_model.state if state_model else "NEW"
            content_lines.append(f"Current Session Status: {session_state}")

            # Get active orchestration tasks status
            tasks = db.query(TaskStateModel).filter(
                TaskStateModel.session_id == session_id
            ).all()
            
            if tasks:
                content_lines.append("Active Workflow Execution Progress:")
                for t in tasks:
                    deps = t.get_dependencies()
                    dep_str = f" (Dependencies: {', '.join(deps)})" if deps else ""
                    content_lines.append(f"- Task '{t.task_id}' ({t.name}): {t.status}{dep_str}")
        except Exception as e:
            content_lines.append(f"Workflow State Context: Unavailable ({e})")
        finally:
            db.close()

        compiled_content = "\n".join(content_lines)
        explainability = (
            f"Provides dynamic session status (current: {session_state}) and "
            f"progress states of the {len(tasks)} orchestration tasks."
        )
        return ContextFragment(
            name="workflow",
            content=compiled_content,
            priority=90,
            explainability=explainability
        )
