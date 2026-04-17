"""
app.py – Flask REST API backend for the AI Surveillance System.

Architecture (Two-Thread Pipeline for smooth video):
  Frame Grabber Thread  → always holds latest raw frame at camera FPS
  Inference Thread      → runs YOLO+DeepSORT asynchronously (CPU limited)
  MJPEG Stream          → annotates latest raw frame with last-known boxes (full speed)
"""

from __future__ import annotations

import sys
import os
import threading
import time
from pathlib import Path
from typing import Optional

import cv2
import numpy as np
from flask import Flask, Response, jsonify, request
from flask_cors import CORS

# ── path bootstrap ────────────────────────────────────────────────────────────
_BACKEND = Path(__file__).resolve().parent
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from config import cfg
from utils.logger import get_logger, get_events

log = get_logger("backend.app")

# ── Flask app ─────────────────────────────────────────────────────────────────
app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})
app.config["SECRET_KEY"] = cfg.SECRET_KEY

# ── Global shared state ───────────────────────────────────────────────────────
_state_lock = threading.Lock()
_system_state: dict = {
    "running": False,
    "starting": False,
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
    "inference_fps": 0.0,
    "last_decision": {},
    "periodic_summary": "",
    "last_updated": time.time(),
    "internet_connected": False,
    "loading_progress": 0,
    "live_counts": {"people": 0, "cars": 0, "other": 0},
}

# ── Dynamic Connectivity Checker ──────────────────────────────────────────────
def _internet_checker_loop():
    import socket
    while True:
        try:
            # Ping Google Public DNS
            socket.create_connection(("8.8.8.8", 53), timeout=2)
            is_connected = True
        except OSError:
            is_connected = False
            
        with _state_lock:
            _system_state["internet_connected"] = is_connected
            
        time.sleep(15)

# Start internet checker immediately
threading.Thread(target=_internet_checker_loop, daemon=True, name="internet-checker").start()

# Latest RAW frame from grabber thread (always up to date at camera FPS)
_raw_frame_lock = threading.Lock()
_latest_raw_frame: Optional[np.ndarray] = None

# Last known tracks/decision from inference thread (updated at inference FPS)
_tracks_lock = threading.Lock()
_last_tracks: list = []
_last_decision = None
_last_custom_events: list = []

_stop_event = threading.Event()
_ai_ready = False
_ai_loading_error = None

_grabber_thread: Optional[threading.Thread] = None
_inference_thread: Optional[threading.Thread] = None
_start_time: float = 0.0

# ── Engine singletons (lazy-loaded on /start) ─────────────────────────────────
_detector = None
_tracker = None
_behavior = None
_rule_engine = None
_alert_svc = None


def _init_engines() -> None:
    global _detector, _tracker, _behavior, _rule_engine, _alert_svc
    log.info("Initialising detection engines (lazy load)…")
    from vision.detection import ObjectDetector
    from vision.tracking import ObjectTracker
    from logic.behavior import BehaviorEngine
    from logic.rule_engine import RuleEngine
    from services.alert_service import AlertService
    _detector    = ObjectDetector()
    _tracker     = ObjectTracker()
    _behavior    = BehaviorEngine()
    _rule_engine = RuleEngine()
    _alert_svc   = AlertService()
    log.info("All engines ready.")

def _boot_ai_background():
    """Background task to load AI models immediately on app start."""
    global _ai_ready, _ai_loading_error
    log.info("EAGER LOADING: Initializing AI engines in background...")
    try:
        with _state_lock: _system_state["loading_progress"] = 5
        
        # We'll use a local import trick to track progress if possible, 
        # or just step through the init.
        log.info("EAGER LOADING: Initializing Detectors...")
        from vision.detection import ObjectDetector
        with _state_lock: _system_state["loading_progress"] = 25
        
        _init_engines()
        with _state_lock: _system_state["loading_progress"] = 85
        
        # Trigger an early warmup
        log.info("EAGER LOADING: Warming up neural pipelines...")
        _detector.detect(np.zeros((cfg.YOLO_IMGSZ, cfg.YOLO_IMGSZ, 3), dtype=np.uint8))
        
        with _state_lock: 
            _system_state["loading_progress"] = 100
            _ai_ready = True
        
        log.info("EAGER LOADING: System fully calibrated and ready.")
        
    except Exception as e:
        _ai_loading_error = str(e)
        log.error("EAGER LOADING: Critical failure during boot: %s", e)
        with _state_lock: _system_state["loading_progress"] = 0

