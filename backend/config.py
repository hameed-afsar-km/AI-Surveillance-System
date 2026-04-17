"""
config.py – Central configuration loader
All modules import from here; never read .env directly elsewhere.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Limit CPU thread contention from PyTorch/OpenBLAS on Windows
os.environ.setdefault("OMP_NUM_THREADS", "4")
os.environ.setdefault("MKL_NUM_THREADS", "4")
os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")
os.environ.setdefault("ULTRALYTICS_OFFLINE", "TRUE")
os.environ.setdefault("YOLO_VERBOSE", "FALSE")
os.environ.setdefault("CHECK_EXT_URL", "0")

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
    
    # ── SMS / Mobile Alerting ──────────────────────────────────
    SMS_MODE: str = os.getenv("SMS_MODE", "cloud") # "cloud", "local", "email_gateway"
    MOBILE_GATEWAY_URL: str = os.getenv("MOBILE_GATEWAY_URL", "http://192.168.1.15:8080")
    
    PHONE_ACCIDENT: str = os.getenv("PHONE_ACCIDENT", "")
    PHONE_FIRE: str = os.getenv("PHONE_FIRE", "")
    PHONE_GARBAGE: str = os.getenv("PHONE_GARBAGE", "")
    PHONE_HEALTH: str = os.getenv("PHONE_HEALTH", "")
    PHONE_TRAFFIC: str = os.getenv("PHONE_TRAFFIC", "")

    # Legacy (keeping for compat)
    TWILIO_SID: str = os.getenv("TWILIO_SID", "")
    TWILIO_AUTH_TOKEN: str = os.getenv("TWILIO_AUTH_TOKEN", "")
    TWILIO_PHONE_NUMBER: str = os.getenv("TWILIO_PHONE_NUMBER", "")

    # ── Thresholds ─────────────────────────────────────────
    OVERCROWDING_THRESHOLD: int = int(os.getenv("OVERCROWDING_THRESHOLD", 5))
    LOITERING_THRESHOLD_SECONDS: int = int(
        os.getenv("LOITERING_THRESHOLD_SECONDS", 30)
    )
    CROWD_FORMATION_DELTA: int = int(os.getenv("CROWD_FORMATION_DELTA", 3))

    # ── Cooldowns ──────────────────────────────────────────
    SOUND_ALERT_COOLDOWN: int = int(os.getenv("SOUND_ALERT_COOLDOWN", 30))
    EMAIL_ALERT_COOLDOWN: int = int(os.getenv("EMAIL_ALERT_COOLDOWN", 120))

    # ── Video & Spatial ────────────────────────────────────
    DEFAULT_VIDEO_SOURCE: str = os.getenv("DEFAULT_VIDEO_SOURCE", "webcam")
    DEFAULT_WEBCAM_INDEX: int = int(os.getenv("DEFAULT_WEBCAM_INDEX", 0))
    CAMERA_LOCATION: str = os.getenv("CAMERA_LOCATION", "Terminal A - Checkpoint 1")

    # ── Paths ──────────────────────────────────────────────
    YOLO_MODEL_PATH: Path = ROOT_DIR / os.getenv("YOLO_MODEL_PATH", "models/yolov8n.pt")
    RULES_FILE: Path = ROOT_DIR / os.getenv("RULES_FILE", "backend/data/rules.json")
    LOGS_FILE: Path = ROOT_DIR / os.getenv("LOGS_FILE", "backend/data/logs.json")
    ALERT_SOUND_PATH: Path = ROOT_DIR / os.getenv(
        "ALERT_SOUND_PATH", "assets/sounds/alert.wav"
    )
    VIDEOS_DIR: Path = ROOT_DIR / "videos"

    # ── Detection ──────────────────────────────────────────────
    # Custom trained model for event detection (accident, fall, fire, garbage)
    CUSTOM_MODEL_PATH: Path = ROOT_DIR / os.getenv("CUSTOM_MODEL_PATH", "models/custom_best.pt")
    CUSTOM_CONFIDENCE: float = float(os.getenv("CUSTOM_CONFIDENCE", "0.25"))

    YOLO_CONFIDENCE: float = 0.28
    YOLO_IMGSZ: int = 416 # Optimized for speed
    # COCO classes: 0=person, 1=bicycle, 2=car, 3=motorcycle, 5=bus, 7=truck, 24=backpack, 26=handbag, 28=suitcase, 39=bottle, 41=cup, 63=laptop, 67=cell phone
    TRACKED_CLASSES: list[int] = [0, 1, 2, 3, 5, 7, 24, 26, 28, 39, 41, 63, 67]
    TARGET_FPS: int = 30       # Camera capture target FPS
    STREAM_FPS: int = 30       # MJPEG stream target FPS (decoupled from inference)
    MAX_STREAM_WIDTH: int = 640


cfg = Config()
