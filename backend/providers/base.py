from abc import ABC, abstractmethod
from typing import Dict, Any, List

class BaseTravelProvider(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        """Returns the unique name identifier of the provider."""
        pass

    @abstractmethod
    def search_buses(self, origin: str, destination: str, travel_date: str) -> List[Dict[str, Any]]:
        """Queries route inventory and returns a list of available bus options."""
        pass

    @abstractmethod
    def hold_seat(self, bus_id: int, seat_number: str, passenger_name: str, passenger_email: str, session_id: str) -> Dict[str, Any]:
        """Locks a seat in the provider inventory, returning hold details."""
        pass

    @abstractmethod
    def confirm_booking(self, booking_id: int) -> Dict[str, Any]:
        """Finalizes booking payment confirmation and issues ticket PNR."""
        pass

    @abstractmethod
    def cancel_booking(self, booking_id: int, session_id: str) -> Dict[str, Any]:
        """Cancels booking and rolls back seat allocations."""
        pass
