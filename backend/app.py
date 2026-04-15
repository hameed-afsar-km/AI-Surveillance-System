"""
app.py – Flask REST API backend for the AI Surveillance System.

Endpoints:
  GET  /status        – live snapshot of system state
  POST /start         – start the detection loop (with source params)
  POST /stop          – stop the detection loop
  GET  /frame         – JPEG-encoded annotated video frame (MJPEG stream)
  GET  /events        – recent event log
  GET  /rules         – fetch all custom rules
  POST /rules         – save new ruleset
  GET  /health        – simple health-check
"""

from __future__ import annotations

import base64
import sys
import os
import threading
import time
import queue
from pathlib import Path
from typing import Optional

import cv2
import numpy as np
from flask import Flask, Response, jsonify, request, stream_with_context
from flask_cors import CORS

# ── path bootstrap ────────────────────────────────────────────────────────────
_BACKEND = Path(__file__).resolve().parent
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from config import cfg
from vision.video_input import VideoSource
from vision.detection import ObjectDetector
from vision.tracking import ObjectTracker
from logic.behavior import BehaviorEngine
from logic.rule_engine import RuleEngine
from services.alert_service import AlertService, Decision, _NO_DECISION
from utils.logger import get_logger, get_events

log = get_logger("backend.app")

# ── Flask app ─────────────────────────────────────────────────────────────────

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})
app.config["SECRET_KEY"] = cfg.SECRET_KEY

# ── Shared mutable state (protected by _state_lock) ──────────────────────────

_state_lock = threading.Lock()

_system_state: dict = {
    "running": False,
    "people_count": 0,
    "alert": False,
    "alert_type": "none",
    "message": "System not started.",
    "ai_insight": "",
    "severity": "none",
    "active_ids": [],
    "frame_count": 0,
    "uptime": 0.0,
    "source": "none",
    "fps": 0.0,
    "last_decision": {},
    "periodic_summary": "",
    "last_updated": time.time(),
}

_latest_jpeg_bytes: Optional[bytes] = None
_frame_lock = threading.Lock()
_detection_thread: Optional[threading.Thread] = None
_stop_event = threading.Event()
_start_time: float = 0.0

# ── Engine singletons ─────────────────────────────────────────────────────────

_detector: Optional[ObjectDetector] = None
_tracker: Optional[ObjectTracker] = None
_behavior: Optional[BehaviorEngine] = None
_rule_engine: Optional[RuleEngine] = None
_alert_svc: Optional[AlertService] = None


def _init_engines() -> None:
    global _detector, _tracker, _behavior, _rule_engine, _alert_svc
    log.info("Initialising detection engines …")
    _detector    = ObjectDetector()
    _tracker     = ObjectTracker()
    _behavior    = BehaviorEngine()
    _rule_engine = RuleEngine()
    _alert_svc   = AlertService()
    log.info("All engines ready.")


# ── Detection loop ────────────────────────────────────────────────────────────


