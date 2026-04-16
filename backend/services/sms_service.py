"""
sms_service.py – Twilio-based SMS alerts as a fallback for network issues.
"""

from __future__ import annotations

import threading
from twilio.rest import Client
from config import cfg
from utils.logger import get_logger

log = get_logger("services.sms")

class SmsService:
    """Sends SMS alerts using Twilio SDK."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._enabled = bool(
            cfg.TWILIO_SID and 
            cfg.TWILIO_AUTH_TOKEN and 
            cfg.TWILIO_PHONE_NUMBER and 
            cfg.RECIPIENT_PHONE
        )
        
        if self._enabled:
            try:
                self._client = Client(cfg.TWILIO_SID, cfg.TWILIO_AUTH_TOKEN)
                log.info("SmsService initialised with Twilio.")
            except Exception as e:
                log.error(f"Failed to initialise Twilio client: {e}")
                self._enabled = False
        else:
            log.warning("SmsService disabled – Twilio credentials not fully set in .env")

    def send_alert(self, alert_type: str, message: str) -> bool:
        """
        Send a high-priority SMS alert.
        Returns: True if sent successfully, False otherwise.
        """
        if not self._enabled:
            return False

        with self._lock:
            try:
                # Brief, urgent message for SMS
                sms_body = (
                    f"⚠️ SURVEILLANCE ALERT\n"
                    f"Type: {alert_type.upper().replace('_', ' ')}\n"
                    f"Msg: {message[:100]}"
                )
                
                message = self._client.messages.create(
                    body=sms_body,
                    from_=cfg.TWILIO_PHONE_NUMBER,
                    to=cfg.RECIPIENT_PHONE
                )
                
                log.info(f"SMS Alert sent! SID: {message.sid}")
                return True
            except Exception as e:
                log.error(f"Failed to send SMS via Twilio: {e}")
                return False
