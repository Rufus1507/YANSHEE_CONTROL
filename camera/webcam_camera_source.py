import threading
import time
import cv2
import numpy as np
from typing import Optional, Tuple

from logs.logger import get_logger
from config import (
    CAMERA_INDEX,
    CAMERA_RECONNECT_DELAY,
    AUTO_RECONNECT,
)
from .camera_source import CameraSource

logger = get_logger(__name__)

class WebcamCameraSource(CameraSource):
    """Camera source that reads frames from a local webcam using OpenCV.

    The implementation runs a background thread that continuously captures
    frames from ``cv2.VideoCapture``. The latest JPEG bytes and timestamp are
    stored and can be accessed via ``read``. FPS and latency metrics are
    updated for the dashboard.
    """

    def __init__(self, bus):
        self.bus = bus
        self.running = False
        self._cap: Optional[cv2.VideoCapture] = None
        self._jpeg: Optional[bytes] = None
        self._ts: float = 0.0
        self._fps: float = 0.0
        self._latency: float = 0.0
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        self._last_frame_ts: float = 0.0

    def start(self) -> None:
        self.running = True
        self._thread = threading.Thread(target=self._capture_loop, daemon=True)
        self._thread.start()
        logger.info("WebcamCameraSource thread started (camera index=%s).", CAMERA_INDEX)

    def stop(self) -> None:
        self.running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.5)
            self._thread = None
        if self._cap:
            try:
                self._cap.release()
            except Exception:
                pass
            self._cap = None
        self.bus.emit("CAMERA_STOPPED", {})
        logger.info("WebcamCameraSource stopped.")

    def _capture_loop(self) -> None:
        import platform
        while self.running:
            try:
                if self._cap is None:
                    if platform.system() == "Windows" and isinstance(CAMERA_INDEX, int):
                        self._cap = cv2.VideoCapture(CAMERA_INDEX, cv2.CAP_DSHOW)
                        if not self._cap.isOpened():
                            self._cap = cv2.VideoCapture(CAMERA_INDEX)
                    else:
                        self._cap = cv2.VideoCapture(CAMERA_INDEX)

                    if not self._cap.isOpened():
                        raise RuntimeError(f"Cannot open webcam at index {CAMERA_INDEX}")
                    self.bus.emit("CAMERA_CONNECTED", {})
                    logger.info("Webcam opened successfully.")
                ret, frame = self._cap.read()
                if not ret:
                    raise RuntimeError("Failed to read frame from webcam")
                # Encode to JPEG for consistency
                success, jpeg = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
                if not success:
                    raise RuntimeError("Failed to encode webcam frame to JPEG")
                ts = time.time()
                with self._lock:
                    self._jpeg = jpeg.tobytes()
                    self._ts = ts
                    if self._last_frame_ts:
                        self._fps = 1.0 / max(ts - self._last_frame_ts, 0.001)
                    self._last_frame_ts = ts
                    self._latency = (time.time() - ts) * 1000.0
                self.bus.emit("CAMERA_STATUS", {"status": "online"})
                time.sleep(0.01)
            except Exception as exc:
                if not self.running:
                    break
                logger.error(f"Webcam source error: {exc}")
                self.bus.emit("CAMERA_ERROR", {"error": str(exc)})
                if self._cap:
                    try:
                        self._cap.release()
                    except Exception:
                        pass
                    self._cap = None
                if AUTO_RECONNECT and self.running:
                    self.bus.emit("CAMERA_RECONNECTING", {})
                    for _ in range(int(CAMERA_RECONNECT_DELAY * 10)):
                        if not self.running:
                            break
                        time.sleep(0.1)
                else:
                    break
        if self._cap:
            try:
                self._cap.release()
            except Exception:
                pass
            self._cap = None
        self.bus.emit("CAMERA_DISCONNECTED", {})

    def read(self) -> Optional[Tuple[bytes, float]]:
        with self._lock:
            if self._jpeg is None:
                return None
            return self._jpeg, self._ts

    def get_fps(self) -> float:
        return self._fps

    def get_latency(self) -> float:
        return self._latency
