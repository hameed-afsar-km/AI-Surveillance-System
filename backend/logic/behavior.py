"""
behavior.py – AI Surveillance Behavior Analysis Engine.

Active Detection Modules:
  0.  CUSTOM MODEL EVENTS  – Direct detections from trained model (fire, accident, fall, garbage)
  1.  FIRE DETECTION        – HSV fallback if custom model misses
  2.  ACCIDENT DETECTION    – Speed-physics convergence + sudden freeze (COCO tracks)
  3.  CROWDING DETECTION    – ≥10 same-category entities in a 300 px radius
  4.  LITTERING DETECTION   – Person carries object, walks away, object stays ≥7 s
  5.  HUMAN ABNORMAL MOVEMENT – Collapse / health-issue / fatality heuristic
  6.  THEFT DETECTION       – Sudden disappearance or abnormal fast movement of objects (handbags, laptops, etc.)
"""

import time
import cv2
import numpy as np
import math
from collections import deque
from dataclasses import dataclass, field
from typing import Optional

from config import cfg
from vision.tracking import TrackState
from utils.logger import get_logger

log = get_logger("logic.behavior")


# ─── Data ──────────────────────────────────────────────────────────────────────

@dataclass
class BehaviorAlert:
    alert: bool
    alert_type: str
    message: str
    severity: str = "medium"
    people_count: int = 0
    involved_ids: list[int] = field(default_factory=list)
    zone: Optional[str] = None
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            "alert":       self.alert,
            "type":        self.alert_type,
            "message":     self.message,
            "severity":    self.severity,
            "people_count":self.people_count,
            "involved_ids":self.involved_ids,
            "zone":        self.zone,
            "timestamp":   self.timestamp,
        }


_NO_ALERT = BehaviorAlert(alert=False, alert_type="none", message="System nominal.")


# ─── Speed helpers ─────────────────────────────────────────────────────────────

def _speed_full(track: TrackState) -> float:
    """Average speed over the entire position history (px/s → km/h proxy)."""
    if len(track.position_history) < 10:
        return 0.0
    p1 = track.position_history[0]
    p2 = track.position_history[-1]
    dist = math.hypot(p2[0] - p1[0], p2[1] - p1[1])
    pps  = dist / (len(track.position_history) / max(cfg.TARGET_FPS, 10.0))
    return (pps / 150.0) * 40.0


def _speed_recent(track: TrackState, n: int = 4) -> float:
    """Speed over the last *n* frames (detects sudden stops)."""
    if len(track.position_history) < n + 1:
        return 0.0
    p1 = track.position_history[-(n + 1)]
    p2 = track.position_history[-1]
    dist = math.hypot(p2[0] - p1[0], p2[1] - p1[1])
    pps  = dist / (n / max(cfg.TARGET_FPS, 10.0))
    return (pps / 150.0) * 40.0


def _iou(bboxA: tuple, bboxB: tuple) -> float:
    xA = max(bboxA[0], bboxB[0]);  yA = max(bboxA[1], bboxB[1])
    xB = min(bboxA[2], bboxB[2]);  yB = min(bboxA[3], bboxB[3])
    inter = max(0, xB - xA) * max(0, yB - yA)
    aA = (bboxA[2]-bboxA[0]) * (bboxA[3]-bboxA[1])
    aB = (bboxB[2]-bboxB[0]) * (bboxB[3]-bboxB[1])
    denom = aA + aB - inter
    return inter / denom if denom > 0 else 0.0


# ─── Engine ────────────────────────────────────────────────────────────────────

