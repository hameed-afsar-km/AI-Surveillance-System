"""
tracking.py – DeepSORT multi-person tracking engine.

Responsibilities:
  • Wrap DeepSORT tracker
  • Assign & maintain unique IDs across frames
  • Record entry/exit timestamps, position history, zone presence
  • Expose per-track state for downstream analysis
"""

from __future__ import annotations

import time
import threading
from dataclasses import dataclass, field
from collections import deque
from typing import Optional

import cv2
import numpy as np
from deep_sort_realtime.deepsort_tracker import DeepSort

from config import cfg
from vision.detection import Detection
from utils.logger import get_logger

log = get_logger("vision.tracking")


# ── Per-track state ───────────────────────────────────────────────────────────


@dataclass
class TrackState:
    track_id: int
    class_id: int = 0
    entry_time: float = field(default_factory=time.time)
    last_seen: float = field(default_factory=time.time)
    bbox: tuple[int, int, int, int] = (0, 0, 0, 0)
    center: tuple[int, int] = (0, 0)
    confidence: float = 0.0
    position_history: deque = field(default_factory=lambda: deque(maxlen=60))
    is_active: bool = True

    @property
    def duration(self) -> float:
        """Seconds this track has been active."""
        return self.last_seen - self.entry_time

    @property
    def age_seconds(self) -> float:
        return time.time() - self.entry_time

    def update(
        self,
        bbox: tuple[int, int, int, int],
        confidence: float,
        class_id: int = 0,
    ) -> None:
        self.bbox = bbox
        x1, y1, x2, y2 = bbox
        self.center = ((x1 + x2) // 2, (y1 + y2) // 2)
        self.confidence = confidence
        self.class_id = class_id
        self.last_seen = time.time()
        self.position_history.append(self.center)

    def to_dict(self) -> dict:
        return {
            "track_id": self.track_id,
            "entry_time": self.entry_time,
            "last_seen": self.last_seen,
            "duration": round(self.duration, 2),
            "center": self.center,
            "bbox": self.bbox,
            "confidence": round(self.confidence, 3),
            "is_active": self.is_active,
        }


# ── Tracker ───────────────────────────────────────────────────────────────────


class ObjectTracker:
    """
    DeepSORT-based person tracker.

    Call update(frame, detections) each frame; returns list of TrackState.
    """

    def __init__(self) -> None:
        self._tracker = DeepSort(
            max_age=20,
            n_init=2,              # Confirm track after 2 frames (was 3) — faster latch-on
            max_iou_distance=0.7,
            max_cosine_distance=0.3,
            nn_budget=100,
        )
        self._states: dict[int, TrackState] = {}   # track_id → TrackState
        self._exited: dict[int, TrackState] = {}   # recently exited
        self._lock = threading.Lock()
        log.info("ObjectTracker initialised (DeepSORT).")

    # ── public ────────────────────────────────────────────────────────────────

    def update(
        self,
        frame: np.ndarray,
        detections: list[Detection],
    ) -> list[TrackState]:
        """
        Feed new detections into DeepSORT tracker.

        Returns list of currently active TrackState objects.
        """
        h, w = frame.shape[:2]
        raw_dets = self._build_deepsort_input(detections)

        try:
            tracks = self._tracker.update_tracks(raw_dets, frame=frame)
        except Exception as exc:
            log.error("DeepSORT update error (auto-resetting tracker): %s", exc)
            # Self-heal: reinitialize tracker so one bad frame doesn't kill the session
            self._tracker = DeepSort(
                max_age=20, n_init=2, max_iou_distance=0.7,
                max_cosine_distance=0.3, nn_budget=100,
            )
            return []

        active_ids: set[int] = set()

        with self._lock:
            for track in tracks:
                if not track.is_confirmed():
                    continue
                tid = int(track.track_id)
                active_ids.add(tid)

                ltrb = track.to_ltrb()
                x1 = max(0, int(ltrb[0]))
                y1 = max(0, int(ltrb[1]))
                x2 = min(w, int(ltrb[2]))
                y2 = min(h, int(ltrb[3]))
                bbox = (x1, y1, x2, y2)

                conf = track.det_conf if track.det_conf is not None else 0.0

                # DeepSORT's track classification
                try:
                    cid = int(track.get_det_class())
                except (AttributeError, TypeError, ValueError):
                    cid = 0

                if tid not in self._states:
                    self._states[tid] = TrackState(track_id=tid, class_id=cid)
                    log.debug("New track: ID=%d, class=%d", tid, cid)

                self._states[tid].update(bbox, float(conf), cid)
                self._states[tid].is_active = True

            # Mark missing tracks as inactive
            for tid, state in self._states.items():
                if tid not in active_ids:
                    if state.is_active:
                        state.is_active = False
                        self._exited[tid] = state
                        log.debug("Track exited: ID=%d duration=%.1fs", tid, state.duration)

            # Return only active states
            active_states = [s for s in self._states.values() if s.is_active]

        return active_states

    def get_all_states(self) -> dict[int, TrackState]:
        with self._lock:
            return dict(self._states)

    def get_active_states(self) -> list[TrackState]:
        with self._lock:
            return [s for s in self._states.values() if s.is_active]

    def get_exited_states(self) -> dict[int, TrackState]:
        with self._lock:
            return dict(self._exited)

    def reset(self) -> None:
        with self._lock:
            self._states.clear()
            self._exited.clear()
            self._tracker = DeepSort(
                max_age=20, n_init=2, max_iou_distance=0.7,
                max_cosine_distance=0.3, nn_budget=100,
            )
        log.info("ObjectTracker reset.")

    def draw(self, frame: np.ndarray, states: list[TrackState]) -> np.ndarray:
        """
        Clean minimal overlay. Shows a small pill label (icon + ID) per tracked entity.
        No duration clutter. Only major classes get a label.
        """
        # Icon mapping — compact
        # Icon mapping — full text for clarity
        class_icons = {
            0: "[Person]",
            2: "[Car]",
            3: "[Moto]",
            5: "[Bus]",
            7: "[Truck]",
            24: "[Bag]", # Backpack
            26: "[Bag]", # Handbag
            28: "[Suitcase]",
            63: "[Laptop]",
            67: "[Phone]",
        }
        # Color mapping per class (consistent, not per-ID)
        class_colors = {
            0: (80, 220, 120),    # Green — Person
            2: (60, 160, 255),    # Blue — Car
            3: (255, 160, 60),    # Orange — Moto
            5: (120, 80, 255),    # Purple — Bus
            7: (200, 60, 255),    # Violet — Truck
            24: (180, 180, 180),  # Gray — Bags/Items
            26: (180, 180, 180),
            28: (180, 180, 180),
            63: (180, 180, 180),
            67: (180, 180, 180),
        }
        out = frame

        for st in states:
            x1, y1, x2, y2 = st.bbox
            cid = st.class_id

            # Skip drawing tiny object classes entirely (declutter)
            if cid not in class_icons:
                continue

            color = class_colors.get(cid, (180, 180, 180))

            # Thin, clean bounding box
            cv2.rectangle(out, (x1, y1), (x2, y2), color, 2)

            # Minimal pill label: just "P#12" or "C#5"
            icon = class_icons.get(cid, "?")
            label = f"{icon}#{st.track_id}"
            font = cv2.FONT_HERSHEY_SIMPLEX
            font_scale = 0.45
            thickness = 1
            (tw, th), _ = cv2.getTextSize(label, font, font_scale, thickness)
            pad = 3
            # Draw pill background
            cv2.rectangle(out, (x1, y1 - th - pad * 2), (x1 + tw + pad * 2, y1), color, -1)
            cv2.putText(out, label, (x1 + pad, y1 - pad),
                        font, font_scale, (0, 0, 0), thickness, cv2.LINE_AA)

        return out

    # ── private ───────────────────────────────────────────────────────────────

    @staticmethod
    def _build_deepsort_input(
        detections: list[Detection],
    ) -> list:
        """Convert Detection objects to strict DeepSORT input format."""
        result = []
        for det in detections:
            x1, y1, x2, y2 = det.bbox
            # Ensure float types to avoid 'Inconsistent object during array creation'
            tlwh = [float(x1), float(y1), float(x2 - x1), float(y2 - y1)]
            result.append((tlwh, float(det.confidence), int(det.class_id)))
        return result

    @staticmethod
    def _id_color(track_id: int) -> tuple[int, int, int]:
        """Deterministic colour per track ID."""
        palette = [
            (255, 80, 80), (80, 255, 80), (80, 80, 255),
            (255, 200, 0), (0, 200, 255), (200, 0, 255),
            (255, 100, 200), (100, 255, 200), (200, 100, 255),
        ]
        return palette[track_id % len(palette)]
