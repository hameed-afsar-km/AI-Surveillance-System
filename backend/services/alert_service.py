"""
alert_service.py – Central alert dispatcher.

Coordinates:
  • Sound alerts  (playsound with cooldown)
  • Email alerts  (via EmailService)
  • Gemini insights (via GeminiService)
  • Event logging (via logger.log_event)
  • Decision engine: combine behavior + rule alerts
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Optional

from config import cfg
from logic.behavior import BehaviorAlert
from logic.rule_engine import RuleMatch
from services.email_service import EmailService
from services.gemini_service import GeminiService
from utils.logger import get_logger, log_event

log = get_logger("services.alert")


# ── Decision output ───────────────────────────────────────────────────────────


@dataclass
class Decision:
    alert: bool
    alert_type: str
    message: str
    severity: str = "none"
    ai_insight: str = ""
    people_count: int = 0
    involved_ids: list[int] = field(default_factory=list)
    zone: Optional[str] = None
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            "alert": self.alert,
            "type": self.alert_type,
            "message": self.message,
            "severity": self.severity,
            "ai_insight": self.ai_insight,
            "people_count": self.people_count,
            "involved_ids": self.involved_ids,
            "zone": self.zone,
            "timestamp": self.timestamp,
        }


_NO_DECISION = Decision(
    alert=False,
    alert_type="none",
    message="System nominal. No threats detected.",
    severity="none",
)


# ── Alert Service ─────────────────────────────────────────────────────────────


class AlertService:
    """
    Central alert dispatcher.

    Call process(behavior_alert, rule_matches, active_tracks) every frame.
    Frame-level data is evaluated; alerts are only dispatched respecting cooldowns.
    """

    def __init__(self) -> None:
        self._email_svc = EmailService()
        self._gemini_svc = GeminiService()
        self._lock = threading.Lock()

        # Sound cooldown
        self._last_sound_time: float = 0.0
        self._sound_enabled: bool = True
        self._ai_enabled: bool = True

        # Per-type alert cooldown tracking
        self._last_alert_times: dict[str, float] = {}
        self._alert_cooldown: int = cfg.SOUND_ALERT_COOLDOWN
        log.info("AlertService initialised.")

    def _no_decision(self) -> Decision:
        """Return a safe nominal decision — used only as a crash fallback."""
        return Decision(alert=False, alert_type="none", message="System nominal.", severity="none")

    # ── public ────────────────────────────────────────────────────────────────

    def process(
        self,
        behavior_alert: BehaviorAlert,
        rule_matches: list[RuleMatch],
        active_tracks,  # list[TrackState]
    ) -> Decision:
        """
        Decision engine: merge behavior + rule alerts → produce Decision.
        Trigger sound / email as appropriate.
        """
        people_count = len(active_tracks)
        duration_data = self._compute_duration_data(active_tracks)

        # Pick highest-priority source
        decision = self._merge_alerts(behavior_alert, rule_matches, people_count)

        if not decision.alert:
            return _NO_DECISION

        # Rate-limit per type
        if not self._should_dispatch(decision.alert_type):
            # Still return the decision (UI needs to know) but skip side effects
            return decision

        # Get AI insight
        ai_insight = ""
        if self._ai_enabled:
            ai_insight = self._gemini_svc.get_alert_insight(
                alert_type=decision.alert_type,
                people_count=people_count,
                message=decision.message,
                duration_data=duration_data,
            )
        decision.ai_insight = ai_insight

        # Register dispatch time
        self._register_dispatch(decision.alert_type)

        # Log event
        log_event(
            event_type=decision.alert_type,
            message=decision.message,
            extra={
                "people_count": people_count,
                "severity": decision.severity,
                "ai_insight": ai_insight,
            },
        )
        log.warning("ALERT dispatched | type=%s | count=%d | %s",
                    decision.alert_type, people_count, decision.message[:80])

        # Sound alert (non-blocking)
        threading.Thread(target=self._play_sound, daemon=True).start()

        # Email alert (non-blocking)
        threading.Thread(
            target=self._email_svc.send_alert,
            args=(decision.alert_type, people_count, decision.message, ai_insight),
            daemon=True,
        ).start()

        return decision

    def get_periodic_summary(self, people_count: int, uptime: float, history: list) -> str | None:
        if not self._ai_enabled:
            return None
        return self._gemini_svc.get_periodic_summary(people_count, uptime, history)

    def toggle_sound(self, enabled: bool) -> None:
        self._sound_enabled = enabled
        log.info("Sound alerts %s.", "enabled" if enabled else "disabled")

    def toggle_ai(self, enabled: bool) -> None:
        self._ai_enabled = enabled
        log.info("AI insights %s.", "enabled" if enabled else "disabled")

    # ── private ───────────────────────────────────────────────────────────────

    @staticmethod
    def _merge_alerts(
        behavior_alert: BehaviorAlert,
        rule_matches: list[RuleMatch],
        people_count: int,
    ) -> Decision:
        severity_order = {"none": 0, "low": 1, "medium": 2, "high": 3, "critical": 4}
        candidates: list[Decision] = []

        if behavior_alert.alert:
            candidates.append(Decision(
                alert=True,
                alert_type=behavior_alert.alert_type,
                message=behavior_alert.message,
                severity=behavior_alert.severity,
                people_count=people_count,
                involved_ids=behavior_alert.involved_ids,
                zone=behavior_alert.zone,
            ))

        for rm in rule_matches:
            candidates.append(Decision(
                alert=True,
                alert_type="custom",
                message=rm.message,
                severity=rm.severity,
                people_count=rm.people_count,
                zone=rm.zone,
            ))

        if not candidates:
            return _NO_DECISION

        candidates.sort(
            key=lambda d: severity_order.get(d.severity, 0),
            reverse=True,
        )
        return candidates[0]

    def _should_dispatch(self, alert_type: str) -> bool:
        now = time.time()
        last = self._last_alert_times.get(alert_type, 0.0)
        return (now - last) >= self._alert_cooldown

    def _register_dispatch(self, alert_type: str) -> None:
        self._last_alert_times[alert_type] = time.time()

    def _play_sound(self) -> None:
        if not self._sound_enabled:
            return
        now = time.time()
        if now - self._last_sound_time < cfg.SOUND_ALERT_COOLDOWN:
            return
        self._last_sound_time = now
        sound_path = cfg.ALERT_SOUND_PATH
        if not sound_path.exists():
            log.debug("Alert sound file not found: %s – skipping.", sound_path)
            return
        try:
            from playsound import playsound
            playsound(str(sound_path), block=False)
        except Exception as exc:
            log.warning("Sound alert failed: %s", exc)

    @staticmethod
    def _compute_duration_data(active_tracks) -> dict:
        if not active_tracks:
            return {"max_duration": 0.0, "avg_duration": 0.0}
        durations = [t.duration for t in active_tracks]
        return {
            "max_duration": max(durations),
            "avg_duration": sum(durations) / len(durations),
        }
