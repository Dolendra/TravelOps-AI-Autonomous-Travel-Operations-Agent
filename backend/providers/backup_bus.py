import logging
from typing import Dict, Any, List

from backend.providers.base import BaseTravelProvider
from backend.providers.mock_bus import MockBusProvider

logger = logging.getLogger("travelops.providers.backup_bus")

class BackupBusProvider(BaseTravelProvider):
    def __init__(self):
        self._delegate = MockBusProvider()
        self.should_fail = False

    @property
    def name(self) -> str:
        return "BackupBusProvider"

    def search_buses(self, origin: str, destination: str, travel_date: str) -> List[Dict[str, Any]]:
        if self.should_fail:
            logger.error("BackupBusProvider simulated search failure.")
            raise ConnectionError("Backup Provider Connection Timeout")
            
        logger.info(f"BackupBusProvider routing search buses request...")
        results = self._delegate.search_buses(origin, destination, travel_date)
        
        # Modify operator names so we can visually verify backup failover routing
        for bus in results:
            bus["operator_name"] = f"Backup: {bus['operator_name']}"
        return results

    def hold_seat(self, bus_id: int, seat_number: str, passenger_name: str, passenger_email: str, session_id: str) -> Dict[str, Any]:
        if self.should_fail:
            logger.error("BackupBusProvider simulated seat hold failure.")
            return {"success": False, "error": "Backup Provider Connection Timeout"}
            
        logger.info(f"BackupBusProvider holding seat...")
        res = self._delegate.hold_seat(bus_id, seat_number, passenger_name, passenger_email, session_id)
        if res.get("success"):
            res["operator_name"] = f"Backup: {res.get('operator_name', 'Travel Express')}"
        return res

    def confirm_booking(self, booking_id: int) -> Dict[str, Any]:
        if self.should_fail:
            logger.error("BackupBusProvider simulated ticket confirmation failure.")
            return {"success": False, "error": "Backup Provider Connection Timeout"}
            
        logger.info(f"BackupBusProvider confirming booking...")
        res = self._delegate.confirm_booking(booking_id)
        if res.get("success") and "ticket" in res:
            res["ticket"]["operator_name"] = f"Backup: {res['ticket'].get('operator_name', 'Travel Express')}"
        return res

    def cancel_booking(self, booking_id: int, session_id: str) -> Dict[str, Any]:
        logger.info(f"BackupBusProvider cancelling booking...")
        return self._delegate.cancel_booking(booking_id, session_id)
