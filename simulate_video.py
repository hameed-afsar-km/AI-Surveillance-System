"""
simulate_video.py
-----------------
Generates two synthetic simulation videos:
  • videos/normal.mp4   – 1-2 people walking
  • videos/crowded.mp4  – 6-8 people clustered (triggers overcrowding)

These are placeholder videos using OpenCV drawing so the system
works without real camera footage. Replace with real footage for production.

Run once: python simulate_video.py
"""

import cv2
import numpy as np
import math
import random
from pathlib import Path


class Person:
    def __init__(self, x, y, vx, vy, color, w=40, h=90):
        self.x, self.y = float(x), float(y)
        self.vx, self.vy = float(vx), float(vy)
        self.color = color
        self.w, self.h = w, h

    def update(self, frame_w, frame_h):
        self.x += self.vx
        self.y += self.vy
        if self.x < 0 or self.x + self.w > frame_w:
            self.vx *= -1
        if self.y < 0 or self.y + self.h > frame_h:
            self.vy *= -1

    def draw(self, frame):
        x, y = int(self.x), int(self.y)
        # Body
        cv2.rectangle(frame, (x, y + 28), (x + self.w, y + self.h), self.color, -1)
        # Head
        cx, cy = x + self.w // 2, y + 15
        cv2.circle(frame, (cx, cy), 15, self.color, -1)


def _make_video(path: Path, people: list["Person"], fps: int = 20, duration: int = 30):
    W, H = 960, 540
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    path.parent.mkdir(parents=True, exist_ok=True)
    out = cv2.VideoWriter(str(path), fourcc, fps, (W, H))

    bg_color = (20, 30, 50)
    floor_color = (35, 45, 60)
    total_frames = fps * duration

    for i in range(total_frames):
        frame = np.full((H, W, 3), bg_color, dtype=np.uint8)
        # Floor lines
        for fx in range(0, W, 80):
            cv2.line(frame, (fx, H // 2), (fx, H), floor_color, 1)
        for fy in range(H // 2, H, 40):
            cv2.line(frame, (0, fy), (W, fy), floor_color, 1)

        t = i / fps
        # Animated timestamp
        ts = f"{int(t // 60):02d}:{int(t % 60):02d}"
        cv2.putText(frame, ts,      (14, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (180, 200, 220), 1)
        cv2.putText(frame, "SIM", (W - 60, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (80, 200, 100), 1)

        for p in people:
            p.update(W, H)
            p.draw(frame)

        out.write(frame)

    out.release()
    print(f"Generated: {path}")


def make_normal():
    random.seed(1)
    people = [
        Person(100, 200, 1.5, 0.4, (0, 180, 120)),
        Person(600, 300, -1.2, 0.6, (80, 140, 255)),
    ]
    _make_video(Path("videos/normal.mp4"), people, duration=30)


def make_crowded():
    random.seed(42)
    colors = [(0,180,100),(80,120,255),(255,100,80),(200,180,0),
              (0,200,200),(180,80,255),(255,160,40),(120,220,160)]
    people = []
    for i, c in enumerate(colors):
        ox = random.randint(200, 760)
        oy = random.randint(180, 400)
        vx = random.uniform(-1.0, 1.0)
        vy = random.uniform(-0.5, 0.5)
        people.append(Person(ox, oy, vx, vy, c))
    _make_video(Path("videos/crowded.mp4"), people, duration=30)


if __name__ == "__main__":
    make_normal()
    make_crowded()
    print("\nDone! Both simulation videos created in /videos/")