# Start physical boot immediately
_boot_thread = threading.Thread(target=_boot_ai_background, daemon=True, name="ai-boot-thread")
_boot_thread.start()


# ── Thread 1: Frame Grabber ───────────────────────────────────────────────────

def _frame_grabber_loop(source) -> None:
    """
    Reads frames from the video source as fast as possible.
    Stores only the LATEST frame in _latest_raw_frame.
    Does NO inference — purely a fast reader.
    """
    global _latest_raw_frame
    log.info("Frame Grabber Thread started.")

    while not _stop_event.is_set():
        try:
            ok, frame = source.read()
        except Exception as e:
            log.warning("Grabber read error: %s", e)
            time.sleep(0.01)
            continue

        if not ok or frame is None:
            time.sleep(0.005)
            continue

        # Resize once here for efficiency
        h, w = frame.shape[:2]
        if w != 640:
            scale = 640.0 / w
            frame = cv2.resize(frame, (640, max(1, int(h * scale))), interpolation=cv2.INTER_LINEAR)

        with _raw_frame_lock:
            _latest_raw_frame = frame

    source.release()
    log.info("Frame Grabber Thread finished.")


# ── Thread 2: Inference ───────────────────────────────────────────────────────

def _inference_loop() -> None:
    """
    Runs YOLO + DeepSORT + Behavior asynchronously.
    Reads the latest raw frame, infers, stores annotated bytes.
    The inference rate is limited by CPU/GPU speed.
    The stream is NOT blocked by this — it uses last-known results.
    """
    global _last_tracks, _last_decision, _start_time

    # Warm up YOLO (this triggers lazy model load — may take 10-30s on first run)
    log.info("Warming up YOLO… (first run may take up to 30s)")
    with _state_lock: _system_state["loading_progress"] = 30
    
    try:
        # We can't easily hook into ultralytics for progress, so we simulate progress during the call
        # in a slightly hacky way for UI benefit
        def _update_prog():
            # Fast progress simulation
            for i in range(1, 10):
                time.sleep(0.1)
                if _system_state["running"]: break
                with _state_lock:
                    _system_state["loading_progress"] = min(95, 30 + (i * 7))
        
        pro_thread = threading.Thread(target=_update_prog, daemon=True)
        pro_thread.start()

        _detector.detect(np.zeros((320, 320, 3), dtype=np.uint8))
        log.info("YOLO warmup complete.")
        with _state_lock: _system_state["loading_progress"] = 100
    except Exception as e:
        log.error("YOLO warmup failed: %s", e)
        with _state_lock: _system_state["loading_progress"] = 0

    _start_time = time.time()
    frame_count = 0
    fps_counter = 0
    fps_timer = time.time()
    fps_window = 10  # measure inference fps every 10 inferences

    # Mark system as truly live now that warmup is done
    with _state_lock:
        _system_state["running"] = True
        _system_state["starting"] = False
        _system_state["message"] = "System live."

    log.info("Inference Thread started.")

    while not _stop_event.is_set():
        # Grab latest raw frame (non-blocking)
        with _raw_frame_lock:
            frame = _latest_raw_frame
        if frame is None:
            time.sleep(0.01)
            continue

        frame = frame.copy()
        frame_count += 1

        # ── 1. Dual-Model Inference (COCO + Custom) ───────────────────────────
        custom_events = []
        try:
            dual_result = _detector.detect_dual(frame)
            detections = dual_result.coco_detections
            custom_events = dual_result.custom_events
        except Exception as e:
            log.warning("Detection error: %s", e)
            detections = []
            custom_events = []

        # ── 2. DeepSORT ──────────────────────────────────────────────────────
        try:
            active_tracks = _tracker.update(frame, detections)
            
            # Update Live Counts
            p_cnt = len([t for t in active_tracks if t.class_id == 0])
            v_cnt = len([t for t in active_tracks if t.class_id in [2, 3, 5, 7]])
            o_cnt = len(active_tracks) - p_cnt - v_cnt
            with _state_lock:
                _system_state["live_counts"] = {
                    "people": p_cnt,
                    "cars": v_cnt,
                    "other": o_cnt
                }
        except Exception as e:
            log.warning("Tracker error: %s", e)
            active_tracks = []

        exited_tracks = list(_tracker.get_exited_states().values()) if _tracker else []

        # ── 3. Behavior ───────────────────────────────────────────────────────
        try:
            behavior_alert = _behavior.analyse(active_tracks, frame, custom_events, exited_tracks)
        except Exception as e:
            log.warning("Behavior error: %s", e)
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
            from services.alert_service import _NO_DECISION
            decision = _alert_svc.process(behavior_alert, rule_matches, active_tracks)
        except Exception as e:
            log.warning("Alert service error: %s", e)
            from services.alert_service import Decision
            decision = Decision(alert=False, alert_type="none", message="System nominal.", severity="none")

        # ── 4. Store last-known tracks + decision + custom events ──────────────
        with _tracks_lock:
            _last_tracks = active_tracks
            _last_decision = decision
            _last_custom_events = custom_events

        # ── 6. Immediate Alert Update (Critical for Latency) ────────────
        with _state_lock:
            _system_state.update({
                "alert":          decision.alert,
                "alert_type":     decision.alert_type,
                "message":        decision.message,
                "severity":       decision.severity,
                "last_updated":   time.time(),
            })

        # ── 7. Throttled Metrics Update (Efficiency) ──────────────────────────
        fps_counter += 1
        uptime = time.time() - _start_time

        if fps_counter >= fps_window:
            elapsed = time.time() - fps_timer
            inference_fps = fps_window / elapsed if elapsed > 0 else 0.0
            fps_timer = time.time()
            fps_counter = 0

            with _state_lock:
                _system_state.update({
                    "running":        True,
                    "people_count":   len(active_tracks),
                    "ai_insight":     decision.ai_insight,
                    "active_ids":     [t.track_id for t in active_tracks],
                    "frame_count":    frame_count,
                    "uptime":         round(uptime, 1),
                    "inference_fps":  round(inference_fps, 1),
                })

        # ── 7. Periodic Gemini Summary ────────────────────────────────────────
        try:
            if uptime > 0 and int(uptime) % cfg.GEMINI_PERIODIC_INTERVAL == 0:
                summary = _alert_svc.get_periodic_summary(len(active_tracks), uptime, get_events(10))
                if summary:
                    with _state_lock:
                        _system_state["periodic_summary"] = summary
        except Exception:
            pass

    log.info("Inference Thread finished.")


