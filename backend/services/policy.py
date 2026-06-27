import logging
from datetime import datetime

logger = logging.getLogger("travelops.services.policy")

class PolicyEngine:
    @staticmethod
    def calculate_refund_percentage(departure_time: datetime, request_time: datetime) -> float:
        """
        Calculates refund percentage based on time remaining before bus departure.
        - >24 hours: 100% refund
        - 12 to 24 hours: 75% refund
        - 2 to 12 hours: 50% refund
        - <2 hours: 0% refund
        """
        if request_time >= departure_time:
            return 0.0

        time_diff = departure_time - request_time
        hours_diff = time_diff.total_seconds() / 3600.0

        if hours_diff >= 24.0:
            return 1.0
        elif hours_diff >= 12.0:
            return 0.75
        elif hours_diff >= 2.0:
            return 0.50
        else:
            return 0.0

    @staticmethod
    def validate_upgrade_eligibility(current_class: str, loyalty_points: int) -> bool:
        """
        Evaluates whether a passenger qualifies for a seat upgrade.
        - Upgrade is only eligible for standard tickets.
        - Requires at least 1000 loyalty points.
        """
        if "premium" in current_class.lower() or "sleeper" in current_class.lower():
            return False
            
        if loyalty_points >= 1000:
            return True
            
        return False