def _detection_loop(source: VideoSource) -> None:
    global _latest_jpeg_bytes, _start_time

    # Warm up YOLO
    log.info("Warming up neural network...")
    _detector.detect(np.zeros((320, 320, 3), dtype=np.uint8))
    log.info("Warmup complete.")

    _start_time = time.time()
    frame_count = 0
    t_calc = time.time()

    frame_skip = 2           # Process every 2nd frame (balances detection quality vs speed)
    target_fps = 10          # Processing rate cap
    frame_time = 1.0 / target_fps
    fps_window = 10          # FPS measurement window

    log.info("Inference Thread started (source=%s).", source)

    try:
        while not _stop_event.is_set():
            loop_start = time.time()

            # ── Frame Read ────────────────────────────────────────────────────
            try:
                ok, frame = source.read()
            except Exception as e:
                log.warning("Frame read error (skipping): %s", e)
                time.sleep(0.05)
                continue

            if not ok or frame is None:
                time.sleep(0.01)
                continue

            frame_count += 1
            if frame_count % frame_skip != 0:
                continue

            # ── Resize ───────────────────────────────────────────────────────
            try:
                h, w = frame.shape[:2]
                target_w = 640
                scale = target_w / float(w)
                target_h = max(1, int(h * scale))
                interp = cv2.INTER_AREA if scale < 1.0 else cv2.INTER_LINEAR
                frame = cv2.resize(frame, (target_w, target_h), interpolation=interp)
            except Exception as e:
                log.warning("Frame resize error (skipping): %s", e)
                continue

            if frame_count % 30 == 0:
                log.info("Heartbeat: frame=%d FPS=%s", frame_count, _system_state.get('fps', 'N/A'))

            # ── 1. YOLO Detection ─────────────────────────────────────────────
            try:
                detections = _detector.detect(frame)
            except Exception as e:
                log.warning("YOLO error (skipping frame): %s", e)
                detections = []

            # ── 2. DeepSORT Tracking ──────────────────────────────────────────
            try:
                active_tracks = _tracker.update(frame, detections)
            except Exception as e:
                log.warning("Tracker error (skipping frame): %s", e)
                active_tracks = []

            # ── 3. Behavior Analysis ──────────────────────────────────────────
            try:
                behavior_alert = _behavior.analyse(active_tracks, frame)
            except Exception as e:
                log.warning("Behavior engine error: %s", e)
                behavior_alert = None

            rule_state = {
                "people_count": sum(1 for t in active_tracks if t.class_id == 0),
                "max_duration": max((t.duration for t in active_tracks), default=0.0),
                "active_ids":   [t.track_id for t in active_tracks],
            }
            try:
                rule_matches = _rule_engine.evaluate(rule_state)
            except Exception as e:
                log.warning("Rule engine error: %s", e)
                rule_matches = []

            try:
                decision: Decision = _alert_svc.process(
                    behavior_alert, rule_matches, active_tracks
                )
            except Exception as e:
                log.warning("Alert service error: %s", e)
                decision = _alert_svc._no_decision()  # Safe fallback

            # ── 4. Annotate & Stream ──────────────────────────────────────────
            try:
                annotated = _tracker.draw(frame, active_tracks)
                _draw_overlay(annotated, len(active_tracks), decision)
                _, buffer = cv2.imencode('.jpg', annotated, [int(cv2.IMWRITE_JPEG_QUALITY), 72])
                with _frame_lock:
                    _latest_jpeg_bytes = buffer.tobytes()
            except Exception as e:
                log.warning("Annotation/stream error: %s", e)

            # ── 5. Periodic Gemini Summary ────────────────────────────────────
            uptime = time.time() - _start_time
            summary = None
            try:
                if uptime > 0 and int(uptime) % cfg.GEMINI_PERIODIC_INTERVAL == 0:
                    summary = _alert_svc.get_periodic_summary(len(active_tracks), uptime, get_events(10))
            except Exception:
                pass

            # ── 6. State Update ───────────────────────────────────────────────
            if frame_count % fps_window == 0:
                elapsed = time.time() - t_calc
                current_fps = fps_window / elapsed if elapsed > 0 else 0.0
                t_calc = time.time()
                with _state_lock:
                    _system_state.update({
                        "running":        True,
                        "people_count":   len(active_tracks),
                        "alert":          decision.alert,
                        "alert_type":     decision.alert_type,
                        "message":        decision.message,
                        "ai_insight":     decision.ai_insight,
                        "severity":       decision.severity,
                        "frame_count":    frame_count,
                        "uptime":         round(uptime, 1),
                        "fps":            round(current_fps, 1),
                        "periodic_summary": summary or _system_state.get("periodic_summary", ""),
                        "last_updated":   time.time(),
                    })

            # ── FPS Throttle ──────────────────────────────────────────────────
            elapsed = time.time() - loop_start
            sleep_time = frame_time - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)

    except Exception as exc:
        log.exception("Detection loop crashed: %s", exc)
    finally:
        source.release()
        with _state_lock:
            _system_state["running"] = False
        log.info("Detection loop finished.")


def _draw_overlay(frame: np.ndarray, count: int, decision: Decision) -> None:
    """Draw HUD overlay on the frame."""
    h, w = frame.shape[:2]

    # Top-left info bar
    cv2.rectangle(frame, (0, 0), (w, 40), (15, 20, 40), -1)
    cv2.putText(frame, f"People: {count}",
                (10, 27), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (80, 220, 120), 2)

    # Alert banner
    if decision.alert:
        severity_colors = {
            "low":      (0, 200, 200),
            "medium":   (0, 165, 255),
            "high":     (0, 80, 255),
            "critical": (0, 0, 220),
        }
        color = severity_colors.get(decision.severity, (0, 0, 200))
        cv2.rectangle(frame, (0, h - 50), (w, h), color, -1)
        txt = f"ALERT: {decision.alert_type.upper().replace('_',' ')}"
        cv2.putText(frame, txt, (10, h - 18),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.75, (255, 255, 255), 2)
    else:
        cv2.rectangle(frame, (0, h - 50), (w, h), (10, 100, 30), -1)
        cv2.putText(frame, "STATUS: NORMAL",
                    (10, h - 18), cv2.FONT_HERSHEY_SIMPLEX, 0.75, (80, 255, 120), 2)

    # Timestamp
    ts = time.strftime("%H:%M:%S")
    cv2.putText(frame, ts, (w - 90, 27),
                cv2.FONT_HERSHEY_SIMPLEX, 0.65, (180, 180, 180), 1)


