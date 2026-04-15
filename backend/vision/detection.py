"""
detection.py – YOLOv8 person detection engine.

Responsibilities:
  • Load YOLOv8 model (lazy, singleton)
  • Run inference on frames
  • Return only "person" detections with bboxes + confidence
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

from config import cfg
from utils.logger import get_logger

log = get_logger("vision.detection")

# ── Data structures ───────────────────────────────────────────────────────────


@dataclass
class Detection:
    """Single person detection result."""
    bbox: tuple[int, int, int, int]   # (x1, y1, x2, y2) absolute pixels
    confidence: float
    class_id: int = 0  # always 0 = person

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
        """Convert to (top, left, width, height) for DeepSORT."""
        x1, y1, x2, y2 = self.bbox
        return (x1, y1, x2 - x1, y2 - y1)


# ── Detector class ────────────────────────────────────────────────────────────


class ObjectDetector:
    """Singleton YOLOv8 detector — thread-safe."""

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
        self._load_model()

    # ── init ──────────────────────────────────────────────────────────────────

    def _load_model(self) -> None:
        from ultralytics import YOLO  # deferred import for fast startup

        model_path = cfg.YOLO_MODEL_PATH
        if not model_path.exists():
            log.info("YOLOv8 model not found locally – downloading yolov8n.pt …")
            model_path.parent.mkdir(parents=True, exist_ok=True)

        log.info("Loading YOLOv8 model from: %s", model_path)
        self._model = YOLO(str(model_path))
        
        import torch
        device = 'cuda' if torch.cuda.is_available() else 'cpu'
        self._model.to(device)
        log.info(f"YOLOv8 initialized on device: {device.upper()}")

    # ── public ────────────────────────────────────────────────────────────────

    def detect(self, frame: np.ndarray) -> list[Detection]:
        """
        Run inference on a BGR frame.

        Returns list of Detection objects for class 'person' only.
        """
        if frame is None or frame.size == 0:
            return []

        try:
            results = self._model.predict(
                source=frame,
                conf=cfg.YOLO_CONFIDENCE,
                classes=cfg.TRACKED_CLASSES,
                imgsz=cfg.YOLO_IMGSZ,  # Configurable – 416 for CPU, 640 for GPU
                max_det=300,  # Prevent skipping people in large crowds
                verbose=False,
                stream=False,
            )
        except Exception as exc:
            log.error("YOLO inference error: %s", exc)
            return []

        detections: list[Detection] = []

        for result in results:
            boxes = result.boxes
            if boxes is None:
                continue
            for box in boxes:
                cls_id = int(box.cls[0].item())
                if cls_id not in cfg.TRACKED_CLASSES:
                    continue
                conf = float(box.conf[0].item())
                xyxy = box.xyxy[0].cpu().numpy().astype(int)
                x1, y1, x2, y2 = int(xyxy[0]), int(xyxy[1]), int(xyxy[2]), int(xyxy[3])
                # sanity-clip
                x1, y1 = max(0, x1), max(0, y1)
                x2 = min(frame.shape[1], x2)
                y2 = min(frame.shape[0], y2)
                if x2 <= x1 or y2 <= y1:
                    continue
                detections.append(Detection(bbox=(x1, y1, x2, y2), confidence=conf, class_id=cls_id))

        return detections

    def draw(self, frame: np.ndarray, detections: list[Detection]) -> np.ndarray:
        """Draw raw detections (no tracking ID) on a copy of the frame."""
        out = frame.copy()
        
        # Simple lookup table
        class_names = {0: "Person", 2: "Car", 3: "Moto", 5: "Bus", 7: "Truck", 9: "Traffic Light", 10: "Fire Hydrant", 11: "Stop Sign", 24: "Backpack", 39: "Bottle", 41: "Cup"}
        
        for det in detections:
            x1, y1, x2, y2 = det.bbox
            cv2.rectangle(out, (x1, y1), (x2, y2), (0, 200, 0), 2)
            cname = class_names.get(det.class_id, f"cls_{det.class_id}")
            label = f"{cname} {det.confidence:.2f}"
            cv2.putText(out, label, (x1, y1 - 6),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 200, 0), 1)
        return out
