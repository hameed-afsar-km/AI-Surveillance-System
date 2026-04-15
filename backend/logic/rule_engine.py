"""
rule_engine.py – Dynamic custom rule evaluator.

Loads rules from rules.json and evaluates them against live system state.
Rules can be hot-reloaded without restarting the backend.
"""

from __future__ import annotations

import json
import operator
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from config import cfg
from utils.logger import get_logger

log = get_logger("logic.rule_engine")

# ── Rule data class ───────────────────────────────────────────────────────────


@dataclass
class Rule:
    name: str
    description: str
    conditions: dict[str, str | int | float]
    alert_type: str
    severity: str
    enabled: bool

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "conditions": self.conditions,
            "alert_type": self.alert_type,
            "severity": self.severity,
            "enabled": self.enabled,
        }


@dataclass
class RuleMatch:
    alert: bool
    rule_name: str
    message: str
    severity: str
    people_count: int = 0
    zone: str | None = None
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            "alert": self.alert,
            "type": "custom",
            "rule_name": self.rule_name,
            "message": self.message,
            "severity": self.severity,
            "people_count": self.people_count,
            "zone": self.zone,
            "timestamp": self.timestamp,
        }


# ── Operator map ──────────────────────────────────────────────────────────────

_OPS: dict[str, Callable[[Any, Any], bool]] = {
    ">":  operator.gt,
    ">=": operator.ge,
    "<":  operator.lt,
    "<=": operator.le,
    "==": operator.eq,
    "!=": operator.ne,
}


def _parse_condition(raw: str) -> tuple[str, float] | None:
    """
    Parse a condition string like '>3' or '>=20' into (op_str, value).
    Returns None if raw is not a numeric expression (e.g. zone name).
    """
    raw = str(raw).strip()
    for op in (">=", "<=", "==", "!=", ">", "<"):
        if raw.startswith(op):
            try:
                return op, float(raw[len(op):].strip())
            except ValueError:
                return None
    # Plain number – treat as ==
    try:
        return "==", float(raw)
    except ValueError:
        return None


# ── Engine ────────────────────────────────────────────────────────────────────


class RuleEngine:
    """
    Loads JSON rules, evaluates them against system state each cycle.

    System state interface:
        {
            "people_count": int,
            "max_duration": float,         # longest track duration (seconds)
            "active_zones": set[str],      # zones currently occupied
            "active_ids": list[int],
        }
    """

    def __init__(self, rules_path: Path | None = None) -> None:
        self._path = Path(rules_path or cfg.RULES_FILE)
        self._rules: list[Rule] = []
        self._lock = threading.Lock()
        self._last_mtime: float = 0.0
        self._load()

    # ── public ────────────────────────────────────────────────────────────────

    def evaluate(self, state: dict) -> list[RuleMatch]:
        """
        Evaluate all enabled rules against the current state.

        Returns a list of RuleMatch objects for every rule that fired.
        """
        self._maybe_hot_reload()
        matches: list[RuleMatch] = []

        with self._lock:
            rules_snapshot = list(self._rules)

        for rule in rules_snapshot:
            if not rule.enabled:
                continue
            match = self._evaluate_rule(rule, state)
            if match and match.alert:
                matches.append(match)

        return matches

    def get_rules(self) -> list[Rule]:
        with self._lock:
            return list(self._rules)

    def reload(self) -> None:
        """Force reload rules from disk."""
        self._load()

    def save_rules(self, rules: list[dict]) -> None:
        """Persist a new ruleset to JSON."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._lock:
            with open(self._path, "w", encoding="utf-8") as fh:
                json.dump(rules, fh, indent=2)
        self._load()
        log.info("Rules saved (%d rules).", len(rules))

    # ── private ───────────────────────────────────────────────────────────────

    def _load(self) -> None:
        try:
            if not self._path.exists():
                log.warning("Rules file not found: %s", self._path)
                return
            mtime = self._path.stat().st_mtime
            with self._lock:
                raw = json.loads(self._path.read_text(encoding="utf-8"))
                self._rules = [
                    Rule(
                        name=r.get("name", "Unnamed"),
                        description=r.get("description", ""),
                        conditions=r.get("conditions", {}),
                        alert_type=r.get("alert_type", "custom"),
                        severity=r.get("severity", "medium"),
                        enabled=r.get("enabled", True),
                    )
                    for r in raw
                ]
                self._last_mtime = mtime
            log.info("Rules loaded: %d rules from %s", len(self._rules), self._path)
        except Exception as exc:
            log.error("Failed to load rules: %s", exc)

    def _maybe_hot_reload(self) -> None:
        try:
            mtime = self._path.stat().st_mtime
            if mtime != self._last_mtime:
                log.info("Rules file changed – hot-reloading …")
                self._load()
        except Exception:
            pass

    def _evaluate_rule(self, rule: Rule, state: dict) -> RuleMatch | None:
        conds = rule.conditions
        people_count = state.get("people_count", 0)
        max_duration = state.get("max_duration", 0.0)
        active_zones: set[str] = state.get("active_zones", set())

        # Zone check (string equality – not numeric)
        if "zone" in conds:
            required_zone = str(conds["zone"]).strip()
            if required_zone not in active_zones:
                return None  # zone condition not met → no match

        # Numeric condition checks
        numeric_map = {
            "people_count": people_count,
            "duration": max_duration,
        }
        for key, expected in conds.items():
            if key == "zone":
                continue
            actual = numeric_map.get(key)
            if actual is None:
                continue
            parsed = _parse_condition(str(expected))
            if parsed is None:
                continue
            op_str, threshold = parsed
            op_fn = _OPS.get(op_str)
            if op_fn is None:
                continue
            if not op_fn(actual, threshold):
                return None  # condition not met

        # All conditions satisfied → alert!
        zone_str = conds.get("zone")
        return RuleMatch(
            alert=True,
            rule_name=rule.name,
            message=(
                f"Custom rule '{rule.name}' triggered: {rule.description}. "
                f"Current count={people_count}, max_duration={max_duration:.0f}s."
            ),
            severity=rule.severity,
            people_count=people_count,
            zone=str(zone_str) if zone_str else None,
        )