# ── MJPEG stream generator ────────────────────────────────────────────────────

def _mjpeg_generator():
    """
    Streams at full camera FPS.
    Fix: Ensures we always yield something so Flask worker threads don't livelock.
    """
    target_interval = 1.0 / 30.0
    encode_params = [int(cv2.IMWRITE_JPEG_QUALITY), 75]
    
    # Pre-create a "No Signal" black frame to save CPU
    no_signal = np.zeros((480, 640, 3), dtype=np.uint8)
    cv2.putText(no_signal, "INITIALIZING FEED...", (160, 240),
                cv2.FONT_HERSHEY_SIMPLEX, 1.0, (100, 100, 100), 2)
    _, no_signal_buf = cv2.imencode('.jpg', no_signal, encode_params)
    no_signal_bytes = (
        b'--frame\r\n'
        b'Content-Type: image/jpeg\r\n\r\n' + no_signal_buf.tobytes() + b'\r\n'
    )

    while True:
        t0 = time.time()

        with _raw_frame_lock:
            raw = _latest_raw_frame

        if raw is not None:
            try:
                frame = raw.copy()

                with _tracks_lock:
                    tracks    = list(_last_tracks)
                    decision  = _last_decision
                    cust_evts = list(_last_custom_events)

                if _tracker is not None and tracks:
                    frame = _tracker.draw(frame, tracks)

                # Draw custom model event boxes (fire, accident, fall, garbage)
                if _detector is not None and cust_evts:
                    frame = _detector.draw_custom_events(frame, cust_evts)

                _draw_overlay(frame, len(tracks), decision)

                _, buf = cv2.imencode('.jpg', frame, encode_params)
                yield (
                    b'--frame\r\n'
                    b'Content-Type: image/jpeg\r\n\r\n' + buf.tobytes() + b'\r\n'
                )
            except Exception as e:
                log.error("Stream encode error: %s", e)
                yield no_signal_bytes
        else:
            # Important: Yield a placeholder so the connection doesn't hang
            # and the worker thread can be reclaimed if the client leaves.
            yield no_signal_bytes

        # Throttle to 30fps
        elapsed = time.time() - t0
        sleep_t = target_interval - elapsed
        if sleep_t > 0:
            time.sleep(sleep_t)


