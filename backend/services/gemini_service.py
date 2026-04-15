"""
gemini_service.py – Google Gemini AI integration (strictly rate-limited).

Rules:
  • NEVER called per-frame
  • Called ONLY on alert or periodic summary (every N seconds)
  • Response is cached to avoid duplicate calls for same alert type
  • Graceful degradation when API is unavailable
"""

from __future__ import annotations

import hashlib
import time
import threading
from typing import Optional

import google.generativeai as genai

from config import cfg
from utils.logger import get_logger

log = get_logger("services.gemini")


class GeminiService:
    """Rate-limited, cached Gemini insight generator."""

    _SYSTEM_PROMPT = (
        "You are an AI security analyst monitoring a real-time surveillance system. "
        "When given information about detected behaviors, provide a concise 2-3 line "
        "insight explaining the situation and recommend an immediate action. "
        "Be professional, clear, and actionable. Do not use bullet points or markdown."
    )

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._cache: dict[str, tuple[str, float]] = {}  # key → (response, timestamp)
        self._cache_ttl: int = 300  # 5 minutes

        # Rate limiting
        self._last_call_time: float = 0.0
        self._min_call_interval: float = 10.0  # minimum 10s between any API calls
        self._call_count: int = 0
        self._max_calls_per_hour: int = 100
        self._hour_start: float = time.time()

        # Periodic summary tracking
        self._last_summary_time: float = 0.0

        self._model: Optional[genai.GenerativeModel] = None
        self._initialize()

    # ── init ──────────────────────────────────────────────────────────────────

    def _initialize(self) -> None:
        if not cfg.GEMINI_API_KEY:
            log.warning("GEMINI_API_KEY not set – AI insights will be disabled.")
            return
        try:
            genai.configure(api_key=cfg.GEMINI_API_KEY)
            self._model = genai.GenerativeModel(
                model_name=cfg.GEMINI_MODEL,
                system_instruction=self._SYSTEM_PROMPT,
            )
            log.info("Gemini model '%s' initialised.", cfg.GEMINI_MODEL)
        except Exception as exc:
            log.error("Gemini initialisation failed: %s", exc)
            self._model = None

    # ── public ────────────────────────────────────────────────────────────────

    def get_alert_insight(
        self,
        alert_type: str,
        people_count: int,
        message: str,
        duration_data: dict | None = None,
    ) -> str:
        """
        Generate an AI insight for an alert event.
        Returns cached result if the same alert fired recently.
        """
        cache_key = self._make_key(alert_type, people_count, message)
        cached = self._get_cached(cache_key)
        if cached:
            log.debug("Gemini cache hit for alert_type='%s'", alert_type)
            return cached

        prompt = self._build_alert_prompt(alert_type, people_count, message, duration_data)
        response = self._call_api(prompt)

        if response:
            self._set_cache(cache_key, response)
        return response or self._fallback_insight(alert_type, people_count)

    def get_periodic_summary(
        self,
        people_count: int,
        uptime_seconds: float,
        alert_history: list[dict],
    ) -> str | None:
        """
        Generate a session summary at maximum once per GEMINI_PERIODIC_INTERVAL seconds.
        Returns None if interval hasn't passed yet.
        """
        now = time.time()
        if now - self._last_summary_time < cfg.GEMINI_PERIODIC_INTERVAL:
            return None

        self._last_summary_time = now
        prompt = self._build_summary_prompt(people_count, uptime_seconds, alert_history)
        return self._call_api(prompt) or "Periodic summary unavailable."

    # ── private ───────────────────────────────────────────────────────────────

    def _call_api(self, prompt: str) -> str | None:
        if self._model is None:
            return None

        with self._lock:
            if not self._check_rate_limit():
                log.warning("Gemini rate limit reached – skipping call.")
                return None
            try:
                response = self._model.generate_content(prompt)
                self._call_count += 1
                self._last_call_time = time.time()
                text = response.text.strip()
                log.debug("Gemini response (len=%d): %s…", len(text), text[:80])
                return text
            except Exception as exc:
                err_msg = str(exc).lower()
                if "429" in err_msg or "quota" in err_msg or "limit" in err_msg:
                    log.warning("Gemini Quota Exceeded. Falling back to local intelligence.")
                else:
                    log.error("Gemini API error: %s", exc)
                return None

    def _check_rate_limit(self) -> bool:
        now = time.time()
        # Reset hourly counter
        if now - self._hour_start >= 3600:
            self._call_count = 0
            self._hour_start = now
        # Minimum interval between calls
        if now - self._last_call_time < self._min_call_interval:
            return False
        # Hourly cap
        if self._call_count >= self._max_calls_per_hour:
            return False
        return True

    def _get_cached(self, key: str) -> str | None:
        entry = self._cache.get(key)
        if entry:
            response, ts = entry
            if time.time() - ts < self._cache_ttl:
                return response
            del self._cache[key]
        return None

    def _set_cache(self, key: str, value: str) -> None:
        self._cache[key] = (value, time.time())
        # Prune old entries
        now = time.time()
        self._cache = {
            k: v for k, v in self._cache.items()
            if now - v[1] < self._cache_ttl
        }

    @staticmethod
    def _make_key(*parts) -> str:
        raw = "|".join(str(p) for p in parts)
        return hashlib.md5(raw.encode()).hexdigest()

    @staticmethod
    def _build_alert_prompt(
        alert_type: str,
        people_count: int,
        message: str,
        duration_data: dict | None,
    ) -> str:
        dur_info = ""
        if duration_data:
            max_d = duration_data.get("max_duration", 0)
            avg_d = duration_data.get("avg_duration", 0)
            dur_info = f" The longest presence is {max_d:.0f}s, average {avg_d:.0f}s."

        return (
            f"SURVEILLANCE ALERT DETECTED.\n"
            f"Alert type: {alert_type.upper()}\n"
            f"People currently visible: {people_count}\n"
            f"System message: {message}{dur_info}\n\n"
            f"Provide a concise security insight and recommended action in 2-3 sentences."
        )

    @staticmethod
    def _build_summary_prompt(
        people_count: int,
        uptime_seconds: float,
        alert_history: list[dict],
    ) -> str:
        uptime_min = uptime_seconds / 60
        recent = alert_history[-5:] if len(alert_history) > 5 else alert_history
        alert_summary = "; ".join(
            f"{a.get('type','?')} at {a.get('timestamp','?')}"
            for a in recent
        ) or "no recent alerts"

        return (
            f"PERIODIC SURVEILLANCE SUMMARY.\n"
            f"System uptime: {uptime_min:.1f} minutes\n"
            f"Current people count: {people_count}\n"
            f"Recent alerts: {alert_summary}\n\n"
            f"Provide a brief 2-3 sentence security situation summary and recommendation."
        )

    @staticmethod
    def _fallback_insight(alert_type: str, people_count: int) -> str:
        """Offline fallback message when Gemini is unavailable."""
        fallbacks = {
            "overcrowding": (
                f"Overcrowding detected with {people_count} people. "
                "Recommend dispersing the crowd and monitoring exits."
            ),
            "loitering": (
                "Loitering detected. An individual has remained stationary for an "
                "extended period. Recommend verification by security personnel."
            ),
            "restricted_zone": (
                "Restricted zone violation detected. Immediate intervention required. "
                "Contact on-site security."
            ),
            "sudden_crowd": (
                "Rapid crowd formation detected. Monitor the situation closely "
                "and prepare crowd management protocols."
            ),
        }
        return fallbacks.get(
            alert_type,
            f"Alert '{alert_type}' detected with {people_count} people. "
            "Security review recommended.",
        )
