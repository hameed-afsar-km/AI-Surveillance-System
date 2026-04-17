"""
sms_service.py – Twilio-based SMS alerts as a fallback for network issues.
"""

import threading
import requests
from twilio.rest import Client
from config import cfg
from utils.logger import get_logger

log = get_logger("services.sms")

class SmsService:
    """Sends SMS alerts via Cloud (Twilio), Local (Android), or Email-Gateway."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._mode = cfg.SMS_MODE.lower()
        
        # Initialize Twilio if in cloud mode
        self._client = None
        if self._mode == "cloud" and cfg.TWILIO_SID:
            try:
                self._client = Client(cfg.TWILIO_SID, cfg.TWILIO_AUTH_TOKEN)
            except Exception as e:
                log.error(f"Twilio Init Fail: {e}")

        # Map alert type to config fields
        self.DEPT_ROUTING = {
            "collision":         ["PHONE_ACCIDENT", "PHONE_TRAFFIC"],
            "overcrowding":      ["PHONE_TRAFFIC"],
            "fire_hazard":       ["PHONE_FIRE", "PHONE_ACCIDENT"],
            "blast":             ["PHONE_FIRE", "PHONE_ACCIDENT"],
            "theft":             ["PHONE_ACCIDENT"],
            "littering":         ["PHONE_GARBAGE"],
            "garbage_hotspot":   ["PHONE_GARBAGE"],
            "test_connection":   ["PHONE_ACCIDENT"] # Default test use police field
        }

    def send_alert(self, alert_type: str, message: str) -> bool:
        recipients = self._get_recipients(alert_type)
        if not recipients:
            return False

        success = True
        for phone in recipients:
            if not self._dispatch(phone, message):
                success = False
        return success

    def _get_recipients(self, alert_type: str) -> list[str]:
        keys = self.DEPT_ROUTING.get(alert_type, ["PHONE_ACCIDENT"])
        phones = []
        for k in keys:
            val = getattr(cfg, k, "")
            if val: phones.append(val)
        return list(set(phones))

    def _dispatch(self, phone: str, message: str) -> bool:
        """Internal dispatcher based on SMS_MODE."""
        try:
            sms_body = f"⚠️ SURVEILLANCE: {message[:120]}"
            
            if self._mode == "local":
                # OFFLINE BACKUP: Sending via local Android Mobile Server
                resp = requests.post(f"{cfg.MOBILE_GATEWAY_URL}/send", 
                                     data={"number": phone, "message": sms_body}, 
                                     timeout=3)
                return resp.status_code == 200
            
            elif self._mode == "cloud" and self._client:
                # ONLINE: Sending via Twilio Cloud
                self._client.messages.create(body=sms_body, from_=cfg.TWILIO_PHONE_NUMBER, to=phone)
                return True
            
            elif self._mode == "email_gateway":
                # FREE: Sending via Email-to-SMS Gateway (Placeholder carrier: vtext.com)
                # In a real app, you'd allow carrier selection in UI
                from services.email_service import EmailService
                EmailService()._send_raw_email(f"{phone}@vtext.com", "SMS ALERT", sms_body)
                return True
            
            return False
        except Exception as e:
            log.error(f"SMS Dispatch Fail ({self._mode}): {e}")
            return False