# ── Overlay HUD ───────────────────────────────────────────────────────────────

def _draw_overlay(frame: np.ndarray, count: int, decision) -> None:
    h, w = frame.shape[:2]
    cv2.rectangle(frame, (0, 0), (w, 40), (15, 20, 40), -1)
    cv2.putText(frame, f"People: {count}", (10, 27),
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (80, 220, 120), 2)
    ts = time.strftime("%H:%M:%S")
    cv2.putText(frame, ts, (w - 90, 27),
                cv2.FONT_HERSHEY_SIMPLEX, 0.65, (180, 180, 180), 1)

    if decision and decision.alert:
        severity_colors = {"low": (0, 200, 200), "medium": (0, 165, 255),
                           "high": (0, 80, 255), "critical": (0, 0, 220)}
        color = severity_colors.get(decision.severity, (0, 0, 200))
        cv2.rectangle(frame, (0, h - 50), (w, h), color, -1)
        txt = f"ALERT: {decision.alert_type.upper().replace('_', ' ')}"
        cv2.putText(frame, txt, (10, h - 18),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.75, (255, 255, 255), 2)
    else:
        cv2.rectangle(frame, (0, h - 50), (w, h), (10, 100, 30), -1)
        cv2.putText(frame, "STATUS: NORMAL", (10, h - 18),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.75, (80, 255, 120), 2)


# ── API Endpoints ─────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return jsonify({"status": "ok", "uptime": round(time.time() - _start_time, 1)})


@app.get("/status")
def get_status():
    with _state_lock:
        return jsonify(dict(_system_state))


