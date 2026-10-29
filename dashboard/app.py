"""
FastAPI Dashboard — MJPEG video stream + WebSocket event relay + REST API controls.

THIẾT KẾ HIỆU NĂNG:
- MJPEG stream: đọc JPEG đã được encode sẵn từ CameraManager (không encode lại),
  dùng threading.Event để wake-up ngay khi có frame mới.
- WebSocket: broadcast các sự kiện qua asyncio.Queue per-connection.
  Không dùng asyncio.ensure_future per-event để tránh task explosion.

API ENDPOINTS (Dashboard điều khiển):
- GET  /api/status         → trạng thái hệ thống (mode, camera, robot, voice, queue, memory)
- POST /api/mode           → chuyển chế độ {"mode": "face"|"gesture"|"ai"}
- POST /api/shutdown       → dừng toàn bộ hệ thống an toàn
- POST /api/robot/motion   → gửi lệnh cử động robot qua ActionQueue
- POST /api/tts            → phát câu thoại tiếng Việt (gTTS/robot/local)
- POST /api/voice/toggle   → bật/tắt luồng nhận diện giọng nói
- GET  /api/memory         → lấy thống kê và danh sách cử động trong bộ nhớ
- POST /api/memory/learn   → dạy từ khóa mới cho một cử động
"""
import os
import json
import asyncio
from typing import Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse
from pydantic import BaseModel

from events.event_bus import EventBus
from camera.camera_manager import CameraManager
from logs.logger import get_logger

logger = get_logger(__name__)

_FORWARD_EVENTS = [
    # Face & Detection
    "FACE_DETECTED", "FACE_LOST", "FACE_QUALITY_POOR", "INSUFFICIENT_VISUAL_INFORMATION",
    "LIVENESS_STARTED", "LIVENESS_PASSED", "LIVENESS_FAILED", "LIVENESS_PROGRESS",
    "USER_RECOGNIZED", "USER_VERIFIED", "UNKNOWN_USER", "LOW_CONFIDENCE",
    # Robot Lifecycle & Execution
    "ROBOT_STATUS", "ROBOT_ACTION_STARTED", "ROBOT_ACTION_FAILED", "ROBOT_ACTION_SKIPPED",
    "ROBOT_SPEAKING_STARTED", "ROBOT_SPEAKING_FINISHED", "ROBOT_GREETING_STARTED", 
    "ROBOT_GREETING_FINISHED", "ROBOT_RESET_WAITING", "ROBOT_RESET_STARTED", "ROBOT_RESET_FINISHED", "ROBOT_READY",
    # Camera
    "CAMERA_STATUS", "CAMERA_CONNECTED", "CAMERA_RECONNECTING", "CAMERA_DISCONNECTED", "CAMERA_ERROR", "CAMERA_STOPPED",
    # System & Metrics
    "SYSTEM_ERROR", "SYSTEM_METRICS", "FRAME_READY", "PERFORMANCE_METRICS", "PIPELINE_METRICS",
    # Voice Control
    "VOICE_STATUS", "VOICE_RECOGNIZED", "VOICE_COMMAND", "VOICE_UNKNOWN_WORD",
    "VOICE_EXECUTING", "VOICE_COMMAND_SUCCESS", "VOICE_COMMAND_FAILED",
    # Smart Memory
    "MEMORY_UPDATED",
    # Vietnamese TTS
    "TTS_STARTED", "TTS_FINISHED",
    # Action Queue
    "ACTION_QUEUE_UPDATE", "ACTION_EXECUTING", "ACTION_COMPLETED",
    # Gesture
    "GESTURE_STATUS", "GESTURE_COMMAND", "GESTURE_EXECUTING", "GESTURE_COMPLETED",
    # Mode switching (from ModeCoordinator)
    "MODE_CHANGING", "MODE_CHANGED", "MODE_ERROR",
    # Gemini AI
    "GEMINI_AI_STATUS", "GEMINI_AI_REPLY",
]


# ── Pydantic Request Models ──────────────────────────────────────────

class ModeRequest(BaseModel):
    mode: str

class MotionRequest(BaseModel):
    motion: str

class TTSRequest(BaseModel):
    text: str

class LearnRequest(BaseModel):
    motion: str
    keyword: str


class _WSManager:
    """Quản lý nhiều WebSocket connections và broadcast message."""

    def __init__(self):
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


