"""
generate_alert_sound.py
-----------------------
Generates a WAV alert beep sound so the system works out-of-the-box
even without a pre-recorded sound file.

Run once: python generate_alert_sound.py
"""

import struct
import math
import wave
from pathlib import Path


def generate_beep(
    filepath: Path,
    frequency: float = 880.0,
    duration: float = 0.8,
    sample_rate: int = 44100,
    amplitude: int = 28000,
) -> None:
    filepath.parent.mkdir(parents=True, exist_ok=True)
    n_samples = int(sample_rate * duration)
    samples = []

    for i in range(n_samples):
        t = i / sample_rate
        # Envelope: quick attack, slow decay
        env = min(t / 0.01, 1.0) * max(1.0 - (t - 0.05) / (duration - 0.05), 0.0)
        # Harmonic beep
        val = int(amplitude * env * (
            0.6 * math.sin(2 * math.pi * frequency * t) +
            0.3 * math.sin(2 * math.pi * frequency * 2 * t) +
            0.1 * math.sin(2 * math.pi * frequency * 3 * t)
        ))
        val = max(-32768, min(32767, val))
        samples.append(val)

    # Repeat 3 times with gaps
    gap = [0] * int(sample_rate * 0.15)
    full = samples + gap + samples + gap + samples

    with wave.open(str(filepath), "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(struct.pack(f"<{len(full)}h", *full))

    print(f"Alert sound generated: {filepath}")


if __name__ == "__main__":
    out = Path(__file__).resolve().parent / "assets" / "sounds" / "alert.wav"
    generate_beep(out)
