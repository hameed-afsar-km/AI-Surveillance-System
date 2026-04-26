"""
logger.py – Centralised structured logging for the entire backend.
"""

import logging
import json
import threading
from datetime import datetime, timezone
from pathlib import Path

from config import cfg

_lock = threading.Lock()


def _build_file_handler(log_path: Path) -> logging.FileHandler:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    handler = logging.FileHandler(log_path, encoding="utf-8")
    handler.setLevel(logging.DEBUG)
    fmt = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)-25s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    handler.setFormatter(fmt)
    return handler


def get_logger(name: str) -> logging.Logger:
    """Return a named logger with both console and file sinks."""
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger  # already configured

    logger.setLevel(logging.DEBUG)

    # Console
    console = logging.StreamHandler()
    console.setLevel(logging.INFO)
    console.setFormatter(
        logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s",
                          datefmt="%H:%M:%S")
    )

    # File
    file_handler = _build_file_handler(
        cfg.LOGS_FILE.parent / "system.log"
    )

    logger.addHandler(console)
    logger.addHandler(file_handler)
    logger.propagate = False
    return logger


# ── JSON event log (shared across all modules) ───────────────────────────────

_event_log: list[dict] = []
_MAX_EVENTS = 500


def log_event(event_type: str, message: str, extra: dict | None = None) -> dict:
    """Append a structured event to the in-memory log and persist to JSON."""
    entry = {
        "id": len(_event_log) + 1,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "type": event_type,
        "message": message,
        **(extra or {}),
    }
    with _lock:
        _event_log.append(entry)
        if len(_event_log) > _MAX_EVENTS:
            _event_log.pop(0)
        _persist_events()
    return entry


def get_events(last_n: int = 50) -> list[dict]:
    with _lock:
        return list(_event_log[-last_n:])


def clear_events() -> None:
    global _event_log
    with _lock:
        _event_log = []
        _persist_events()


def _persist_events() -> None:
    try:
        cfg.LOGS_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(cfg.LOGS_FILE, "w", encoding="utf-8") as fh:
            json.dump(_event_log[-_MAX_EVENTS:], fh, indent=2)
    except Exception:
        pass  # non-critical


# Load persisted events on startup
def _load_persisted() -> None:
    global _event_log
    try:
        if cfg.LOGS_FILE.exists():
            with open(cfg.LOGS_FILE, encoding="utf-8") as fh:
                _event_log = json.load(fh)
    except Exception:
        _event_log = []


_load_persisted()
