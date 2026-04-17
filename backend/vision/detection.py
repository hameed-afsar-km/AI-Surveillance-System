"""
detection.py – Dual-Model Inference Engine.

Architecture (ML-grade, senior design):
  Model A  →  Custom-trained YOLOv8n (best.pt) — 4 classes:
                 0: accident   1: fall   2: fire   3: garbage
  Model B  →  COCO YOLOv8n — People, Vehicles, Objects for tracking

Strategy:
  - Both models run on every inference frame.
  - Model A detections skip tracking (event-level, stateless per frame).
  - Model B detections feed the DeepSORT tracker for IDs and motion history.
  - CustomEvent results are exposed to BehaviorEngine so it can skip
    duplicate HSV-based fire checks (avoids false positives).
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from pathlib import Path

import cv2
import numpy as np

from config import cfg
from utils.logger import get_logger

log = get_logger("vision.detection")


# ── Data structures ───────────────────────────────────────────────────────────

@dataclass
class Detection:
    """Single tracked detection result (from COCO model)."""
    bbox: tuple[int, int, int, int]   # (x1, y1, x2, y2) absolute pixels
    confidence: float
    class_id: int = 0

    @property
    def center(self) -> tuple[int, int]:
        x1, y1, x2, y2 = self.bbox
        return ((x1 + x2) // 2, (y1 + y2) // 2)

    @property
    def width(self) -> int:
        return self.bbox[2] - self.bbox[0]

    @property
    def height(self) -> int:
        return self.bbox[3] - self.bbox[1]

    def to_tlwh(self) -> tuple[int, int, int, int]:
        x1, y1, x2, y2 = self.bbox
        return (x1, y1, x2 - x1, y2 - y1)


@dataclass
class CustomEvent:
    """A scene-level event detected by the custom model (stateless per frame)."""
    label: str                        # "accident" | "fall" | "fire" | "garbage"
    bbox: tuple[int, int, int, int]
    confidence: float

    # Mapping from custom model label → system alert_type
    LABEL_TO_ALERT: dict = field(default_factory=lambda: {
        "accident": "collision",
        "fall":     "medical_emergency",
        "fire":     "fire_hazard",
        "garbage":  "garbage_hotspot",
    })

    @property
    def alert_type(self) -> str:
        return self.LABEL_TO_ALERT.get(self.label, self.label)


@dataclass
class DualInferenceResult:
    """Combined result from one inference cycle."""
    coco_detections: list[Detection]
    custom_events: list[CustomEvent]


# ── Detector class ────────────────────────────────────────────────────────────

class ObjectDetector:
    """
    Dual-model object detector — thread-safe singleton.

    Runs both the COCO tracking model and the custom event model
    in parallel for every frame.
    """

    _instance: "ObjectDetector | None" = None
    _lock = threading.Lock()

    def __new__(cls) -> "ObjectDetector":
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return
        self._initialized = True
        self._coco_model = None
        self._custom_model = None
        self._custom_class_names: dict[int, str] = {}
        
        # ── Redesign: Persistent Workers ───────────────────
        self._pending_frame = None
        self._frame_lock = threading.Lock()
        
        self._latest_coco_dets = []
        self._latest_custom_events = []
        self._results_lock = threading.Lock()
        
        self._stop_workers = False
        self._worker_threads = []
        
        log.info("ObjectDetector initialized (Async Redesign).")

    # ── Initialization ────────────────────────────────────────────────────────

    def _load_model(self) -> None:
        if self._coco_model is not None:
            return

        import os
        os.environ["ULTRALYTICS_OFFLINE"] = "True"
        os.environ["YOLO_VERBOSE"] = "False"

        from ultralytics import YOLO
        import torch

        try:
            device = 'cuda' if torch.cuda.is_available() else 'cpu'
        except Exception:
            device = 'cpu'

        # ── MODEL B: COCO ──────────────────────────────────
        coco_path = cfg.YOLO_MODEL_PATH
        log.info("Loading COCO model: %s", coco_path)
        self._coco_model = YOLO(str(coco_path))
        self._coco_model.to(device)
        try: self._coco_model.fuse() 
        except: pass
        if device == 'cuda': self._coco_model.half()

        # ── MODEL A: Custom ─────────────────────────────────
        custom_path = cfg.CUSTOM_MODEL_PATH
        if custom_path.exists():
            log.info("Loading CUSTOM model: %s", custom_path)
            self._custom_model = YOLO(str(custom_path))
            self._custom_model.to(device)
            try: self._custom_model.fuse()
            except: pass
            if device == 'cuda': self._custom_model.half()
            self._custom_class_names = self._custom_model.names
        
        # Start workers
        self._start_workers()

    def _start_workers(self):
        self._stop_workers = False
        t1 = threading.Thread(target=self._coco_worker, daemon=True, name="coco-worker")
        t2 = threading.Thread(target=self._custom_worker, daemon=True, name="custom-worker")
        t1.start(); t2.start()
        self._worker_threads = [t1, t2]

    def _coco_worker(self):
        log.info("COCO Worker Started.")
        while not self._stop_workers:
            with self._frame_lock:
                frame = self._pending_frame
            
            if frame is None:
                time.sleep(0.005)
                continue
            
            try:
                # Predict
                results = self._coco_model.predict(
                    source=frame,
                    conf=cfg.YOLO_CONFIDENCE,
                    classes=cfg.TRACKED_CLASSES,
                    imgsz=cfg.YOLO_IMGSZ,
                    verbose=False
                )
                
                # Parse
                dets = []
                for r in results:
                    if r.boxes:
                        for b in r.boxes:
                            cls = int(b.cls[0].item())
                            conf = float(b.conf[0].item())
                            xyxy = b.xyxy[0].cpu().numpy().astype(int)
                            x1, y1, x2, y2 = self._clip_box(frame, xyxy)
                            dets.append(Detection(bbox=(x1,y1,x2,y2), confidence=conf, class_id=cls))
                
                with self._results_lock:
                    self._latest_coco_dets = dets
                    
            except Exception as e:
                log.error("COCO Worker Error: %s", e)
            
            time.sleep(0.001)

    def _custom_worker(self):
        log.info("Custom Worker Started.")
        while not self._stop_workers:
            if self._custom_model is None: break
            
            with self._frame_lock:
                frame = self._pending_frame
            
            if frame is None:
                time.sleep(0.01)
                continue
            
            try:
                results = self._custom_model.predict(
                    source=frame,
                    conf=cfg.CUSTOM_CONFIDENCE,
                    imgsz=640, # keep custom at its native training size
                    verbose=False
                )
                
                evts = []
                for r in results:
                    if r.boxes:
                        for b in r.boxes:
                            cls = int(b.cls[0].item())
                            conf = float(b.conf[0].item())
                            lbl = self._custom_class_names.get(cls, f"cls_{cls}")
                            xyxy = b.xyxy[0].cpu().numpy().astype(int)
                            x1, y1, x2, y2 = self._clip_box(frame, xyxy)
                            evts.append(CustomEvent(label=lbl, bbox=(x1,y1,x2,y2), confidence=conf))
                
                with self._results_lock:
                    self._latest_custom_events = evts
                    
            except Exception as e:
                log.error("Custom Worker Error: %s", e)
            
            time.sleep(0.001)

    # ── Public API ────────────────────────────────────────────────────────────

    def detect(self, frame: np.ndarray) -> list[Detection]:
        if self._coco_model is None:
            self._load_model()
        
        with self._frame_lock:
            self._pending_frame = frame
            
        with self._results_lock:
            return list(self._latest_coco_dets)

    def detect_dual(self, frame: np.ndarray) -> DualInferenceResult:
        if self._coco_model is None:
            self._load_model()
            
        # Update pending frame for workers to pick up
        with self._frame_lock:
            self._pending_frame = frame
            
        # Return latest available results (Async)
        with self._results_lock:
            return DualInferenceResult(
                coco_detections=list(self._latest_coco_dets),
                custom_events=list(self._latest_custom_events)
            )

    # ── Internal inference ────────────────────────────────────────────────────
    # (Removed _run_dual as it is replaced by workers)


    @staticmethod
    def _clip_box(frame: np.ndarray, xyxy: np.ndarray) -> tuple[int, int, int, int]:
        x1, y1, x2, y2 = int(xyxy[0]), int(xyxy[1]), int(xyxy[2]), int(xyxy[3])
        x1, y1 = max(0, x1), max(0, y1)
        x2 = min(frame.shape[1], x2)
        y2 = min(frame.shape[0], y2)
        return x1, y1, x2, y2

    # ── Drawing ───────────────────────────────────────────────────────────────

    def draw(self, frame: np.ndarray, detections: list[Detection]) -> np.ndarray:
        """Draw COCO detections on frame."""
        out = frame.copy()
        class_names = {
            0: "Person", 2: "Car", 3: "Moto", 5: "Bus", 7: "Truck",
            9: "Traffic Light", 10: "Fire Hydrant", 11: "Stop Sign",
            24: "Backpack", 39: "Bottle", 41: "Cup"
        }
        colors = {
            0: (80, 220, 120),   # Green — person
            2: (255, 180, 30),   # Blue-ish — car
            3: (255, 120, 50),   # Orange — moto
            5: (100, 180, 255),  # Light blue — bus
            7: (180, 100, 255),  # Purple — truck
        }
        for det in detections:
            x1, y1, x2, y2 = det.bbox
            color = colors.get(det.class_id, (200, 200, 200))
            cv2.rectangle(out, (x1, y1), (x2, y2), color, 2)
            cname = class_names.get(det.class_id, f"cls_{det.class_id}")
            label = f"{cname} {det.confidence:.2f}"
            cv2.putText(out, label, (x1, y1 - 6),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)
        return out

    def draw_custom_events(self, frame: np.ndarray, events: list[CustomEvent]) -> np.ndarray:
        """
        Clean event overlay: dashed alert box + small corner badge.
        Does NOT draw duplicate COCO tracking boxes.
        """
        out = frame
        event_styles = {
            "fire":     {"color": (0, 50, 230),   "badge": "FIRE"},
            "accident": {"color": (0, 120, 255),  "badge": "ACCDT"},
            "fall":     {"color": (180, 0, 200),  "badge": "FALL"},
            "garbage":  {"color": (30, 180, 30),  "badge": "GRBAGE"},
        }
        for ev in events:
            x1, y1, x2, y2 = ev.bbox
            style = event_styles.get(ev.label, {"color": (0, 200, 255), "badge": ev.label.upper()})
            color = style["color"]
            badge = style["badge"]

            # Dashed border (draw corner segments only — visually clean)
            seg = 12  # segment length
            pts = [(x1,y1,x1+seg,y1), (x2-seg,y1,x2,y1),
                   (x1,y2,x1+seg,y2), (x2-seg,y2,x2,y2),
                   (x1,y1,x1,y1+seg), (x2,y1,x2,y1+seg),
                   (x1,y2-seg,x1,y2), (x2,y2-seg,x2,y2)]
            for (ax, ay, bx, by) in pts:
                cv2.line(out, (ax, ay), (bx, by), color, 2)

            # Small corner badge (top-right)
            badge_text = f"{badge} {ev.confidence:.0%}"
            font = cv2.FONT_HERSHEY_SIMPLEX
            (tw, th), _ = cv2.getTextSize(badge_text, font, 0.38, 1)
            bx1, by1 = x2 - tw - 6, y1
            bx2, by2 = x2, y1 + th + 6
            cv2.rectangle(out, (bx1, by1), (bx2, by2), color, -1)
            cv2.putText(out, badge_text, (bx1 + 3, by2 - 3),
                        font, 0.38, (255, 255, 255), 1, cv2.LINE_AA)

        return out
