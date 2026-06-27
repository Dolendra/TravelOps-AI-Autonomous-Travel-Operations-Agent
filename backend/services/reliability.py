import time
import random
import logging
from typing import Callable, Any, Dict

logger = logging.getLogger("travelops.services.reliability")

class CircuitBreakerOpenException(Exception):
    """Exception raised when a circuit breaker is in OPEN state and blocks requests."""
    pass


class CircuitBreaker:
    def __init__(self, name: str, failure_threshold: int = 3, recovery_timeout: float = 30.0):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN
        self.failure_count = 0
        self.last_state_change = time.time()
        self.last_failure_time = 0.0

    def call(self, func: Callable, *args, **kwargs) -> Any:
        """Executes the function wrapping it with circuit breaker checks."""
        current_time = time.time()
        
        # Check transition from OPEN to HALF_OPEN
        if self.state == "OPEN":
            if current_time - self.last_failure_time > self.recovery_timeout:
                logger.warning(f"[CircuitBreaker {self.name}] Transitioning from OPEN to HALF_OPEN (timeout expired).")
                self.state = "HALF_OPEN"
                self.last_state_change = current_time
            else:
                logger.error(f"[CircuitBreaker {self.name}] Call blocked. Circuit is OPEN.")
                raise CircuitBreakerOpenException(f"Circuit '{self.name}' is OPEN. Requests blocked.")

        try:
            # Execute the call
            result = func(*args, **kwargs)
            
            # If the call returns a payload indicating failure (e.g. tool execution return success: False)
            if isinstance(result, dict) and result.get("success") is False:
                # Treat as tool failure
                self._handle_failure(result.get("error", "Tool reported failure"))
            else:
                # Reset circuit on success
                if self.state == "HALF_OPEN":
                    logger.info(f"[CircuitBreaker {self.name}] Successful call. Transitioning from HALF_OPEN to CLOSED.")
                    self.state = "CLOSED"
                    self.failure_count = 0
                    self.last_state_change = current_time
                elif self.state == "CLOSED" and self.failure_count > 0:
                    # Clear transient failures
                    self.failure_count = 0
            return result
        except Exception as e:
            self._handle_failure(str(e))
            raise

    def _handle_failure(self, error_msg: str):
        current_time = time.time()
        self.failure_count += 1
        self.last_failure_time = current_time
        logger.warning(f"[CircuitBreaker {self.name}] Failure detected: {error_msg}. Count: {self.failure_count}/{self.failure_threshold}")
        
        if self.state in ["CLOSED", "HALF_OPEN"] and self.failure_count >= self.failure_threshold:
            logger.critical(f"[CircuitBreaker {self.name}] Failure threshold reached. Tripping circuit to OPEN.")
            self.state = "OPEN"
            self.last_state_change = current_time


# Instantiate shared database connection circuit breaker
db_breaker = CircuitBreaker("database_engine", failure_threshold=5, recovery_timeout=30.0)


class ExponentialBackoff:
    @staticmethod
    def execute(
        func: Callable,
        *args,
        max_retries: int = 3,
        base_delay: float = 1.0,
        factor: float = 2.0,
        max_delay: float = 8.0,
        **kwargs
    ) -> Any:
        """Executes a function with exponential backoff and jitter retry loops."""
        last_exception = None
        for attempt in range(1, max_retries + 2):
            try:
                result = func(*args, **kwargs)
                if isinstance(result, dict) and result.get("success") is False:
                    # Treat failure payloads as retriable
                    raise Exception(result.get("error", "Action failed"))
                return result
            except Exception as e:
                last_exception = e
                if attempt > max_retries:
                    break
                
                # Calculate backoff delay with random jitter (0-20% jitter)
                delay = min(max_delay, base_delay * (factor ** (attempt - 1)))
                jitter = delay * random.uniform(0.0, 0.2)
                total_delay = delay + jitter
                
                logger.warning(
                    f"Attempt {attempt} failed: {e}. Retrying in {total_delay:.2f}s..."
                )
                time.sleep(total_delay)
                
        raise last_exception


from sqlalchemy.orm import Session
from datetime import datetime, timedelta
import json
from backend.database.models import CacheModel
from typing import Optional, Dict

def get_idempotent_result(db: Session, key: str) -> Optional[Dict[str, Any]]:
    """Checks the database cache for a previously saved idempotent response."""
    cache_entry = db.query(CacheModel).filter(CacheModel.key == f"idem:{key}").first()
    if cache_entry:
        if cache_entry.expires_at and cache_entry.expires_at < datetime.utcnow():
            db.delete(cache_entry)
            db.commit()
            return None
        try:
            return json.loads(cache_entry.value)
        except Exception:
            return None
    return None

def save_idempotent_result(db: Session, key: str, value: Dict[str, Any], ttl_seconds: int = 3600):
    """Saves a response to the database cache for idempotency verification."""
    try:
        cache_key = f"idem:{key}"
        expires_at = datetime.utcnow() + timedelta(seconds=ttl_seconds)
        cache_entry = db.query(CacheModel).filter(CacheModel.key == cache_key).first()
        if cache_entry:
            cache_entry.value = json.dumps(value)
            cache_entry.expires_at = expires_at
        else:
            cache_entry = CacheModel(
                key=cache_key,
                value=json.dumps(value),
                expires_at=expires_at
            )
            db.add(cache_entry)
        db.commit()
    except Exception as e:
        logger.error(f"Failed to save idempotency cache for key {key}: {e}")
        db.rollback()

