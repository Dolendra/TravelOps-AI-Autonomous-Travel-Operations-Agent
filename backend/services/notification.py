import logging
from typing import Dict, Any, List

logger = logging.getLogger("travelops.services.notification")

class NotificationGateway:
    @classmethod
    def send_sms(cls, recipient: str, message: str) -> bool:
        """Simulates dispatching an SMS."""
        logger.info(f"[Notification Gateway - SMS MOCK] To: {recipient} | Message: {message}")
        return True

    @classmethod
    def send_email(cls, recipient: str, subject: str, body: str) -> bool:
        """Simulates sending an Email."""
        logger.info(f"[Notification Gateway - EMAIL MOCK] To: {recipient} | Subject: {subject} | Body: {body}")
        return True

    @classmethod
    def send_whatsapp(cls, recipient: str, message: str) -> bool:
        """Simulates sending a WhatsApp text."""
        logger.info(f"[Notification Gateway - WHATSAPP MOCK] To: {recipient} | Message: {message}")
        return True

    @classmethod
    def dispatch_alert(cls, channel: str, recipient: str, message: str, subject: str = "TravelOps Update") -> bool:
        """Central router routing notification requests to their respective mocks."""
        c = channel.upper()
        if c == "SMS":
            return cls.send_sms(recipient, message)
        elif c == "EMAIL":
            return cls.send_email(recipient, subject, message)
        elif c == "WHATSAPP":
            return cls.send_whatsapp(recipient, message)
        else:
            logger.warning(f"Requested notification channel '{channel}' is not supported.")
            return False
