import re
import logging
from datetime import datetime
from typing import Dict, Any

logger = logging.getLogger("travelops.services.guardrails")

# Regular expression to match 13-19 digit credit card numbers with optional spaces/dashes
CARD_REGEX = re.compile(r'\b(?:\d[ -]?){13,19}\b')
# Simple email regex
EMAIL_REGEX = re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b')

# Core prompt injection bypass keywords
INJECTION_KEYWORDS = [
    "ignore system prompt",
    "ignore system instruction",
    "ignore previous instruction",
    "bypass guardrail",
    "ignore system rules",
    "bypass rules"
]

class GuardrailsProcessor:
    @staticmethod
    def sanitize_input(text: str) -> str:
        """
        Sanitizes raw user text inputs.
        - Masks Credit Card numbers with [MASKED_CARD]
        - Masks Emails with [MASKED_EMAIL]
        - Throws ValueError if injection bypass keywords are detected.
        """
        if not text:
            return text

        # 1. Mask credit cards
        text = CARD_REGEX.sub("[MASKED_CARD]", text)

        # 2. Mask emails
        text = EMAIL_REGEX.sub("[MASKED_EMAIL]", text)

        # 3. Detect prompt injections
        lower_text = text.lower()
        for keyword in INJECTION_KEYWORDS:
            if keyword in lower_text:
                logger.warning(f"Security Warning: Prompt injection pattern detected: '{keyword}'")
                raise ValueError("Input blocked: Security guardrail violation.")

        return text

    @staticmethod
    def validate_args(tool_name: str, args: Dict[str, Any]) -> bool:
        """
        Enforces parameter specifications before calling tools.
        """
        if tool_name == "search_buses":
            origin = args.get("origin")
            destination = args.get("destination")
            travel_date = args.get("travel_date")

            if not origin or not isinstance(origin, str) or len(origin.strip()) < 2:
                raise ValueError("Invalid origin name: must be a string of at least 2 characters.")
            if not destination or not isinstance(destination, str) or len(destination.strip()) < 2:
                raise ValueError("Invalid destination name: must be a string of at least 2 characters.")

            if travel_date:
                try:
                    datetime.strptime(travel_date, "%Y-%m-%d")
                except ValueError:
                    raise ValueError("Invalid travel_date format. Must be YYYY-MM-DD.")

        elif tool_name == "hold_seat":
            seat_number = args.get("seat_number")
            if seat_number:
                if not re.match(r'^\d{1,2}[A-Z]$', seat_number):
                    raise ValueError("Invalid seat_number format. Must match patterns like '1A', '10D'.")

        elif tool_name == "process_payment":
            card_number = args.get("card_number")
            if not card_number:
                raise ValueError("Card number is required for payments.")
            clean_card = card_number.replace(" ", "").replace("-", "")
            if not clean_card.isdigit() or len(clean_card) < 13 or len(clean_card) > 19:
                raise ValueError("Invalid credit card format.")

        return True
