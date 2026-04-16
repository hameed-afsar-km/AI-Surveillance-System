"""
config.py – Central configuration loader
All modules import from here; never read .env directly elsewhere.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Limit CPU thread contention from PyTorch/OpenBLAS on Windows
os.environ.setdefault("OMP_NUM_THREADS", "2")
os.environ.setdefault("MKL_NUM_THREADS", "2")
os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")

# Resolve project root (two levels up from backend/)
ROOT_DIR = Path(__file__).resolve().parent.parent
load_dotenv(ROOT_DIR / ".env")


class Config:
    # ── Flask ──────────────────────────────────────────────
    FLASK_HOST: str = os.getenv("FLASK_HOST", "0.0.0.0")
    FLASK_PORT: int = int(os.getenv("FLASK_PORT", 5050))
    FLASK_DEBUG: bool = os.getenv("FLASK_DEBUG", "False").lower() == "true"
    SECRET_KEY: str = os.getenv("SECRET_KEY", "change-me")

    # ── Gemini ─────────────────────────────────────────────
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL: str = "gemini-2.5-flash"
    GEMINI_PERIODIC_INTERVAL: int = int(
        os.getenv("GEMINI_PERIODIC_SUMMARY_INTERVAL", 60)
    )

    # ── Email ──────────────────────────────────────────────
    EMAIL_SENDER: str = os.getenv("EMAIL_SENDER", "")
    EMAIL_PASSWORD: str = os.getenv("EMAIL_PASSWORD", "")
    EMAIL_RECIPIENTS: list[str] = [
        r.strip()
        for r in os.getenv("EMAIL_RECIPIENTS", "").split(",")
        if r.strip()
    ]
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    
    # ── SMS (Twilio) ───────────────────────────────────────
    TWILIO_SID: str = os.getenv("TWILIO_SID", "")
    TWILIO_AUTH_TOKEN: str = os.getenv("TWILIO_AUTH_TOKEN", "")
    TWILIO_PHONE_NUMBER: str = os.getenv("TWILIO_PHONE_NUMBER", "")
    RECIPIENT_PHONE: str = os.getenv("RECIPIENT_PHONE", "")

    # ── Thresholds ─────────────────────────────────────────
    OVERCROWDING_THRESHOLD: int = int(os.getenv("OVERCROWDING_THRESHOLD", 5))
    LOITERING_THRESHOLD_SECONDS: int = int(
        os.getenv("LOITERING_THRESHOLD_SECONDS", 30)
    )
    CROWD_FORMATION_DELTA: int = int(os.getenv("CROWD_FORMATION_DELTA", 3))

    # ── Cooldowns ──────────────────────────────────────────
    SOUND_ALERT_COOLDOWN: int = int(os.getenv("SOUND_ALERT_COOLDOWN", 30))
    EMAIL_ALERT_COOLDOWN: int = int(os.getenv("EMAIL_ALERT_COOLDOWN", 120))

    # ── Video ──────────────────────────────────────────────
    DEFAULT_VIDEO_SOURCE: str = os.getenv("DEFAULT_VIDEO_SOURCE", "webcam")
    DEFAULT_WEBCAM_INDEX: int = int(os.getenv("DEFAULT_WEBCAM_INDEX", 0))

    # ── Paths ──────────────────────────────────────────────
    YOLO_MODEL_PATH: Path = ROOT_DIR / os.getenv("YOLO_MODEL_PATH", "models/yolo11n.pt")
    RULES_FILE: Path = ROOT_DIR / os.getenv("RULES_FILE", "backend/data/rules.json")
    LOGS_FILE: Path = ROOT_DIR / os.getenv("LOGS_FILE", "backend/data/logs.json")
    ALERT_SOUND_PATH: Path = ROOT_DIR / os.getenv(
        "ALERT_SOUND_PATH", "assets/sounds/alert.wav"
    )
    VIDEOS_DIR: Path = ROOT_DIR / "videos"

    # ── Detection ──────────────────────────────────────────────
    YOLO_CONFIDENCE: float = 0.25   # Sensitive enough for distant/small people & bikes
    YOLO_IMGSZ: int = 320           # 320 = fastest CPU inference (~2x faster than 416)
    # COCO classes: 0=person, 1=bicycle, 2=car, 3=motorcycle, 5=bus, 7=truck, 9=traffic light, 10=fire hydrant, 11=stop sign, 24=backpack, 39=bottle, 41=cup
    TRACKED_CLASSES: list[int] = [0, 1, 2, 3, 5, 7, 24, 39, 41]
    TARGET_FPS: int = 30       # Camera capture target FPS
    STREAM_FPS: int = 30       # MJPEG stream target FPS (decoupled from inference)
    MAX_STREAM_WIDTH: int = 640


cfg = Config()
