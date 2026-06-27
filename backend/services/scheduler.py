import asyncio
import logging
from typing import Dict, Any, Callable

logger = logging.getLogger("travelops.services.scheduler")

class JobScheduler:
    _tasks: Dict[str, asyncio.Task] = {}

    @classmethod
    def schedule_once(cls, job_id: str, delay_seconds: float, func: Callable[..., Any], *args: Any, **kwargs: Any) -> None:
        """Schedules a one-off task to run after a delay."""
        async def runner():
            try:
                await asyncio.sleep(delay_seconds)
                if asyncio.iscoroutinefunction(func):
                    await func(*args, **kwargs)
                else:
                    func(*args, **kwargs)
            except asyncio.CancelledError:
                logger.info(f"Scheduled job '{job_id}' was cancelled.")
            except Exception as e:
                logger.error(f"Error executing scheduled job '{job_id}': {e}")
            finally:
                cls._tasks.pop(job_id, None)

        # Cancel existing job with same ID if exists
        cls.cancel_job(job_id)
        
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = asyncio.get_event_loop()
            
        task = loop.create_task(runner())
        cls._tasks[job_id] = task
        logger.info(f"Scheduled job '{job_id}' to run in {delay_seconds} seconds.")

    @classmethod
    def cancel_job(cls, job_id: str) -> None:
        if job_id in cls._tasks:
            task = cls._tasks.get(job_id)
            if task and not task.done():
                task.cancel()
                logger.info(f"Cancelled active job '{job_id}'.")
            cls._tasks.pop(job_id, None)