@app.post("/start")
def start_system():
    global _grabber_thread, _inference_thread, _stop_event

    with _state_lock:
        if _system_state["running"] or _system_state.get("starting"):
            return jsonify({"error": "Already running or starting."}), 400

    data = request.get_json(silent=True) or {}
    mode   = data.get("mode", "webcam")
    source = data.get("source", "")

    # Validate source exists BEFORE returning (fast check, no model loading)
    from vision.video_input import VideoSource
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

    # Mark as starting so UI can show loading state immediately
    with _state_lock:
        _system_state["starting"] = True
        _system_state["message"] = "Initialising AI engines…"
        _system_state["source"] = str(video_src.source)

    def _startup():
        global _grabber_thread, _inference_thread, _ai_ready
        try:
            with _state_lock: _system_state["loading_progress"] = 10
            _stop_event.clear()
            
            # If AI isn't ready yet, wait/init (for requests coming from UI before boot)
            if not _ai_ready:
                max_wait = 600 
                start_wait = time.time()
                while not _ai_ready and (time.time() - start_wait < max_wait):
                    if _ai_loading_error: raise RuntimeError(_ai_loading_error)
                    time.sleep(0.5)
                    elapsed = time.time() - start_wait
                    if elapsed < 30: prog = 10 + int(elapsed * 2.5)
                    else: prog = min(99, 85 + int((elapsed - 30) * 0.1))
                    with _state_lock: _system_state["loading_progress"] = prog

            if not _ai_ready:
                raise RuntimeError("AI engines failed to initialize.")
            
            with _state_lock: 
                _system_state["loading_progress"] = 100
                _system_state["starting"] = True
                _system_state["message"] = "Initializing Feed..."
            
            _tracker.reset()
            _behavior.reset()
            with _state_lock: _system_state["loading_progress"] = 95

            _grabber_thread = threading.Thread(
                target=_frame_grabber_loop, args=(video_src,), daemon=True, name="frame-grabber"
            )
            _grabber_thread.start()

            _inference_thread = threading.Thread(
                target=_inference_loop, daemon=True, name="inference-loop"
            )
            _inference_thread.start()
            # Loop will handle 100
            log.info("System startup initiated (mode=%s, source=%s).", mode, source or "default")
        except Exception as exc:
            log.error("Startup failed: %s", exc)
            with _state_lock:
                _system_state["starting"] = False
                _system_state["loading_progress"] = 0
                _system_state["message"] = f"CRITICAL: {exc}"

    threading.Thread(target=_startup, daemon=True, name="startup-thread").start()

    return jsonify({"status": "starting", "mode": mode, "source": str(video_src.source)})


@app.post("/stop")
def stop_system():
    global _latest_raw_frame, _last_tracks, _last_decision

    _stop_event.set()

    if _grabber_thread and _grabber_thread.is_alive():
        _grabber_thread.join(timeout=3)
    if _inference_thread and _inference_thread.is_alive():
        _inference_thread.join(timeout=3)

    # Reset shared buffers
    with _raw_frame_lock:
        _latest_raw_frame = None
    with _tracks_lock:
        _last_tracks = []
        _last_decision = None

    with _state_lock:
        _system_state["running"] = False
        _system_state["starting"] = False
        _system_state["message"] = "System stopped by user."

    log.info("System stopped.")
    return jsonify({"status": "stopped"})


@app.get("/video_feed")
def video_feed():
    return Response(
        _mjpeg_generator(),
        mimetype="multipart/x-mixed-replace; boundary=frame",
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0",
            "X-Accel-Buffering": "no",
        }
    )


@app.get("/frame")
def get_frame():
    return jsonify({"frame": None, "error": "Deprecated. Use /video_feed"}), 204


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
    from logic.rule_engine import RuleEngine
    engine = _rule_engine or RuleEngine()
    engine.save_rules(data)
    return jsonify({"status": "saved", "count": len(data)})


@app.get("/settings")
def get_settings():
    # Return current email settings
    return jsonify({
        "sound_enabled": True,  # These are currently runtime memory bounds, default to True on load
        "ai_enabled": True,     
        "email_sender": cfg.EMAIL_SENDER,
        "email_password": cfg.EMAIL_PASSWORD, # Don't send password to UI in prod ideally, but doing it for UI simplicity
        "email_accident": os.getenv("EMAIL_DEPT_ACCIDENT", os.getenv("EMAIL_DEPT_POLICE", "")),
        "email_fire": os.getenv("EMAIL_DEPT_FIRE", ""),
        "email_garbage": os.getenv("EMAIL_DEPT_MUNICIPAL", ""),
        "email_health": os.getenv("EMAIL_DEPT_MEDICAL", ""),
        "email_traffic": os.getenv("EMAIL_DEPT_TRAFFIC", ""),
    })