def create_app(
    bus: EventBus,
    camera: CameraManager,
    mode_coordinator,
    robot_action=None,
    robot_conn=None,
    voice_controller=None,
    robot_memory=None,
) -> FastAPI:
    """Create FastAPI app with real backend services injected."""

    app = FastAPI(title="Yanshee AI Control Center")
    static_dir = os.path.join(os.path.dirname(__file__), "static")
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

    ws_manager = _WSManager()

    # ─── Cache trạng thái mới nhất để gửi cho client mới kết nối ────────────
    _cached_state: dict[str, str] = {}  # event_type -> json string
    _CACHEABLE_EVENTS = {"ROBOT_STATUS", "CAMERA_STATUS", "MODE_CHANGED", "VOICE_STATUS"}

    def _make_broadcaster(event_type: str):
        def handler(payload: dict):
            if event_type == "FRAME_READY":
                cam_info = {
                    "fps": payload.get("fps", getattr(camera, "fps", 0.0)),
                    "latency_ms": getattr(camera, "latency", 0.0),
                    "source": "yanshee" if getattr(camera, "running", False) else "stopped",
                }
                data = json.dumps({"type": "FRAME_READY", "payload": cam_info})
            else:
                try:
                    data = json.dumps({"type": event_type, "payload": payload})
                except (TypeError, ValueError):
                    return
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
                    await asyncio.wait_for(frame_ready_event.wait(), timeout=0.5)
                    frame_ready_event.clear()
                    jpeg = camera.get_latest_jpeg()
                    if jpeg:
                        yield (b"--frame\r\nContent-Type: image/jpeg\r\n\r\n"
                               + jpeg + b"\r\n")
                except asyncio.TimeoutError:
                    curr_mode = getattr(mode_coordinator, "current_mode", "")
                    if not getattr(camera, "running", False) and curr_mode not in ("face", "gesture"):
                        await asyncio.sleep(0.3)
                    continue

        return StreamingResponse(gen(), media_type="multipart/x-mixed-replace; boundary=frame")

    # ═════════════════════════════════════════════════════════════════
    # REST API — Điều khiển hệ thống từ Dashboard
    # ═════════════════════════════════════════════════════════════════

    @app.get("/api/status")
    async def api_status():
        """Trả về trạng thái tổng thể hệ thống (Real State)."""
        status = mode_coordinator.get_status()
        status.update({
            "robot_connected": getattr(robot_conn, "connected", False),
            "robot_state": getattr(robot_action, "state", "UNKNOWN"),
            "action_queue_size": getattr(robot_action.action_queue, "queue_size", 0) if (robot_action and hasattr(robot_action, "action_queue")) else 0,
            "voice_running": getattr(voice_controller, "is_running", False),
            "memory_stats": robot_memory.get_stats() if robot_memory else {},
            "camera_running": getattr(camera, "running", False) or status.get("gesture_running", False),
            "camera_fps": getattr(camera, "fps", 0.0),
        })
        return JSONResponse(content=status)

    @app.post("/api/mode")
    async def api_set_mode(req: ModeRequest):
        """Chuyển chế độ hoạt động: face / gesture / ai."""
        result = await mode_coordinator.set_mode(req.mode)
        status_code = 200 if result.get("success") else 409
        return JSONResponse(content=result, status_code=status_code)

    @app.post("/api/shutdown")
    async def api_shutdown():
        """Dừng toàn bộ hệ thống an toàn từ Dashboard."""
        result = await mode_coordinator.shutdown()
        return JSONResponse(content=result)

    @app.post("/api/robot/motion")
    async def api_robot_motion(req: MotionRequest):
        """Gửi lệnh chuyển động tới robot qua ActionQueue."""
        if not robot_action:
            return JSONResponse(content={"success": False, "error": "Robot action engine not available"}, status_code=503)
        if not robot_conn or not getattr(robot_conn, "connected", False):
            return JSONResponse(content={"success": False, "error": "Robot đang offline. Không thể gửi cử động."}, status_code=400)

        motion = req.motion.strip()
        if not motion:
            return JSONResponse(content={"success": False, "error": "Tên motion không được rỗng"}, status_code=400)

        bus.emit("VOICE_COMMAND", {
            "motion": motion,
            "raw_text": f"web:{motion}",
            "source": "dashboard",
        })
        return JSONResponse(content={"success": True, "motion": motion, "message": f"Đã đưa {motion} vào ActionQueue"})

    @app.post("/api/tts")
    async def api_tts(req: TTSRequest):
        """Phát âm tiếng Việt qua TTS."""
        text = req.text.strip()
        if not text:
            return JSONResponse(content={"success": False, "error": "Nội dung TTS không được rỗng"}, status_code=400)

        bus.emit("TTS_REQUEST", {"text": text, "source": "dashboard"})
        return JSONResponse(content={"success": True, "text": text, "message": "Đang phát âm qua hệ thống TTS..."})

    @app.post("/api/voice/toggle")
    async def api_voice_toggle():
        """Bật/tắt lắng nghe giọng nói."""
        if not voice_controller:
            return JSONResponse(content={"success": False, "error": "Voice controller không khả dụng"}, status_code=503)

        if voice_controller.is_running:
            voice_controller.stop()
            running = False
        else:
            voice_controller.start()
            running = True
        return JSONResponse(content={"success": True, "running": running})

    @app.get("/api/memory")
    async def api_get_memory():
        """Lấy danh sách các motions và thống kê smart memory."""
        if not robot_memory:
            return JSONResponse(content={"success": False, "error": "Robot memory không khả dụng"}, status_code=503)
        stats = robot_memory.get_stats()
        motions = robot_memory.get_all_motions()
        return JSONResponse(content={"success": True, "stats": stats, "motions": motions})

    @app.post("/api/memory/learn")
    async def api_memory_learn(req: LearnRequest):
        """Dạy robot từ khóa mới cho hành động."""
        if not robot_memory:
            return JSONResponse(content={"success": False, "error": "Robot memory không khả dụng"}, status_code=503)
        motion = req.motion.strip()
        keyword = req.keyword.strip()
        if not motion or not keyword:
            return JSONResponse(content={"success": False, "error": "Motion và Keyword không được để trống"}, status_code=400)

        success = robot_memory.learn_keyword(motion, keyword)
        if success:
            return JSONResponse(content={"success": True, "motion": motion, "keyword": keyword})
        else:
            return JSONResponse(content={"success": False, "error": f"Hành động '{motion}' không tồn tại trong từ điển"}, status_code=404)

    # ─── WebSocket ────────────────────────────────────────────────────────────
    @app.websocket("/ws")
    async def ws_endpoint(ws: WebSocket):
        await ws.accept()
        logger.info("Client kết nối WebSocket")
        q = ws_manager.add()
        bus.dashboard_connected = True

        # Gửi trạng thái hiện tại cho client mới
        for cached_msg in _cached_state.values():
            try:
                await ws.send_text(cached_msg)
            except Exception:
                pass

        # Gửi mode hiện tại
        try:
            mode_status = mode_coordinator.get_status()
            await ws.send_text(json.dumps({"type": "MODE_CHANGED", "payload": {"mode": mode_status["mode"]}}))
        except Exception:
            pass

        try:
            while True:
                try:
                    msg = await asyncio.wait_for(q.get(), timeout=10.0)
                    await ws.send_text(msg)
                except asyncio.TimeoutError:
                    await ws.send_text(json.dumps({"type": "ping"}))
        except (WebSocketDisconnect, Exception, asyncio.CancelledError):
            pass
        finally:
            ws_manager.remove(q)
            if len(ws_manager._queues) == 0:
                bus.dashboard_connected = False
            logger.info("Client ngắt kết nối WebSocket")

    return app


async def start_dashboard_server(
    bus: EventBus,
    camera: CameraManager,
    mode_coordinator,
    host: str,
    port: int,
    robot_action=None,
    robot_conn=None,
    voice_controller=None,
    robot_memory=None,
    shutdown_event: asyncio.Event = None,
):
    bus.dashboard_connected = False
    import uvicorn
    import socket
    app = create_app(
        bus=bus,
        camera=camera,
        mode_coordinator=mode_coordinator,
        robot_action=robot_action,
        robot_conn=robot_conn,
        voice_controller=voice_controller,
        robot_memory=robot_memory,
    )
    config = uvicorn.Config(app, host=host, port=port, log_level="warning",
                            loop="asyncio", access_log=False)
    server = uvicorn.Server(config)
    server.config.socket_opts = [(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)]

    if shutdown_event:
        async def watch_shutdown():
            await shutdown_event.wait()
            server.should_exit = True
        asyncio.create_task(watch_shutdown())

    try:
        await server.serve()
    except asyncio.CancelledError:
        pass
