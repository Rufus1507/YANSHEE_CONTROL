import asyncio
import time
import cv2
import numpy as np
from typing import Optional

from logs.logger import get_logger
from events.event_bus import EventBus
from config import (
    YANSHEE_CAMERA_ENABLED,
    CAMERA_RECONNECT_DELAY,
    AUTO_RECONNECT,
    MAX_FRAME_QUEUE,
)

# Local imports of the abstraction
from .camera_source import CameraSource
from .yanshee_camera_source import YansheeCameraSource

logger = get_logger(__name__)


class CameraManager:
    """Quản lý nguồn camera và cung cấp khung hình cho pipeline.

    - Khi ``YANSHEE_CAMERA_ENABLED=True`` sẽ khởi tạo ``YansheeCameraSource``
      (MJPEG HTTP).
    - Liên tục đọc JPEG từ source, decode thành numpy frame, và:
      * Lưu JPEG mới nhất cho Dashboard ``/video_feed``.
      * Emit event ``FRAME_READY`` kèm numpy frame cho pipeline nhận diện.
    - Queue async có kích thước tối đa ``MAX_FRAME_QUEUE`` (mặc định 2) để luôn
      giữ khung hình mới nhất, tránh backlog.
    """

    def __init__(self, bus: EventBus):
        self.bus = bus
        self.running = False
        self._source: Optional[CameraSource] = None

        # Lưu JPEG mới nhất cho dashboard /video_feed (thread-safe qua GIL)
        self._latest_jpeg: Optional[bytes] = None

        # Metrics
        self.fps: float = 0.0
        self.latency: float = 0.0

    # ---------------------------------------------------------------------
    # Internal coroutine: liên tục đọc JPEG từ source, decode, emit frame
    # ---------------------------------------------------------------------
    async def _poll_source(self) -> None:
        """Đọc JPEG liên tục từ CameraSource, decode thành numpy frame,
        lưu JPEG cho dashboard, và emit FRAME_READY cho pipeline.
        Chỉ emit khi có frame MỚI (timestamp thay đổi)."""
        _last_ts: float = 0.0
        while self.running:
            if self._source is None:
                await asyncio.sleep(0.1)
                continue

            data = self._source.read()
            if data is None:
                # Không có frame – có thể đang reconnect
                await asyncio.sleep(0.05)
                continue

            jpeg, ts = data

            # Bỏ qua nếu frame chưa đổi (tránh emit lặp cùng 1 frame)
            if ts == _last_ts:
                await asyncio.sleep(0.01)
                continue
            _last_ts = ts

            # Cập nhật metric
            self.fps = self._source.get_fps()
            self.latency = self._source.get_latency()

            # Lưu JPEG cho dashboard
            self._latest_jpeg = jpeg

            # Decode JPEG → numpy frame cho pipeline
            frame = self._decode_jpeg(jpeg)
            if frame is None:
                await asyncio.sleep(0.01)
                continue

            # Emit FRAME_READY kèm cả frame numpy (cho pipeline)
            # và fps (cho dashboard metrics)
            self.bus.emit("FRAME_READY", {"frame": frame, "fps": self.fps})

            # Nhường event loop để dashboard/websocket có thể xử lý
            await asyncio.sleep(0)

    @staticmethod
    def _decode_jpeg(jpeg_bytes: bytes) -> Optional[np.ndarray]:
        """Decode JPEG bytes thành numpy BGR frame."""
        try:
            arr = np.frombuffer(jpeg_bytes, dtype=np.uint8)
            frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
            return frame
        except Exception:
            return None

    # ---------------------------------------------------------------------
    # Public API
    # ---------------------------------------------------------------------
    async def run(self) -> None:
        """Khởi động nguồn camera và bắt đầu polling.
        Hàm này được gọi trong vòng lặp asyncio của main.py.
        """
        self.running = True
        # Chọn nguồn camera
        if YANSHEE_CAMERA_ENABLED:
            self._source = YansheeCameraSource(self.bus)
        else:
            raise NotImplementedError(
                "Legacy webcam không còn hỗ trợ – bật YANSHEE_CAMERA_ENABLED trong config."
            )
        self._source.start()
        logger.info("Camera source started.")
        # Bắt đầu task poll
        poll_task = asyncio.create_task(self._poll_source())
        while self.running:
            await asyncio.sleep(1.0)
        # Dừng nguồn và task
        if self._source:
            self._source.stop()
        poll_task.cancel()
        logger.info("CameraManager stopped.")

    # ---------------------------------------------------------------------
    # Các hàm được dashboard / pipeline gọi
    # ---------------------------------------------------------------------
    def get_latest_jpeg(self) -> Optional[bytes]:
        """Lấy JPEG mới nhất (sync, dùng cho dashboard /video_feed)."""
        return self._latest_jpeg

    def stop(self) -> None:
        """Dừng vòng lặp và đóng nguồn camera."""
        self.running = False
