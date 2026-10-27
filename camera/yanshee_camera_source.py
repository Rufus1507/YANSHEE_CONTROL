import threading
import time
import requests
from typing import Optional, Tuple
from logs.logger import get_logger
from config import (
    YANSHEE_IP,
    YANSHEE_STREAM_PORT,
    YANSHEE_STREAM_TIMEOUT,
    CAMERA_RECONNECT_DELAY,
    AUTO_RECONNECT,
    YANSHEE_CAMERA_ENABLED,
    CAMERA_HEALTH_TIMEOUT,
)
from .camera_source import CameraSource

logger = get_logger(__name__)

class YansheeCameraSource(CameraSource):
    """Camera source that reads an MJPEG stream from a Yanshee robot.
    It runs a background thread that continuously pulls JPEG frames from the
    HTTP endpoint ``http://<YANSHEE_IP>:<YANSHEE_STREAM_PORT>/stream.mjpg``.
    The thread stores the latest JPEG and timestamp, updates FPS and latency,
    and emits EventBus events for health monitoring.
    """

    def __init__(self, bus):
        self.bus = bus
        self.running = False
        self._jpeg: Optional[bytes] = None
        self._ts: float = 0.0
        self._fps: float = 0.0
        self._latency: float = 0.0
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        self._last_frame_ts: float = 0.0

    def start(self) -> None:
        if not YANSHEE_CAMERA_ENABLED:
            logger.warning("Yanshee camera is disabled in config – not starting source.")
            return
        self.running = True
        self._thread = threading.Thread(target=self._stream_loop, daemon=True)
        self._thread.start()
        logger.info("YansheeCameraSource thread started.")

    def stop(self) -> None:
        self.running = False
        if self._thread:
            self._thread.join(timeout=2)
        self.bus.emit("CAMERA_STOPPED", {})
        logger.info("YansheeCameraSource stopped.")

    def _stream_loop(self) -> None:
        url = f"http://{YANSHEE_IP}:{YANSHEE_STREAM_PORT}/stream.mjpg"
        while self.running:
            try:
                logger.info("Opening Yanshee MJPEG stream: {}", url)
                resp = requests.get(url, stream=True, timeout=YANSHEE_STREAM_TIMEOUT)
                if resp.status_code != 200:
                    raise RuntimeError(f"Bad HTTP status {resp.status_code}")
                self.bus.emit("CAMERA_CONNECTED", {})
                buffer = b""
                for chunk in resp.iter_content(chunk_size=1024):
                    if not self.running:
                        break
                    buffer += chunk
                    start = buffer.find(b"\xff\xd8")
                    end = buffer.find(b"\xff\xd9")
                    if start != -1 and end != -1 and end > start:
                        jpeg = buffer[start:end+2]
                        buffer = buffer[end+2:]
                        ts = time.time()
                        with self._lock:
                            self._jpeg = jpeg
                            self._ts = ts
                            # FPS estimation (simple moving average)
                            if self._last_frame_ts:
                                self._fps = 1.0 / max(ts - self._last_frame_ts, 0.001)
                            self._last_frame_ts = ts
                            self._latency = (time.time() - ts) * 1000.0  # ms
                        self.bus.emit("CAMERA_STATUS", {"status": "online"})
            except Exception as exc:
                logger.error("Yanshee stream error: {}", exc)
                self.bus.emit("CAMERA_ERROR", {"error": str(exc)})
                if AUTO_RECONNECT:
                    self.bus.emit("CAMERA_RECONNECTING", {})
                    time.sleep(CAMERA_RECONNECT_DELAY)
                else:
                    break
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
