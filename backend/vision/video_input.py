"""
video_input.py – Multi-threaded video source.
"""

import cv2
import time
import threading
import queue
from pathlib import Path
from typing import Optional, Tuple

from config import cfg
from utils.logger import get_logger

log = get_logger("vision.video_input")


class VideoSource:
    """
    Multi-threaded Frame Reader.
    Pushes raw frames into a thread-safe queue.
    """

    def __init__(
        self,
        source: int | str,
        *,
        loop_file: bool = True,
    ) -> None:
        self.source = source
        self.loop_file = loop_file
        self._cap: Optional[cv2.VideoCapture] = None
        
        # Threaded Queue for Frame Reader Thread
        self.frame_queue = queue.Queue(maxsize=10)
        self._stopped = False
        
        self._open()
        
        # 1. Frame Reader Thread
        self._reader_thread = threading.Thread(target=self._reader_loop, daemon=True)
        self._reader_thread.start()

    @classmethod
    def from_config(cls) -> "VideoSource":
        src = cfg.DEFAULT_VIDEO_SOURCE
        if src == "webcam":
            return cls(cfg.DEFAULT_WEBCAM_INDEX, loop_file=False)
        path = Path(src)
        if not path.is_absolute():
            path = cfg.VIDEOS_DIR / src
        if not path.exists():
            raise FileNotFoundError(f"Video file not found: {path}")
        return cls(str(path), loop_file=True)

    @classmethod
    def from_file(cls, filename: str) -> "VideoSource":
        path = Path(filename)
        if not path.is_absolute():
            path = cfg.VIDEOS_DIR / filename
        if not path.exists():
            raise FileNotFoundError(f"Video file not found: {path}")
        return cls(str(path), loop_file=True)

    @classmethod
    def from_webcam(cls, index: int = 0) -> "VideoSource":
        return cls(index, loop_file=False)

    def _reader_loop(self) -> None:
        """Frame Reader Thread: continuously reads frames and pushes to queue."""
        log.info("Frame Reader Thread started for source %s", self.source)
        while not self._stopped:
            if not self._cap or not self._cap.isOpened():
                break
                
            ok, frame = self._cap.read()
            if not ok:
                if self.loop_file and isinstance(self.source, str):
                    self._cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    continue
                else:
                    self._stopped = True
                    break
            
            # Avoid blocking indefinitely if queue is full (drop oldest if necessary, or just wait slightly)
            try:
                self.frame_queue.put(frame, timeout=0.1)
            except queue.Full:
                try:
                    self.frame_queue.get_nowait()
                    self.frame_queue.put_nowait(frame)
                except queue.Empty:
                    pass
        log.info("Frame Reader Thread exiting.")

    def read(self) -> Tuple[bool, Optional[any]]:
        """Pull frame from queue."""
        if self._stopped and self.frame_queue.empty():
            return False, None
        try:
            frame = self.frame_queue.get(timeout=0.1)
            return True, frame
        except queue.Empty:
            return not self._stopped, None

    def release(self) -> None:
        self._stopped = True
        self._reader_thread.join(timeout=1.0)
        if self._cap and self._cap.isOpened():
            self._cap.release()
            log.info("VideoCapture released: %s", self.source)

    @property
    def fps(self) -> float:
        return self._cap.get(cv2.CAP_PROP_FPS) if self._cap else 30.0

    @property
    def width(self) -> int:
        return int(self._cap.get(cv2.CAP_PROP_FRAME_WIDTH)) if self._cap else 0

    @property
    def height(self) -> int:
        return int(self._cap.get(cv2.CAP_PROP_FRAME_HEIGHT)) if self._cap else 0

    def _open(self) -> None:
        if isinstance(self.source, int) or (isinstance(self.source, str) and self.source.isdigit()):
            self.source = int(self.source)
            self._cap = cv2.VideoCapture(self.source, cv2.CAP_DSHOW)
            self._cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            self._cap.set(cv2.CAP_PROP_FPS, cfg.TARGET_FPS)
        else:
            self._cap = cv2.VideoCapture(self.source)
            self._cap.set(cv2.CAP_PROP_FPS, cfg.TARGET_FPS)

        if not self._cap.isOpened():
            raise RuntimeError(f"Cannot open video source: {self.source}")
        log.info("Opened source '%s' @ %.1f fps", self.source, self.fps)

    def __repr__(self) -> str:
        return f"<VideoSource source={self.source!r}>"
