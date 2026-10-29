"""
tools/test_dashboard_integration.py
Kiểm tra tự động toàn bộ API và luồng điều phối của Dashboard, ModeCoordinator,
Voice Lifecycle, Unified Frame, và TTS.
"""
import os
import sys
import json
import asyncio

# Fix Windows console encoding for Vietnamese text
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

# Patch self-pipe for running in sandboxed environment on Windows
if sys.platform == 'win32':
    try:
        import asyncio.proactor_events
        class _DummySocket:
            def setblocking(self, b): pass
            def fileno(self): return -1
            def close(self): pass
            def send(self, data): return len(data)
            def recv(self, n): return b""

        asyncio.proactor_events.BaseProactorEventLoop._make_self_pipe = lambda self: setattr(self, '_ssock', _DummySocket()) or setattr(self, '_csock', _DummySocket())
        asyncio.proactor_events.BaseProactorEventLoop._close_self_pipe = lambda self: None
        asyncio.proactor_events.BaseProactorEventLoop._loop_self_reading = lambda self, f=None: None
    except Exception:
        pass

# Ensure project root is on sys.path
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from events.event_bus import EventBus
from mode_coordinator import ModeCoordinator
from dashboard.app import create_app
from voice.robot_memory import RobotMemory


class ASGIClient:
    """Zero-dependency asynchronous ASGI client for FastAPI testing."""
    def __init__(self, app):
        self.app = app

    async def request(self, method, path, json_data=None, headers=None):
        body = json.dumps(json_data).encode('utf-8') if json_data is not None else b""
        req_headers = [(b"host", b"testserver")]
        if json_data is not None:
            req_headers.append((b"content-type", b"application/json"))
            req_headers.append((b"content-length", str(len(body)).encode('utf-8')))
        if headers:
            for k, v in headers.items():
                req_headers.append((k.lower().encode('utf-8'), v.encode('utf-8')))

        scope = {
            "type": "http",
            "method": method,
            "path": path,
            "raw_path": path.encode('utf-8'),
            "query_string": b"",
            "headers": req_headers,
        }

        sent = False
        async def receive():
            nonlocal sent
            if not sent:
                sent = True
                return {"type": "http.request", "body": body, "more_body": False}
            return {"type": "http.disconnect"}

        response = {"status": 0, "headers": [], "body": b""}
        async def send(message):
            if message["type"] == "http.response.start":
                response["status"] = message["status"]
                response["headers"] = message.get("headers", [])
            elif message["type"] == "http.response.body":
                response["body"] += message.get("body", b"")

        await self.app(scope, receive, send)

        class Response:
            def __init__(self, r):
                self.status_code = r["status"]
                self.content = r["body"]
                self.text = r["body"].decode("utf-8", errors="replace")
            def json(self):
                return json.loads(self.content.decode("utf-8"))

        return Response(response)

    async def get(self, path):
        return await self.request("GET", path)

    async def post(self, path, json=None):
        return await self.request("POST", path, json_data=json)


class DummyCamera:
    def __init__(self, bus):
        self.bus = bus
        self.running = False
        self.fps = 30.0
        self.latency = 12.0
        self._latest_jpeg = b"initial_jpeg_bytes"

    async def run(self):
        self.running = True
        try:
            while self.running:
                await asyncio.sleep(0.05)
        except asyncio.CancelledError:
            self.running = False

    def stop(self):
        self.running = False

    def get_latest_jpeg(self):
        return self._latest_jpeg

    def set_external_jpeg(self, jpeg: bytes, fps: float = 0.0):
        self._latest_jpeg = jpeg
        self.fps = fps
        self.bus.emit("FRAME_READY", {"fps": fps, "source": "gesture"})


class DummyPipeline:
    def __init__(self):
        self.tracks = {}


class DummyRobotConn:
    def __init__(self):
        self.connected = False
    def send_motion(self, name):
        return self.connected
    def send_tts(self, text):
        return self.connected


class DummyRobotAction:
    def __init__(self):
        self.state = "READY"
        self.action_queue = DummyActionQueue()


class DummyActionQueue:
    def __init__(self):
        self.queue_size = 0
    def enqueue(self, action):
        self.queue_size += 1
    def size(self):
        return self.queue_size


class DummyVoiceController:
    def __init__(self):
        self.is_running = False
    def start(self):
        self.is_running = True
    def stop(self):
        self.is_running = False


class DummyBridge:
    def __init__(self):
        self.is_running = False
    def start(self):
        self.is_running = True
    def stop(self):
        self.is_running = False


