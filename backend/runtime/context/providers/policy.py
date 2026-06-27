from backend.runtime.context.models import ContextFragment

class PolicyProvider:
    def get_fragment(self) -> ContextFragment:
        """Retrieves default travel ticketing and cancellation policy contexts."""
        policy_content = (
            "Standard Travel Cancellation & Booking Policies:\n"
            "- Full refund (less 10% fee) is permitted if cancelled > 4 hours prior to departure.\n"
            "- Under 4 hours of departure, tickets are non-refundable.\n"
            "- Seat reservations are held for 15 minutes during payment processing.\n"
            "- Boarding passes are issued starting 3 hours before departure."
        )
        return ContextFragment(
            name="policy",
            content=policy_content,
            priority=60,
            explainability="Deterministic business policies governing refund schedules, ticketing deadlines, and boarding rules."
        )
