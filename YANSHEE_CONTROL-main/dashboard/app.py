"""
FastAPI Dashboard — MJPEG video stream + WebSocket event relay.

THIẾT KẾ HIỆU NĂNG:
- MJPEG stream: đọc JPEG đã được encode sẵn từ CameraManager (không encode lại),
  dùng threading.Event để wake-up ngay khi có frame mới.
- WebSocket: broadcast các sự kiện qua asyncio.Queue per-connection.
  Không dùng asyncio.ensure_future per-event để tránh task explosion.
"""
import os
import json
import asyncio
# pyrefly: ignore [missing-import]
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
# pyrefly: ignore [missing-import]
from fastapi.staticfiles import StaticFiles
# pyrefly: ignore [missing-import]
from fastapi.responses import HTMLResponse, StreamingResponse
from events.event_bus import EventBus
from camera.camera_manager import CameraManager
from logs.logger import get_logger

logger = get_logger(__name__)

_FORWARD_EVENTS = [
    "FACE_DETECTED", "FACE_LOST", "FACE_QUALITY_POOR",
    "LIVENESS_STARTED", "LIVENESS_PASSED", "LIVENESS_FAILED", "LIVENESS_PROGRESS",
    "USER_RECOGNIZED", "USER_VERIFIED", "UNKNOWN_USER", "LOW_CONFIDENCE",
    "ROBOT_STATUS", "ROBOT_ACTION_STARTED", "ROBOT_ACTION_FAILED", "ROBOT_ACTION_SKIPPED",
    "ROBOT_SPEAKING_STARTED", "ROBOT_SPEAKING_FINISHED", "ROBOT_GREETING_STARTED", 
    "ROBOT_GREETING_FINISHED", "ROBOT_RESET_WAITING", "ROBOT_RESET_STARTED", "ROBOT_RESET_FINISHED", "ROBOT_READY",
    "CAMERA_STATUS", "CAMERA_CONNECTED", "CAMERA_RECONNECTING", "CAMERA_DISCONNECTED", "CAMERA_ERROR",
    "SYSTEM_ERROR", "SYSTEM_METRICS", "FRAME_READY", "PERFORMANCE_METRICS", "PIPELINE_METRICS",
    # Feature 5: Voice Control
    "VOICE_STATUS", "VOICE_RECOGNIZED", "VOICE_COMMAND", "VOICE_UNKNOWN_WORD",
    "VOICE_EXECUTING", "VOICE_COMMAND_SUCCESS", "VOICE_COMMAND_FAILED",
    # Feature 6: Smart Memory
    "MEMORY_UPDATED",
    # Feature 7: TTS tiếng Việt
    "TTS_STARTED", "TTS_FINISHED",
    # Action Queue
    "ACTION_QUEUE_UPDATE", "ACTION_EXECUTING", "ACTION_COMPLETED",
]


class _WSManager:
    """Quản lý nhiều WebSocket connections và broadcast message."""

    def __init__(self):
        # Mỗi connection có một asyncio.Queue riêng
        self._queues: list[asyncio.Queue] = []

    def add(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=50)
        self._queues.append(q)
        return q

    def remove(self, q: asyncio.Queue):
        try:
            self._queues.remove(q)
        except ValueError:
            pass

    def broadcast(self, msg: str):
        """Đẩy message vào tất cả queue; drop nếu queue đầy."""
        for q in self._queues:
            try:
                q.put_nowait(msg)
            except asyncio.QueueFull:
                pass  # Client chậm → drop frame


