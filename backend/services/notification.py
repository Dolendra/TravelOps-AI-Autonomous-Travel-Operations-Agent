import logging
import os
import urllib.request
import urllib.parse
import base64
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict, Any, List

logger = logging.getLogger("travelops.services.notification")

class NotificationGateway:
    @classmethod
    def send_sms(cls, recipient: str, message: str) -> bool:
        """Dispatches an SMS via Twilio if configured, falling back to mock logging."""
        account_sid = os.getenv("TWILIO_ACCOUNT_SID")
        auth_token = os.getenv("TWILIO_AUTH_TOKEN")
        from_number = os.getenv("TWILIO_FROM_NUMBER")

        if account_sid and auth_token and from_number:
            try:
                url = f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Messages.json"
                data = urllib.parse.urlencode({
                    "To": recipient,
                    "From": from_number,
                    "Body": message
                }).encode("utf-8")
                
                req = urllib.request.Request(url, data=data, method="POST")
                auth = base64.b64encode(f"{account_sid}:{auth_token}".encode("utf-8")).decode("utf-8")
                req.add_header("Authorization", f"Basic {auth}")
                req.add_header("Content-Type", "application/x-www-form-urlencoded")
                
                with urllib.request.urlopen(req, timeout=5) as response:
                    logger.info(f"[Twilio SMS SUCCESS] Sent SMS to {recipient}")
                    return True
            except Exception as e:
                logger.error(f"Failed to send real SMS via Twilio: {e}")

        logger.info(f"[Notification Gateway - SMS MOCK] To: {recipient} | Message: {message}")
        return True

    @classmethod
    def send_email(cls, recipient: str, subject: str, body: str) -> bool:
        """Sends an Email via SMTP server if configured, falling back to mock logging."""
        smtp_server = os.getenv("SMTP_SERVER")
        smtp_port = os.getenv("SMTP_PORT")
        smtp_user = os.getenv("SMTP_USERNAME")
        smtp_pass = os.getenv("SMTP_PASSWORD")
        from_email = os.getenv("SMTP_FROM_EMAIL", "noreply@travelops.ai")

        if smtp_server and smtp_port:
            try:
                port = int(smtp_port)
                msg = MIMEMultipart()
                msg["From"] = from_email
                msg["To"] = recipient
                msg["Subject"] = subject
                msg.attach(MIMEText(body, "plain"))

                if port == 465:
                    import ssl
                    context = ssl.create_default_context()
                    with smtplib.SMTP_SSL(smtp_server, port, context=context) as server:
                        if smtp_user and smtp_pass:
                            server.login(smtp_user, smtp_pass)
                        server.sendmail(from_email, recipient, msg.as_string())
                else:
                    with smtplib.SMTP(smtp_server, port) as server:
                        server.ehlo()
                        if port == 587:
                            server.starttls()
                            server.ehlo()
                        if smtp_user and smtp_pass:
                            server.login(smtp_user, smtp_pass)
                        server.sendmail(from_email, recipient, msg.as_string())
                logger.info(f"[SMTP EMAIL SUCCESS] Sent email to {recipient}")
                return True
            except Exception as e:
                logger.error(f"Failed to send real SMTP email: {e}")

        logger.info(f"[Notification Gateway - EMAIL MOCK] To: {recipient} | Subject: {subject} | Body: {body}")
        return True

    @classmethod
    def send_whatsapp(cls, recipient: str, message: str) -> bool:
        """Sends a WhatsApp text via Twilio if configured, falling back to mock logging."""
        account_sid = os.getenv("TWILIO_ACCOUNT_SID")
        auth_token = os.getenv("TWILIO_AUTH_TOKEN")
        from_whatsapp = os.getenv("TWILIO_FROM_WHATSAPP")

        if account_sid and auth_token and from_whatsapp:
            try:
                to_number = recipient
                if not to_number.startswith("whatsapp:"):
                    to_number = f"whatsapp:{to_number}"
                
                url = f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Messages.json"
                data = urllib.parse.urlencode({
                    "To": to_number,
                    "From": from_whatsapp,
                    "Body": message
                }).encode("utf-8")
                
                req = urllib.request.Request(url, data=data, method="POST")
                auth = base64.b64encode(f"{account_sid}:{auth_token}".encode("utf-8")).decode("utf-8")
                req.add_header("Authorization", f"Basic {auth}")
                req.add_header("Content-Type", "application/x-www-form-urlencoded")
                
                with urllib.request.urlopen(req, timeout=5) as response:
                    logger.info(f"[Twilio WhatsApp SUCCESS] Sent WhatsApp to {to_number}")
                    return True
            except Exception as e:
                logger.error(f"Failed to send real WhatsApp via Twilio: {e}")

        logger.info(f"[Notification Gateway - WHATSAPP MOCK] To: {recipient} | Message: {message}")
        return True

    @classmethod
    def dispatch_alert(cls, channel: str, recipient: str, message: str, subject: str = "TravelOps Update") -> bool:
        """Central router routing notification requests to SMTP/Twilio/Mock targets."""
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