@app.get("/videos")
def list_videos():
    import os
    video_dir = cfg.VIDEOS_DIR
    files = [f for f in os.listdir(video_dir) if f.endswith(".mp4")]
    return jsonify(files)


# ── API endpoints ─────────────────────────────────────────────────────────────


@app.get("/health")
def health():
    return jsonify({"status": "ok", "uptime": round(time.time() - _start_time, 1)})


@app.get("/status")
def get_status():
    with _state_lock:
        snapshot = dict(_system_state)
    return jsonify(snapshot)


@app.post("/start")
def start_system():
    global _detection_thread, _stop_event

    with _state_lock:
        if _system_state["running"]:
            return jsonify({"error": "System already running."}), 400

    data = request.get_json(silent=True) or {}
    mode   = data.get("mode", "webcam")       # "webcam" | "file"
    source = data.get("source", "")           # file name or webcam index

    try:
        if mode == "file" and source:
            video_src = VideoSource.from_file(source)
        elif mode == "webcam":
            idx = int(source) if source else cfg.DEFAULT_WEBCAM_INDEX
            video_src = VideoSource.from_webcam(idx)
        else:
            video_src = VideoSource.from_config()
    except (FileNotFoundError, RuntimeError) as exc:
        return jsonify({"error": str(exc)}), 400

    _stop_event.clear()
    _init_engines()
    _tracker.reset()
    _behavior.reset()

    with _state_lock:
        _system_state["source"] = str(video_src.source)

    _detection_thread = threading.Thread(
        target=_detection_loop,
        args=(video_src,),
        daemon=True,
        name="detection-loop",
    )
    _detection_thread.start()

    log.info("System started (mode=%s, source=%s).", mode, source or "default")
    return jsonify({"status": "started", "mode": mode, "source": str(video_src.source)})


@app.post("/stop")
def stop_system():
    _stop_event.set()
    if _detection_thread and _detection_thread.is_alive():
        _detection_thread.join(timeout=5)
    with _state_lock:
        _system_state["running"] = False
        _system_state["message"] = "System stopped by user."
    log.info("System stopped by API request.")
    return jsonify({"status": "stopped"})


@app.get("/frame")
def get_frame():
    """Fallback static image - no longer strictly needed in Stream pipeline."""
    return jsonify({"frame": None, "error": "Deprecated. Use /video_feed"}), 204


def _mjpeg_generator():
    """Streaming Thread - serves latest frame from shared memory."""
    while True:
        with _frame_lock:
            data = _latest_jpeg_bytes
        
        if data is None:
            time.sleep(0.1)
            continue
        
        yield (
            b'--frame\r\n'
            b'Content-Type: image/jpeg\r\n\r\n' + data + b'\r\n'
        )
        # Prevent CPU spike while waiting for next 10fps frame
        time.sleep(0.04)


@app.get("/video_feed")
def video_feed():
    return Response(
        _mjpeg_generator(),
        mimetype="multipart/x-mixed-replace; boundary=frame",
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma":        "no-cache",
            "Expires":       "0",
            "X-Accel-Buffering": "no",
        }
    )


@app.get("/events")
def get_event_log():
    n = int(request.args.get("n", 50))
    return jsonify(get_events(n))


@app.post("/events/clear")
def clear_event_log():
    from utils.logger import clear_events
    clear_events()
    return jsonify({"status": "cleared"})


@app.get("/rules")
def get_rules():
    rules = _rule_engine.get_rules() if _rule_engine else []
    return jsonify([r.to_dict() for r in rules])


@app.post("/rules")
def save_rules():
    data = request.get_json(silent=True)
    if not isinstance(data, list):
        return jsonify({"error": "Expected a JSON array of rules."}), 400
    engine = _rule_engine or RuleEngine()
    engine.save_rules(data)
    return jsonify({"status": "saved", "count": len(data)})


@app.post("/settings")
def update_settings():
    data = request.get_json(silent=True) or {}
    if "sound_enabled" in data and _alert_svc:
        _alert_svc.toggle_sound(bool(data["sound_enabled"]))
    if "ai_enabled" in data and _alert_svc:
        _alert_svc.toggle_ai(bool(data["ai_enabled"]))
    return jsonify({"status": "ok"})


# ── Entrypoint ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    log.info("Starting Flask API on %s:%d", cfg.FLASK_HOST, cfg.FLASK_PORT)
    app.run(
        host=cfg.FLASK_HOST,
        port=cfg.FLASK_PORT,
        debug=cfg.FLASK_DEBUG,
        threaded=True,
        use_reloader=False,
    )