def create_app(bus: EventBus, camera: CameraManager) -> FastAPI:
    app = FastAPI(title="Yanshee Face Recognition Dashboard")
    static_dir = os.path.join(os.path.dirname(__file__), "static")
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

    ws_manager = _WSManager()

    # ─── Cache trạng thái mới nhất để gửi cho client mới kết nối ────────────
    _cached_state: dict[str, str] = {}  # event_type -> json string
    _CACHEABLE_EVENTS = {"ROBOT_STATUS", "CAMERA_STATUS"}

    # ─── Đăng ký tất cả events một lần, broadcast cho mọi ws connection ─────
    def _make_broadcaster(event_type: str):
        def handler(payload: dict):
            if event_type == "FRAME_READY":
                # Bổ sung latency và status từ CameraManager
                cam_info = {
                    "fps": payload.get("fps", 0),
                    "latency_ms": getattr(camera, "latency", 0.0),
                    "source": "yanshee",
                }
                data = json.dumps({"type": "FRAME_READY", "payload": cam_info})
            else:
                try:
                    data = json.dumps({"type": event_type, "payload": payload})
                except (TypeError, ValueError):
                    return
            # Cache trạng thái quan trọng
            if event_type in _CACHEABLE_EVENTS:
                _cached_state[event_type] = data
            ws_manager.broadcast(data)
        return handler

    for et in _FORWARD_EVENTS:
        bus.subscribe(et, _make_broadcaster(et))

    # ─── HTML ─────────────────────────────────────────────────────────────────
    @app.get("/", response_class=HTMLResponse)
    async def index():
        tpl = os.path.join(os.path.dirname(__file__), "templates", "index.html")
        with open(tpl, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())

    # ─── Frame Synchronization ────────────────────────────────────────────────
    frame_ready_event = asyncio.Event()

    def _frame_ready_handler(payload):
        frame_ready_event.set()

    bus.subscribe("FRAME_READY", _frame_ready_handler)

    # ─── MJPEG Video Stream ───────────────────────────────────────────────
    @app.get("/video_feed")
    async def video_feed():
        """Stream MJPEG lấy JPEG từ CameraManager (sync), dùng asyncio.Event để chờ frame mới."""
        async def gen():
            while True:
                try:
                    await asyncio.wait_for(frame_ready_event.wait(), timeout=0.2)
                    frame_ready_event.clear()
                except asyncio.TimeoutError:
                    continue

                jpeg = camera.get_latest_jpeg()
                if jpeg:
                    yield (b"--frame\r\nContent-Type: image/jpeg\r\n\r\n"
                           + jpeg + b"\r\n")

        return StreamingResponse(gen(), media_type="multipart/x-mixed-replace; boundary=frame")

    # ─── WebSocket ────────────────────────────────────────────────────────────
    @app.websocket("/ws")
    async def ws_endpoint(ws: WebSocket):
        await ws.accept()
        logger.info("Client kết nối WebSocket")
        q = ws_manager.add()
        bus.dashboard_connected = True

        # Gửi trạng thái hiện tại cho client mới (tránh race condition)
        for cached_msg in _cached_state.values():
            try:
                await ws.send_text(cached_msg)
            except Exception:
                pass

        try:
            while True:
                # Chờ message từ queue và gửi; timeout để kiểm tra kết nối
                try:
                    msg = await asyncio.wait_for(q.get(), timeout=10.0)
                    await ws.send_text(msg)
                except asyncio.TimeoutError:
                    # Ping để giữ kết nối
                    await ws.send_text(json.dumps({"type": "ping"}))
        except (WebSocketDisconnect, Exception):
            pass
        finally:
            ws_manager.remove(q)
            if len(ws_manager._queues) == 0:
                bus.dashboard_connected = False
            logger.info("Client ngắt kết nối WebSocket")

    return app


async def start_dashboard_server(bus: EventBus, camera: CameraManager, host: str, port: int):
    bus.dashboard_connected = False
    # pyrefly: ignore [missing-import]
    import uvicorn
    import socket
    app = create_app(bus, camera)
    config = uvicorn.Config(app, host=host, port=port, log_level="warning",
                            loop="asyncio", access_log=False)
    # Patch socket để SO_REUSEADDR — cho phép restart ngay mà không cần chờ TIME_WAIT
    server = uvicorn.Server(config)
    server.config.socket_opts = [(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)]
    await server.serve()