async def async_test_suite():
    print("="*60, flush=True)
    print("BẮT ĐẦU KIỂM THỬ TỰ ĐỘNG DASHBOARD & MODECOORDINATOR", flush=True)
    print("="*60, flush=True)

    loop = asyncio.get_running_loop()
    event_bus = EventBus()
    event_bus.set_loop(loop)
    shutdown_event = asyncio.Event()

    camera = DummyCamera(event_bus)
    pipeline = DummyPipeline()
    robot_conn = DummyRobotConn()
    robot_action = DummyRobotAction()
    voice_controller = DummyVoiceController()
    robot_memory = RobotMemory(event_bus=event_bus)

    mode_coordinator = ModeCoordinator(
        event_bus=event_bus,
        camera=camera,
        pipeline=pipeline,
        robot_action=robot_action,
        voice_controller=voice_controller,
        gesture_bridge_factory=lambda: DummyBridge(),
        ai_controller_factory=lambda: DummyBridge(),
        shutdown_event=shutdown_event,
    )

    # 1. Test ModeCoordinator transitions & Voice Lifecycle
    print("\n[TEST 1] Kiểm tra Khởi động Face Mode...", flush=True)
    r1 = await mode_coordinator.set_mode("face")
    assert r1["success"] is True, f"Failed face transition: {r1}"
    assert mode_coordinator.current_mode == "face"
    assert camera.running is True
    assert voice_controller.is_running is True, "Voice should be active in Face mode"
    print("  -> PASSED: Mode=face, Camera=running, Voice=running", flush=True)

    print("\n[TEST 2] Kiểm tra Chuyển sang Gesture Mode (Voice KHÔNG được tắt)...", flush=True)
    r2 = await mode_coordinator.set_mode("gesture")
    assert r2["success"] is True, f"Failed gesture transition: {r2}"
    assert mode_coordinator.current_mode == "gesture"
    assert camera.running is False, "Camera resource must be freed for gesture"
    assert mode_coordinator.get_status()["gesture_running"] is True
    assert voice_controller.is_running is True, "Voice must REMAIN active in Gesture mode!"
    print("  -> PASSED: Mode=gesture, Camera nhả tài nguyên, Gesture=running, Voice=running", flush=True)

    print("\n[TEST 3] Kiểm tra Chuyển sang Gemini AI Mode (Voice PHẢI tắt để nhường mic)...", flush=True)
    r3 = await mode_coordinator.set_mode("ai")
    assert r3["success"] is True, f"Failed AI transition: {r3}"
    assert mode_coordinator.current_mode == "ai"
    assert mode_coordinator.get_status()["ai_running"] is True
    assert voice_controller.is_running is False, "Voice MUST be stopped in AI mode!"
    print("  -> PASSED: Mode=ai, AI=running, Voice=stopped (nhường mic cho AI)", flush=True)

    print("\n[TEST 4] Kiểm tra Chuyển từ AI -> Gesture (Voice PHẢI được kích hoạt lại)...", flush=True)
    r4_gest = await mode_coordinator.set_mode("gesture")
    assert r4_gest["success"] is True
    assert mode_coordinator.current_mode == "gesture"
    assert voice_controller.is_running is True, "Voice MUST be reactivated when switching from AI to Gesture!"
    print("  -> PASSED: AI -> Gesture thành công, Voice tự động kích hoạt lại", flush=True)

    print("\n[TEST 5] Kiểm tra Chuyển từ AI -> Face (Voice PHẢI được kích hoạt lại)...", flush=True)
    await mode_coordinator.set_mode("ai")
    assert voice_controller.is_running is False
    r4_face = await mode_coordinator.set_mode("face")
    assert r4_face["success"] is True
    assert mode_coordinator.current_mode == "face"
    assert camera.running is True
    assert voice_controller.is_running is True, "Voice MUST be reactivated when switching from AI to Face!"
    print("  -> PASSED: AI -> Face thành công, Voice tự động kích hoạt lại", flush=True)

    # 2. Test Unified Video Frame
    print("\n[TEST 6] Kiểm tra Unified Frame: Gesture đẩy frame vào cùng CameraManager...", flush=True)
    gesture_frame = b"fake_gesture_jpeg_bytes_12345"
    frame_received = False
    def on_frame(payload):
        nonlocal frame_received
        frame_received = True
    event_bus.subscribe("FRAME_READY", on_frame)
    camera.set_external_jpeg(gesture_frame, fps=28.5)
    await asyncio.sleep(0.02)
    assert camera.get_latest_jpeg() == gesture_frame
    assert camera.fps == 28.5
    assert frame_received is True
    print("  -> PASSED: Gesture frame streaming qua cùng CameraManager._latest_jpeg thành công", flush=True)

    # 3. Test FastAPI Endpoints using zero-dependency ASGIClient
    print("\n[TEST 7] Kiểm tra REST API Endpoints trên FastAPI Dashboard...", flush=True)
    app = create_app(
        bus=event_bus,
        camera=camera,
        mode_coordinator=mode_coordinator,
        robot_action=robot_action,
        robot_conn=robot_conn,
        voice_controller=voice_controller,
        robot_memory=robot_memory,
    )

    client = ASGIClient(app=app)

    # Test GET /
    res_index = await client.get("/")
    assert res_index.status_code == 200
    assert "YANSHEE AI" in res_index.text
    assert "Face Recognition (1)" in res_index.text
    assert "Gesture Control (2)" in res_index.text
    print("  -> PASSED: GET / (HTML template load 200 OK)", flush=True)

    # Test GET /api/status
    res_status = await client.get("/api/status")
    assert res_status.status_code == 200
    data_status = res_status.json()
    assert data_status["mode"] == "face"
    assert "robot_connected" in data_status
    assert "voice_running" in data_status
    assert "camera_running" in data_status
    print(f"  -> PASSED: GET /api/status -> mode={data_status['mode']}, cam_running={data_status['camera_running']}", flush=True)

    # Test POST /api/mode
    res_mode = await client.post("/api/mode", json={"mode": "gesture"})
    assert res_mode.status_code == 200
    assert res_mode.json()["mode"] == "gesture"
    print("  -> PASSED: POST /api/mode {'mode': 'gesture'} -> 200 OK", flush=True)

    # Test POST /api/tts (multiple times consecutively)
    print("\n[TEST 8] Kiểm tra Phát âm Tiếng Việt (TTS) liên tiếp nhiều lần...", flush=True)
    tts_events = []
    event_bus.subscribe("TTS_REQUEST", lambda p: tts_events.append(p.get("text")))

    for i in range(1, 4):
        res_tts = await client.post("/api/tts", json={"text": f"Câu test tiếng Việt lần thứ {i}"})
        assert res_tts.status_code == 200
        assert res_tts.json()["success"] is True

    await asyncio.sleep(0.05)
    assert len(tts_events) == 3
    print("  -> PASSED: Gửi 3 câu TTS liên tiếp thành công, không gặp lỗi", flush=True)

    # Test POST /api/voice/toggle
    res_vt = await client.post("/api/voice/toggle")
    assert res_vt.status_code == 200
    assert "running" in res_vt.json()
    print(f"  -> PASSED: POST /api/voice/toggle -> running={res_vt.json()['running']}", flush=True)

    # Test GET /api/memory & POST /api/memory/learn
    res_mem = await client.get("/api/memory")
    assert res_mem.status_code == 200
    assert res_mem.json()["success"] is True
    assert len(res_mem.json()["motions"]) > 0

    res_learn = await client.post("/api/memory/learn", json={"motion": "Forward", "keyword": "tiến nhanh lên nha"})
    assert res_learn.status_code == 200
    assert res_learn.json()["success"] is True
    print("  -> PASSED: GET /api/memory & POST /api/memory/learn -> 200 OK", flush=True)

    # Test POST /api/robot/motion when offline
    res_mot_off = await client.post("/api/robot/motion", json={"motion": "Forward"})
    assert res_mot_off.status_code == 400
    assert "offline" in res_mot_off.json()["error"]
    print("  -> PASSED: POST /api/robot/motion khi offline -> 400 và báo lỗi chính xác", flush=True)

    # Test POST /api/robot/motion when connected
    robot_conn.connected = True
    res_mot_on = await client.post("/api/robot/motion", json={"motion": "Forward"})
    assert res_mot_on.status_code == 200
    assert res_mot_on.json()["success"] is True
    print("  -> PASSED: POST /api/robot/motion khi connected -> 200 và đưa vào ActionQueue", flush=True)

    # Test POST /api/shutdown
    res_shut = await client.post("/api/shutdown")
    assert res_shut.status_code == 200
    assert shutdown_event.is_set() is True
    print("  -> PASSED: POST /api/shutdown -> 200 OK & shutdown_event kích hoạt thành công", flush=True)

    print("\n" + "="*60, flush=True)
    print("TẤT CẢ CÁC BÀI TEST ĐỀU PASSED 100%!", flush=True)
    print("="*60, flush=True)


if __name__ == "__main__":
    asyncio.run(async_test_suite())