class BehaviorEngine:

    # How close (px) an object must be to a person to be "carried"
    CARRY_RADIUS   = 130
    # Seconds an object must remain unattended before littering is flagged
    LITTER_TIMEOUT = 7.0
    # Minimum number of same-category entities in a cluster to trigger crowding
    CROWD_THRESHOLD = 10
    # Radius (px) for crowding cluster check
    CROWD_RADIUS    = 300

    def __init__(self) -> None:
        # Unique events already flagged (prevents duplicate alerts)
        self._flagged: set = set()

        # Littering state: obj_id → {"first_seen": float, "carried": bool}
        self._obj_state: dict = {}

        # Accident: per-entity rolling speed deque
        self._speed_hist: dict[int, deque] = {}
        self._fall_timers: dict[int, dict] = {}          # Track down-time for falls
        self._custom_event_times: dict[str, float] = {}  # throttle per custom label

        log.info("BehaviorEngine initialised — 6 active modules (incl. custom model).")

    # ──────────────────────────────────────────────────────────────────────────
    # Public API
    # ──────────────────────────────────────────────────────────────────────────

    def analyse(
        self,
        active_tracks: list[TrackState],
        frame: np.ndarray,
        custom_events: list | None = None,
        exited_tracks: list[TrackState] | None = None,
    ) -> BehaviorAlert:
        now      = time.time()
        exited_tracks = exited_tracks or []
        people   = [t for t in active_tracks if t.class_id == 0]
        vehicles = [t for t in active_tracks if t.class_id in (1, 2, 3, 5, 7)]
        objects  = [t for t in active_tracks if t.class_id in (24, 39, 41)]  # backpack, bottle, cup

        alerts: list[BehaviorAlert] = []
        custom_labels_found: set[str] = set()

        # ── MODULE 0: CUSTOM MODEL EVENTS (ML-powered) ────────────────────────
        # These come directly from the trained model — highest confidence
        if custom_events:
            severity_map = {
                "fire":     "critical",
                "accident": "critical",
                "fall":     "critical",
                "garbage":  "medium",
            }
            msg_map = {
                "fire":     "FIRE DETECTED by AI Model: Flames or combustion signature identified in scene.",
                "accident": "ACCIDENT DETECTED by AI Model: Collision or crash event identified in scene.",
                "fall":     "FALL/COLLAPSE DETECTED by AI Model: Person down or medical emergency identified.",
                "garbage":  "GARBAGE DETECTED by AI Model: Waste accumulation or littering identified in scene.",
            }
            alert_type_map = {
                "fire":     "fire_hazard",
                "accident": "collision",
                "fall":     "medical_emergency",
                "garbage":  "garbage_hotspot",
            }
            # Deduplicate by label — send one alert per label type per cycle
            seen_labels: set[str] = set()
            for ev in custom_events:
                lbl = ev.label

                # Garbage is detected only on objects, not cars.
                if lbl == "garbage":
                    overlap_car = any(_iou(ev.bbox, v.bbox) > 0.3 for v in vehicles)
                    if overlap_car:
                        continue
                
                # Fall/collapse relies on velocity + 10s wait logic handled strictly in Module 5.
                if lbl == "fall":
                    continue

                custom_labels_found.add(lbl)
                if lbl in seen_labels:
                    continue
                seen_labels.add(lbl)
                fid = f"custom-{lbl}-{int(now)}"
                # Throttle: only re-alert same custom type every 10s
                last_t = self._custom_event_times.get(lbl, 0.0)
                if now - last_t < 10.0:
                    continue
                self._custom_event_times[lbl] = now
                alerts.append(BehaviorAlert(
                    alert=True,
                    alert_type=alert_type_map.get(lbl, lbl),
                    severity=severity_map.get(lbl, "high"),
                    message=msg_map.get(lbl, f"{lbl.upper()} detected."),
                    people_count=len(people),
                ))
                log.info("Custom model event: %s (conf=%.0f%%)", lbl, ev.confidence * 100)

        # ── MODULE 1: FIRE DETECTION (HSV fallback) ───────────────────────────
        # Skip if custom model already detected fire (avoid duplicate alerts)
        if "fire" not in custom_labels_found and self._check_fire(frame):
            last_t = self._custom_event_times.get("fire_hsv", 0.0)
            if now - last_t >= 10.0:
                self._custom_event_times["fire_hsv"] = now
                alerts.append(BehaviorAlert(
                    alert=True, alert_type="fire_hazard", severity="critical",
                    message="CRITICAL: Fire/Combustion signature detected (HSV filter)!"
                ))

        # ── MODULE 2: ACCIDENT DETECTION ─────────────────────────────────────
        all_movers = people + vehicles

        # Rolling speed history per entity
        for e in all_movers:
            if e.track_id not in self._speed_hist:
                self._speed_hist[e.track_id] = deque(maxlen=25)
            self._speed_hist[e.track_id].append(_speed_full(e))

        # 2a. Two entities overlapping + sudden freeze
        for i in range(len(all_movers)):
            for j in range(i + 1, len(all_movers)):
                e1, e2 = all_movers[i], all_movers[j]
                if _iou(e1.bbox, e2.bbox) < 0.10:
                    continue

                h1 = self._speed_hist.get(e1.track_id, deque())
                h2 = self._speed_hist.get(e2.track_id, deque())
                prev1 = (sum(list(h1)[:-5]) / max(len(h1) - 5, 1)) if len(h1) > 6 else 0.0
                prev2 = (sum(list(h2)[:-5]) / max(len(h2) - 5, 1)) if len(h2) > 6 else 0.0
                now1  = _speed_recent(e1)
                now2  = _speed_recent(e2)

                was_fast  = prev1 > 8.0 or prev2 > 8.0
                now_slow  = now1 < 3.0 or now2 < 3.0
                if was_fast and now_slow:
                    pid = f"acc-{min(e1.track_id, e2.track_id)}-{max(e1.track_id, e2.track_id)}"
                    if pid not in self._flagged:
                        self._flagged.add(pid)
                        alerts.append(BehaviorAlert(
                            alert=True, alert_type="collision", severity="critical",
                            involved_ids=[e1.track_id, e2.track_id],
                            message=f"ACCIDENT ALERT: Entities {e1.track_id} & {e2.track_id} collided — sudden stop detected!"
                        ))

        # 2b. Single entity: high speed → abrupt stop (vehicle/person impact)
        for t in all_movers:
            hist = self._speed_hist.get(t.track_id, deque())
            if len(hist) > 9:
                avg_past = sum(list(hist)[:-4]) / max(len(hist) - 4, 1)
                if avg_past > 15.0 and _speed_recent(t) < 2.0:
                    fid = f"impact-{t.track_id}"
                    if fid not in self._flagged:
                        self._flagged.add(fid)
                        alerts.append(BehaviorAlert(
                            alert=True, alert_type="collision", severity="critical",
                            involved_ids=[t.track_id],
                            message=f"ACCIDENT ALERT: Entity {t.track_id} made an abnormal sudden stop from high speed!"
                        ))

        # ── MODULE 3: CROWDING DETECTION ─────────────────────────────────────
        for cat_name, items in [("people", people), ("vehicles", vehicles)]:
            if len(items) < self.CROWD_THRESHOLD:
                continue
            for anchor in items:
                cx, cy = anchor.center
                nearby = sum(
                    1 for o in items
                    if math.hypot(o.center[0] - cx, o.center[1] - cy) < self.CROWD_RADIUS
                )
                if nearby >= self.CROWD_THRESHOLD:
                    fid = f"crowd-{cat_name}-{anchor.track_id}"
                    if fid not in self._flagged:
                        self._flagged.add(fid)
                        alerts.append(BehaviorAlert(
                            alert=True, alert_type="overcrowding", severity="high",
                            people_count=nearby,
                            message=f"Overcrowding: Dense cluster of {nearby} {cat_name} in a localised area."
                        ))
                    break  # one alert per category per cycle

        # ── MODULE 4: LITTERING DETECTION (throw-and-abandon) ────────────────
        active_obj_ids = {o.track_id for o in objects}

        # Purge state for objects that have left the frame
        for oid in list(self._obj_state.keys()):
            if oid not in active_obj_ids:
                del self._obj_state[oid]

        for obj in objects:
            ox, oy = obj.center

            # Is any person close enough to be carrying this object?
            person_nearby = any(
                math.hypot(p.center[0] - ox, p.center[1] - oy) < self.CARRY_RADIUS
                for p in people
            )

            state = self._obj_state.setdefault(obj.track_id, {
                "first_seen":   now,
                "ever_carried": False,
                "drop_time":    None,
            })

            if person_nearby:
                # Object is currently "with" a person
                state["ever_carried"] = True
                state["drop_time"]    = None  # reset drop timer
            elif state["ever_carried"]:
                # Person walked away — start counting abandonment
                if state["drop_time"] is None:
                    state["drop_time"] = now

                abandoned_secs = now - state["drop_time"]
                if abandoned_secs >= self.LITTER_TIMEOUT and obj.track_id not in self._flagged:
                    self._flagged.add(obj.track_id)
                    alerts.append(BehaviorAlert(
                        alert=True, alert_type="littering", severity="high",
                        involved_ids=[obj.track_id],
                        message=(
                            f"LITTERING ALERT: Object (ID {obj.track_id}) was carried by a person "
                            f"and then abandoned for {abandoned_secs:.0f}s in a public area."
                        )
                    ))

        # ── MODULE 5: HUMAN ABNORMAL MOVEMENT & COLLAPSE ─────────────────────
        active_people_ids = {p.track_id for p in people}
        for pid in list(self._fall_timers.keys()):
            if pid not in active_people_ids:
                del self._fall_timers[pid]

        for p in people:
            if p.duration < 2.0:
                continue

            x1, y1, x2, y2 = p.bbox
            bw, bh = x2 - x1, y2 - y1
            if bh <= 0:
                continue

            aspect    = bw / bh          # > 1.4 → lying flat
            spd       = _speed_recent(p) # near zero → motionless
            hist      = self._speed_hist.get(p.track_id, deque())
            # Check historical speed further back to see if they were moving before down-state
            avg_spd   = sum(list(hist)[:-5]) / max(1, len(hist) - 5) if len(hist) > 5 else 0.0

            # Scenario A: custom model explicitly detected "fall"
            model_fall = any(ev.label == "fall" and _iou(p.bbox, ev.bbox) > 0.2 for ev in custom_events) if custom_events else False
            
            # Scenario B: Heuristics
            collapsed = aspect > 1.4 and spd < 1.5
            sudden_freeze = avg_spd > 5.0 and spd < 1.0 and aspect < 1.2
            
            is_down_now = collapsed or sudden_freeze or (model_fall and spd < 1.5)

            if is_down_now:
                state = self._fall_timers.setdefault(p.track_id, {
                    "first_down": now,
                    "was_moving": avg_spd > 2.0,  # Requirement: goes at some velocity prior
                    "reason": "AI verified fall" if model_fall else ("collapsed on ground" if collapsed else "sudden freeze")
                })
                
                down_time = now - state["first_down"]
                
                # Wait for 10 seconds for the person to show at least a little movement
                if down_time >= 10.0 and state["was_moving"]:
                    if p.track_id not in self._flagged:
                        self._flagged.add(p.track_id)
                        alerts.append(BehaviorAlert(
                            alert=True, alert_type="medical_emergency", severity="critical",
                            involved_ids=[p.track_id],
                            message=(
                                f"MEDICAL ALERT: Person {p.track_id} fell/collapsed after moving and has been motionless for 10 seconds! "
                                f"({state['reason']})"
                            )
                        ))
            else:
                # Recovered or showed movement (false alarm)
                if p.track_id in self._fall_timers:
                    del self._fall_timers[p.track_id]

        # ── MODULE 6: THEFT DETECTION ────────────────────────────────────────
        # Classes: 24 (backpack), 26 (handbag), 28 (suitcase), 63 (laptop), 67 (cell phone)
        theftable_classes = {24, 26, 28, 63, 67}
        active_theftable = [t for t in active_tracks if t.class_id in theftable_classes]
        exited_theftable = [t for t in exited_tracks if t.class_id in theftable_classes]

        # 6a. Sudden disappearance of object when a person was nearby OR snatched (high speed before exit)
        for obj in exited_theftable:
            ox, oy = obj.center
            obj_speed = sum(list(self._speed_hist.get(obj.track_id, [0]))) / max(1, len(self._speed_hist.get(obj.track_id, [1])))
            
            # Is a person near the vanished object's last known location?
            thief = next((p for p in people if math.hypot(p.center[0] - ox, p.center[1] - oy) < self.CARRY_RADIUS * 1.5), None)
            
            is_snatched = obj_speed > 10.0
            
            if (is_snatched or thief) and obj.track_id not in self._flagged:
                self._flagged.add(obj.track_id)
                alerts.append(BehaviorAlert(
                    alert=True, alert_type="theft", severity="high",
                    involved_ids=[obj.track_id, thief.track_id] if thief else [obj.track_id],
                    message=f"THEFT ALERT: Object {obj.track_id} vanished abruptly near a person or was pulled fast!"
                ))
                
        # 6b. Abnormal activity: object moving extremely fast while near a person (snatch and run)
        for obj in active_theftable:
            ox, oy = obj.center
            obj_speed = _speed_recent(obj)
            person_nearby = any(math.hypot(p.center[0] - ox, p.center[1] - oy) < self.CARRY_RADIUS for p in people)
            
            if person_nearby and obj_speed > 15.0:
                if obj.track_id not in self._flagged:
                    self._flagged.add(obj.track_id)
                    alerts.append(BehaviorAlert(
                        alert=True, alert_type="theft", severity="critical",
                        involved_ids=[obj.track_id],
                        message=f"THEFT ALERT: Object {obj.track_id} moving abnormally fast near a person!"
                    ))

        # ── Return highest severity alert ─────────────────────────────────────
        if not alerts:
            return _NO_ALERT

        severity_order = {"low": 0, "medium": 1, "high": 2, "critical": 3}
        alerts.sort(key=lambda a: severity_order.get(a.severity, 0), reverse=True)
        return alerts[0]

    # ──────────────────────────────────────────────────────────────────────────
    # Fire CV check
    # ──────────────────────────────────────────────────────────────────────────

    @staticmethod
    def _check_fire(frame: np.ndarray) -> bool:
        """Detect intense fire-orange/yellow pixels using HSV thresholding."""
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        # Broadened the fire spectrum slightly and lowered saturation requirement
        lower = np.array([12, 120, 200])
        upper = np.array([32, 255, 255])
        # Relaxed pixel count from 4000 -> 300 to detect smaller or further away fires
        return cv2.countNonZero(cv2.inRange(hsv, lower, upper)) > 300

    # ──────────────────────────────────────────────────────────────────────────
    # Reset
    # ──────────────────────────────────────────────────────────────────────────

    def reset(self) -> None:
        self._flagged.clear()
        self._obj_state.clear()
        self._speed_hist.clear()
        log.info("BehaviorEngine reset.")