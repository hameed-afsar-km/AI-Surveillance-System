"""
email_service.py – SMTP email alerts with department routing, retry and cooldown.

Department Routing:
  fire_hazard       → EMAIL_DEPT_FIRE, EMAIL_DEPT_POLICE
  collision         → EMAIL_DEPT_POLICE, EMAIL_DEPT_MEDICAL
  medical_emergency → EMAIL_DEPT_MEDICAL, EMAIL_DEPT_POLICE
  littering         → EMAIL_DEPT_MUNICIPAL
  garbage_hotspot   → EMAIL_DEPT_MUNICIPAL
  overcrowding      → EMAIL_DEPT_POLICE
"""

from __future__ import annotations

import os
import smtplib
import threading
import time
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

from config import cfg
from utils.logger import get_logger

log = get_logger("services.email")


def _html_template(
    alert_type: str,
    people_count: int,
    message: str,
    ai_insight: str,
    timestamp: str,
    dept_label: str = "",
) -> str:
    severity_color = {
        "fire_hazard":       "#dc2626",
        "collision":         "#ea580c",
        "medical_emergency": "#db2777",
        "littering":         "#ca8a04",
        "garbage_hotspot":   "#16a34a",
        "overcrowding":      "#e53e3e",
    }.get(alert_type, "#718096")

    return f"""
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8"/>
  <title>AI Surveillance Alert</title>
</head>
<body style="margin:0;padding:0;background:#0f172a;font-family:Arial,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0"
         style="background:#0f172a;padding:24px 0;">
    <tr><td align="center">
      <table width="600" cellpadding="0" cellspacing="0"
             style="background:#1e293b;border-radius:12px;overflow:hidden;
                    border:1px solid #334155;">

        <!-- Header -->
        <tr>
          <td style="background:{severity_color};padding:20px 30px;">
            <h1 style="color:#fff;margin:0;font-size:22px;">
              ⚠️ AI SURVEILLANCE ALERT
            </h1>
            <p style="color:rgba(255,255,255,0.85);margin:4px 0 0;">
              Dept Notified: <strong>{dept_label}</strong>
            </p>
          </td>
        </tr>

        <!-- Body -->
        <tr>
          <td style="padding:28px 30px;">
            <table width="100%">
              <tr>
                <td style="padding:10px 0;border-bottom:1px solid #334155;">
                  <span style="color:#94a3b8;font-size:13px;">ALERT TYPE</span><br/>
                  <span style="color:#f1f5f9;font-size:18px;font-weight:bold;
                               text-transform:uppercase;">{alert_type.replace('_',' ')}</span>
                </td>
              </tr>
              <tr>
                <td style="padding:14px 0;border-bottom:1px solid #334155;">
                  <span style="color:#94a3b8;font-size:13px;">TIMESTAMP</span><br/>
                  <span style="color:#f1f5f9;font-size:15px;">{timestamp}</span>
                </td>
              </tr>
              <tr>
                <td style="padding:14px 0;border-bottom:1px solid #334155;">
                  <span style="color:#94a3b8;font-size:13px;">SYSTEM MESSAGE</span><br/>
                  <span style="color:#cbd5e1;font-size:14px;">{message}</span>
                </td>
              </tr>
              <tr>
                <td style="padding:16px 0;">
                  <span style="color:#94a3b8;font-size:13px;">🤖 AI INSIGHT (Gemini)</span><br/>
                  <div style="background:#0f172a;border-left:3px solid #3b82f6;
                              padding:12px 16px;margin-top:8px;border-radius:4px;">
                    <span style="color:#93c5fd;font-size:14px;line-height:1.6;">
                      {ai_insight or "No AI insight available."}
                    </span>
                  </div>
                </td>
              </tr>
            </table>
          </td>
        </tr>

        <!-- Footer -->
        <tr>
          <td style="background:#0f172a;padding:16px 30px;text-align:center;">
            <p style="color:#475569;font-size:12px;margin:0;">
              Automated alert from the AI Surveillance System.<br/>
              Do not reply to this email.
            </p>
          </td>
        </tr>

      </table>
    </td></tr>
  </table>
</body>
</html>
""".strip()


