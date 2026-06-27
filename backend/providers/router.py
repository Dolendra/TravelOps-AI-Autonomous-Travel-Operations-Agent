import logging
import time
from typing import Dict, Any, List, Optional

from backend.providers.base import BaseTravelProvider
from backend.providers.mock_bus import MockBusProvider
from backend.providers.backup_bus import BackupBusProvider
from backend.database.db import SessionLocal
from backend.database.models import AuditLogModel

logger = logging.getLogger("travelops.providers.router")

class ProviderHealth:
    def __init__(self, name: str, max_failures: int = 3):
        self.name = name
        self.consecutive_failures = 0
        self.max_failures = max_failures
        self.status = "HEALTHY"  # HEALTHY, UNHEALTHY
        self.latencies: List[float] = []
        self.success_count = 0
        self.failure_count = 0

    def record_success(self, latency: float):
        self.consecutive_failures = 0
        self.success_count += 1
        self.latencies.append(latency)
        if len(self.latencies) > 20:
            self.latencies.pop(0)
        self.status = "HEALTHY"

    def record_failure(self):
        self.consecutive_failures += 1
        self.failure_count += 1
        if self.consecutive_failures >= self.max_failures:
            logger.critical(f"Provider '{self.name}' has failed {self.consecutive_failures} times. Tripping health status to UNHEALTHY.")
            self.status = "UNHEALTHY"

    def get_avg_latency(self) -> float:
        if not self.latencies:
            return 0.0
        return sum(self.latencies) / len(self.latencies)


class ProviderRouter:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(ProviderRouter, cls).__new__(cls, *args, **kwargs)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if getattr(self, "_initialized", False):
            return
        self.providers: Dict[str, BaseTravelProvider] = {}
        self.health_records: Dict[str, ProviderHealth] = {}
        self.preferred_provider_name = "mockbusprovider"
        self._initialized = True
        
        # Auto-register core providers
        self.register_provider(MockBusProvider())
        self.register_provider(BackupBusProvider())

    def register_provider(self, provider: BaseTravelProvider, max_failures: int = 3):
        name_key = provider.name.lower()
        self.providers[name_key] = provider
        self.health_records[name_key] = ProviderHealth(provider.name, max_failures)
        logger.info(f"Registered travel provider: {provider.name}")

    def get_active_provider(self) -> BaseTravelProvider:
        """Resolves the preferred provider. If unhealthy, falls back to the backup."""
        pref_key = self.preferred_provider_name.lower()
        pref_health = self.health_records.get(pref_key)
        
        if pref_health and pref_health.status == "HEALTHY":
            return self.providers[pref_key]
            
        # Fallback to first healthy provider
        for name_key, provider in self.providers.items():
            if name_key != pref_key and self.health_records[name_key].status == "HEALTHY":
                logger.warning(f"Preferred provider '{self.preferred_provider_name}' is unhealthy. Failing over to '{provider.name}'.")
                return provider
                
        # If all unhealthy, return preferred as last resort
        return self.providers.get(pref_key)

    def search_buses(self, origin: str, destination: str, travel_date: str) -> List[Dict[str, Any]]:
        provider = self.get_active_provider()
        health = self.health_records[provider.name.lower()]
        start_time = time.time()
        try:
            res = provider.search_buses(origin, destination, travel_date)
            latency = time.time() - start_time
            health.record_success(latency)
            self._audit_provider_selection(provider.name, "search_buses", latency, True)
            return res
        except Exception as e:
            health.record_failure()
            logger.error(f"Provider {provider.name} failed during search_buses: {e}")
            self._audit_provider_selection(provider.name, "search_buses", time.time() - start_time, False, str(e))
            # Retry with fallback immediately
            for name_key, fallback_p in self.providers.items():
                if fallback_p.name.lower() != provider.name.lower() and self.health_records[name_key].status == "HEALTHY":
                    logger.info(f"Retrying search_buses with fallback provider {fallback_p.name}")
                    return fallback_p.search_buses(origin, destination, travel_date)
            raise

    def hold_seat(self, bus_id: int, seat_number: str, passenger_name: str, passenger_email: str, session_id: str) -> Dict[str, Any]:
        provider = self.get_active_provider()
        health = self.health_records[provider.name.lower()]
        start_time = time.time()
        try:
            res = provider.hold_seat(bus_id, seat_number, passenger_name, passenger_email, session_id)
            latency = time.time() - start_time
            if res.get("success"):
                health.record_success(latency)
                self._audit_provider_selection(provider.name, "hold_seat", latency, True)
            else:
                health.record_failure()
                self._audit_provider_selection(provider.name, "hold_seat", latency, False, res.get("error"))
            return res
        except Exception as e:
            health.record_failure()
            logger.error(f"Provider {provider.name} failed during hold_seat: {e}")
            self._audit_provider_selection(provider.name, "hold_seat", time.time() - start_time, False, str(e))
            raise

    def confirm_booking(self, booking_id: int) -> Dict[str, Any]:
        provider = self.get_active_provider()
        health = self.health_records[provider.name.lower()]
        start_time = time.time()
        try:
            res = provider.confirm_booking(booking_id)
            latency = time.time() - start_time
            if res.get("success"):
                health.record_success(latency)
                self._audit_provider_selection(provider.name, "confirm_booking", latency, True)
            else:
                health.record_failure()
                self._audit_provider_selection(provider.name, "confirm_booking", latency, False, res.get("error"))
            return res
        except Exception as e:
            health.record_failure()
            logger.error(f"Provider {provider.name} failed during confirm_booking: {e}")
            self._audit_provider_selection(provider.name, "confirm_booking", time.time() - start_time, False, str(e))
            raise

    def cancel_booking(self, booking_id: int, session_id: str) -> Dict[str, Any]:
        provider = self.get_active_provider()
        health = self.health_records[provider.name.lower()]
        start_time = time.time()
        try:
            res = provider.cancel_booking(booking_id, session_id)
            latency = time.time() - start_time
            if res.get("success"):
                health.record_success(latency)
                self._audit_provider_selection(provider.name, "cancel_booking", latency, True)
            else:
                health.record_failure()
                self._audit_provider_selection(provider.name, "cancel_booking", latency, False, res.get("error"))
            return res
        except Exception as e:
            health.record_failure()
            logger.error(f"Provider {provider.name} failed during cancel_booking: {e}")
            self._audit_provider_selection(provider.name, "cancel_booking", time.time() - start_time, False, str(e))
            raise

    def _audit_provider_selection(self, provider_name: str, action: str, latency: float, success: bool, error_msg: Optional[str] = None):
        db = SessionLocal()
        try:
            audit = AuditLogModel(
                session_id="system_provider",
                agent_name="ProviderRouter",
                action=action,
                reasoning_summary=f"Routed {action} request to {provider_name}. Success: {success}. Latency: {latency:.3f}s"
            )
            audit.set_payload({
                "provider": provider_name,
                "latency_sec": latency,
                "success": success,
                "error": error_msg
            })
            db.add(audit)
            db.commit()
        except Exception as audit_err:
            logger.warning(f"Failed to save provider selection audit log: {audit_err}")
        finally:
            db.close()