@app.post("/settings")
def update_settings():
    data = request.get_json(silent=True) or {}
    
    # Live runtime toggles
    if "sound_enabled" in data and _alert_svc:
        _alert_svc.toggle_sound(bool(data["sound_enabled"]))
    if "ai_enabled" in data and _alert_svc:
        _alert_svc.toggle_ai(bool(data["ai_enabled"]))
        
    # Persistent changes to .env file
    env_path = ROOT_DIR / ".env"
    from dotenv import set_key
    
    env_keys = {
        "email_sender": "EMAIL_SENDER",
        "email_password": "EMAIL_PASSWORD",
        "email_fire": "EMAIL_DEPT_FIRE",
        "email_accident": "EMAIL_DEPT_ACCIDENT",
        "email_garbage": "EMAIL_DEPT_MUNICIPAL",
        "email_health": "EMAIL_DEPT_MEDICAL",
        "email_traffic": "EMAIL_DEPT_TRAFFIC",
    }
    
    updates = 0
    for k, env_k in env_keys.items():
        if k in data:
            set_key(str(env_path), env_k, data[k])
            os.environ[env_k] = data[k] # update current process env
            
            # Since some variables like EMAIL_SENDER are loaded into `cfg` at startup,
            # we need to override the `cfg` values directly too:
            if hasattr(cfg, env_k):
                setattr(cfg, env_k, data[k])
                
            updates += 1
            
    # Notify EmailService to reload configuration
    if _alert_svc and updates > 0:
        _alert_svc.reload_email_config()
        
    return jsonify({"status": "ok", "updates": updates})


@app.post("/settings/test_email")
def test_email():
    """Endpoint to send a test email using provided (unsaved) credentials."""
    data = request.get_json(silent=True) or {}
    alert_type = data.get("alert_type", "test_connection")
    
    # Resolve recipient based on specific category if provided
    # Maps internal keys to the data keys sent from UI
    cat_map = {
        "fire_hazard": "email_fire",
        "collision": "email_accident",
        "medical_emergency": "email_health",
        "littering": "email_garbage",
        "overcrowding": "email_traffic"
    }
    
    target_data_key = cat_map.get(alert_type)
    recipient = data.get(target_data_key) if target_data_key else None
    
    # Fallback to test_recipient or sender
    if not recipient:
        recipient = data.get("test_recipient") or data.get("email_sender")
    
    if not recipient:
        return jsonify({"error": "No recipient email found for this category."}), 400
        
    sender = data.get("email_sender")
    pwd = data.get("email_password")
    
    if not sender or not pwd:
        return jsonify({"error": "Sender email and password are required for test."}), 400

    old_sender = cfg.EMAIL_SENDER
    old_pwd = cfg.EMAIL_PASSWORD
    
    try:
        cfg.EMAIL_SENDER = sender
        cfg.EMAIL_PASSWORD = pwd
        
        from services.email_service import EmailService
        test_svc = EmailService()
        
        # Manually force the recipient for this specific test
        success = test_svc._send_with_retry(
            alert_type=alert_type,
            people_count=1,
            message=f"SIMULATED TEST ALERT for {alert_type.upper()}.",
            ai_insight="This is a focused department routing test. If you are reading this, the receiver end is correctly configured.",
            recipients=[recipient],
            dept_label=test_svc.DEPT_LABELS.get(alert_type, "Custom Department"),
            max_retries=1
        )
        
        if success:
            return jsonify({"status": "ok", "message": f"Test sent to {recipient}"})
        else:
            return jsonify({"error": "SMTP failed. Check credentials/connection."}), 500
            
    finally:
        cfg.EMAIL_SENDER = old_sender
        cfg.EMAIL_PASSWORD = old_pwd

@app.get("/videos")
def list_videos():
    video_dir = cfg.VIDEOS_DIR
    files = [f for f in os.listdir(video_dir) if f.endswith(".mp4")]
    return jsonify(files)


# ── Entrypoint ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    log.info("Starting Flask API on %s:%d", cfg.FLASK_HOST, cfg.FLASK_PORT)
    app.run(
        host=cfg.FLASK_HOST,
        port=cfg.FLASK_PORT,
        debug=False,
        threaded=True,
        use_reloader=False,
    )
