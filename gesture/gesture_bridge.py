"""
gesture/gesture_bridge.py — Cầu nối Gesture Control → EventBus → ActionQueue
=============================================================================
Adapter chuyển lệnh từ cam_control.py (dùng Queue) sang EventBus
để tích hợp vào kiến trúc async của main.py.

Luồng dữ liệu:
  cam_control.py → cmd_queue.put(priority, seq, src, method, params)
                        → GestureQueueAdapter (thread đọc queue)
                            → EventBus.emit("GESTURE_COMMAND", {...})
                                → RobotActionEngine.handle_gesture_command()
                                    → ActionQueue → Robot
"""
import queue
import threading
from logs.logger import get_logger

logger = get_logger(__name__)


class _GestureQueueAdapter:
    """
    Giả lập một Queue để cam_control.py có thể gọi .put() bình thường.
    Đồng thời có thuộc tính shutdown_requested để dừng vòng lặp cam_control.
    voice_is_busy để cam_control tự nhường lệnh cho voice.
    """

    def __init__(self, event_bus, action_queue=None):
        self._bus = event_bus
        self._action_queue = action_queue
        self._q: queue.Queue = queue.Queue()
        self.shutdown_requested: bool = False
        self.voice_is_busy: bool = False

    def put(self, item, block=True, timeout=None):
        """cam_control gọi put((priority, seq, src, method, params))."""
        self._q.put(item)

    def _dispatch_loop(self):
        """Chạy trên thread riêng, đọc queue và phát EventBus."""
        while not self.shutdown_requested:
            try:
                item = self._q.get(timeout=0.2)
            except queue.Empty:
                continue

            try:
                # Format: (priority, seq, src, method, params_dict)
                if len(item) == 5:
                    priority, seq, src, method, params = item
                    logger.debug(f"[GESTURE] dispatch: method={method} params={params}")
                    self._bus.emit("GESTURE_COMMAND", {
                        "action": method,
                        "data": params,
                        "source": src,
                        "priority": priority,
                    })
                else:
                    logger.warning(f"[GESTURE] Unexpected queue item: {item}")
            except Exception as e:
                logger.error(f"[GESTURE] dispatch error: {e}")


class GestureBridge:
    """
    Quản lý luồng Gesture Control và cầu nối lệnh cử chỉ → EventBus.

    Sử dụng:
        bridge = GestureBridge(event_bus, action_queue=..., camera_index=1)
        bridge.start()     # Bắt đầu nhận diện cử chỉ trên thread riêng
        bridge.stop()      # Dừng
    """

    def __init__(self, event_bus, action_queue=None, camera_index=1):
        self._bus = event_bus
        self._action_queue = action_queue
        self._camera_index = camera_index
        self._adapter = _GestureQueueAdapter(event_bus, action_queue)
        self._gesture_thread: threading.Thread | None = None
        self._dispatch_thread: threading.Thread | None = None
        self._running = False

    # ── Lifecycle ────────────────────────────────────────────────────

    def start(self):
        """Khởi động luồng Gesture Control ở background."""
        if self._running:
            logger.warning("[GESTURE] Đã đang chạy, bỏ qua start().")
            return
        self._adapter.shutdown_requested = False

        # Thread 1: đọc queue và phát EventBus
        self._dispatch_thread = threading.Thread(
            target=self._adapter._dispatch_loop,
            name="GestureDispatcher",
            daemon=True,
        )
        self._dispatch_thread.start()

        # Thread 2: chạy vòng lặp camera + gesture
        self._gesture_thread = threading.Thread(
            target=self._run_gesture_loop,
            name="GestureController",
            daemon=True,
        )
        self._gesture_thread.start()
        self._running = True
        logger.info("[GESTURE] ✅ Luồng nhận diện cử chỉ đã khởi động.")
        self._bus.emit("GESTURE_STATUS", {"status": "started"})

    def stop(self):
        """Dừng luồng Gesture Control (graceful shutdown)."""
        self._adapter.shutdown_requested = True
        self._running = False
        if self._gesture_thread and self._gesture_thread.is_alive():
            self._gesture_thread.join(timeout=5)
        if self._dispatch_thread and self._dispatch_thread.is_alive():
            self._dispatch_thread.join(timeout=2)
        logger.info("[GESTURE] ⏹️ Luồng nhận diện cử chỉ đã dừng.")
        self._bus.emit("GESTURE_STATUS", {"status": "stopped"})

    @property
    def is_running(self) -> bool:
        return self._running and self._gesture_thread is not None and self._gesture_thread.is_alive()

    # ── Internal ─────────────────────────────────────────────────────

    def _run_gesture_loop(self):
        """Import và chạy cam_control trên thread riêng."""
        try:
            from gesture.cam_control import start_cam_control
        except ImportError as e:
            logger.error(f"[GESTURE] ❌ Không thể import gesture.cam_control: {e}")
            logger.error("[GESTURE] Đảm bảo đã cài: pip install mediapipe opencv-python Pillow")
            self._bus.emit("GESTURE_STATUS", {
                "status": "error",
                "message": f"Import error: {e}",
            })
            self._running = False
            return

        logger.info(f"[GESTURE] Camera index = {self._camera_index}")

        # Gọi đúng signature: start_cam_control(cmd_queue=None)
        start_cam_control(cmd_queue=self._adapter)

        self._running = False
        logger.info("[GESTURE] Vòng lặp gesture đã kết thúc.")

    def set_voice_busy(self, busy: bool):
        """Cho cam_control biết voice đang độc chiếm để tự nhường lệnh."""
        self._adapter.voice_is_busy = busy