class EmailService:
    """Thread-safe email alert sender with per-department routing, cooldown and retry."""

    # Map alert_type → which env variables hold the recipient addresses
    DEPT_ROUTING: dict = {
        "fire_hazard":       ["EMAIL_DEPT_FIRE"],
        "collision":         ["EMAIL_DEPT_ACCIDENT"],
        "medical_emergency": ["EMAIL_DEPT_MEDICAL"],
        "littering":         ["EMAIL_DEPT_MUNICIPAL"],
        "garbage_hotspot":   ["EMAIL_DEPT_MUNICIPAL"],
        "overcrowding":      ["EMAIL_DEPT_TRAFFIC"],
        "test_connection":   ["EMAIL_SENDER"],
    }

    DEPT_LABELS: dict = {
        "fire_hazard":       "Fire Department",
        "collision":         "Accident Response Department",
        "medical_emergency": "Health Department",
        "littering":         "Garbage/Municipal Department",
        "garbage_hotspot":   "Garbage/Municipal Department",
        "overcrowding":      "Traffic Department",
        "test_connection":   "System Debug",
    }

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._last_sent: dict[str, float] = {}  # per alert_type cooldown
        self.reload_config()

    def reload_config(self) -> None:
        """Called when settings are updated from the UI to refresh email settings"""
        with self._lock:
            self._enabled = bool(cfg.EMAIL_SENDER and cfg.EMAIL_PASSWORD)
            if not self._enabled:
                log.warning("Email alerts disabled – EMAIL_SENDER or EMAIL_PASSWORD not set.")
            else:
                log.info("Email alerts ENABLED for sender: %s", cfg.EMAIL_SENDER)

    def _get_recipients(self, alert_type: str) -> list[str]:
        """Return the right department email(s) for this alert type."""
        dept_keys = self.DEPT_ROUTING.get(alert_type, [])
        recipients = []
        for key in dept_keys:
            val = os.getenv(key, "").strip()
            if val:
                recipients.extend([e.strip() for e in val.split(",") if e.strip()])
        # Fallback: send to all generic recipients if dept routing not configured
        if not recipients and hasattr(cfg, "EMAIL_RECIPIENTS"):
            recipients = list(cfg.EMAIL_RECIPIENTS)
        return recipients

    # ── public ────────────────────────────────────────────────────────────────

    def send_alert(
        self,
        alert_type: str,
        people_count: int,
        message: str,
        ai_insight: str,
        *,
        force: bool = False,
    ) -> bool:
        if not self._enabled:
            return False

        with self._lock:
            now = time.time()
            last = self._last_sent.get(alert_type, 0.0)
            if not force and (now - last) < cfg.EMAIL_ALERT_COOLDOWN:
                remaining = cfg.EMAIL_ALERT_COOLDOWN - (now - last)
                log.debug("Email cooldown active for '%s' (%.0fs remaining).", alert_type, remaining)
                return False

            recipients = self._get_recipients(alert_type)
            dept_label = self.DEPT_LABELS.get(alert_type, "Surveillance Team")
            success = self._send_with_retry(alert_type, people_count, message, ai_insight, recipients, dept_label)
            if success:
                self._last_sent[alert_type] = time.time()
            return success

    # ── private ───────────────────────────────────────────────────────────────

    def _send_with_retry(
        self,
        alert_type: str,
        people_count: int,
        message: str,
        ai_insight: str,
        recipients: list[str],
        dept_label: str,
        max_retries: int = 3,
    ) -> bool:
        if not recipients:
            log.warning("No recipients configured for alert_type='%s'", alert_type)
            return False

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        subject = f"🚨 [{dept_label}] Surveillance Alert: {alert_type.replace('_', ' ').title()}"

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"]    = cfg.EMAIL_SENDER
        msg["To"]      = ", ".join(recipients)

        plain = (
            f"SURVEILLANCE ALERT\n"
            f"Department: {dept_label}\n"
            f"Type: {alert_type}\n"
            f"Time: {timestamp}\n"
            f"Message: {message}\n"
            f"AI Insight: {ai_insight}"
        )
        html = _html_template(alert_type, people_count, message, ai_insight, timestamp, dept_label)

        msg.attach(MIMEText(plain, "plain"))
        msg.attach(MIMEText(html, "html"))

        for attempt in range(1, max_retries + 1):
            try:
                with smtplib.SMTP(cfg.SMTP_HOST, cfg.SMTP_PORT, timeout=15) as server:
                    server.ehlo()
                    server.starttls()
                    server.login(cfg.EMAIL_SENDER, cfg.EMAIL_PASSWORD)
                    server.sendmail(cfg.EMAIL_SENDER, recipients, msg.as_string())
                log.info(
                    "Alert email → '%s' (%d recipients) | type=%s",
                    dept_label, len(recipients), alert_type,
                )
                return True
            except Exception as exc:
                wait = 2 ** attempt
                log.warning("Email attempt %d/%d failed: %s (retry in %ds)", attempt, max_retries, exc, wait)
                if attempt < max_retries:
                    time.sleep(wait)

        log.error("All email retry attempts failed for alert_type='%s'.", alert_type)
        return False
