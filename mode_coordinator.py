"""
mode_coordinator.py — Bộ điều phối chế độ tập trung (ModeCoordinator)

Quản lý việc chuyển đổi giữa các chế độ FACE / GESTURE / AI.
Cả CLI và Dashboard đều gọi qua service này — đảm bảo dùng chung
logic, lock, và trạng thái.
"""
import asyncio
import time
from typing import Callable, Optional, Literal

from logs.logger import get_logger

logger = get_logger(__name__)

ModeType = Literal["face", "gesture", "ai", "idle"]

# Trạng thái chuyển đổi
TRANSITION_TIMEOUT = 15.0  # giây


class ModeCoordinator:
    """
    Central service quản lý chế độ hoạt động của hệ thống.
    Cả CLI thread và Dashboard API đều gọi set_mode() thông qua service này.
    """

    def __init__(
        self,
        event_bus,
        camera,
        pipeline,
        robot_action,
        voice_controller,
        gesture_bridge_factory: Callable,
        ai_controller_factory: Callable,
        shutdown_event: asyncio.Event,
    ):
        self._bus = event_bus
        self._camera = camera
        self._pipeline = pipeline
        self._robot_action = robot_action
        self._voice_controller = voice_controller
        self._gesture_bridge_factory = gesture_bridge_factory
        self._ai_controller_factory = ai_controller_factory
        self._shutdown_event = shutdown_event

        # State
        self._current_mode: ModeType = "idle"
        self._transitioning: bool = False
        self._lock = asyncio.Lock()

        # Active sub-components (owned by coordinator)
        self._camera_task: Optional[asyncio.Task] = None
        self._gesture_bridge = None
        self._ai_controller = None

        # Transition log
        self._last_transition_time: float = 0
        self._last_error: Optional[str] = None

    # ── Public read-only properties ──────────────────────────────────

    @property
    def current_mode(self) -> ModeType:
        return self._current_mode

    @property
    def is_transitioning(self) -> bool:
        return self._transitioning

    @property
    def last_error(self) -> Optional[str]:
        return self._last_error

    def get_status(self) -> dict:
        """Trả về trạng thái hiện tại cho API / WebSocket."""
        return {
            "mode": self._current_mode,
            "transitioning": self._transitioning,
            "last_error": self._last_error,
            "camera_running": self._camera_task is not None and not self._camera_task.done(),
            "gesture_running": self._gesture_bridge is not None and getattr(self._gesture_bridge, "is_running", False),
            "ai_running": self._ai_controller is not None and getattr(self._ai_controller, "is_running", False),
            "voice_running": self._voice_controller is not None and getattr(self._voice_controller, "is_running", False),
        }

    # ── Core: set_mode ───────────────────────────────────────────────

    async def set_mode(self, target: str) -> dict:
        """
        Chuyển sang chế độ mới. Thread-safe nhờ asyncio.Lock.
        Returns dict {"success": bool, "mode": str, "error": str|None}
        """
        target = target.strip().lower()

        # Normalize aliases
        alias_map = {"1": "face", "2": "gesture", "3": "ai", "chat": "ai", "gemini": "ai"}
        target = alias_map.get(target, target)

        if target not in ("face", "gesture", "ai"):
            return {"success": False, "mode": self._current_mode, "error": f"Unknown mode: {target}"}

        # Nếu đang chuyển đổi → từ chối
        if self._transitioning:
            return {"success": False, "mode": self._current_mode, "error": "Hệ thống đang chuyển chế độ. Vui lòng đợi."}

        # Đã ở chế độ này rồi
        if target == self._current_mode:
            # Double-check thực sự đang chạy
            if target == "face" and self._camera_task and not self._camera_task.done():
                return {"success": True, "mode": self._current_mode, "error": None}
            if target == "gesture" and self._gesture_bridge and getattr(self._gesture_bridge, "is_running", False):
                return {"success": True, "mode": self._current_mode, "error": None}
            if target == "ai" and self._ai_controller and getattr(self._ai_controller, "is_running", False):
                return {"success": True, "mode": self._current_mode, "error": None}

        async with self._lock:
            self._transitioning = True
            self._last_error = None
            previous_mode = self._current_mode
            self._broadcast_mode_event("MODE_CHANGING", {"from": previous_mode, "to": target})

            async def _do_transition():
                # ── Dừng chế độ cũ ─────────────────────────────────
                await self._stop_current_mode()

                # ── Khởi động chế độ mới ───────────────────────────
                if target == "face":
                    await self._start_face()
                elif target == "gesture":
                    await self._start_gesture()
                elif target == "ai":
                    await self._start_ai()

                self._current_mode = target
                self._last_transition_time = time.time()
                logger.info(f"✅ Chuyển chế độ thành công: {previous_mode} → {target}")
                self._broadcast_mode_event("MODE_CHANGED", {"mode": target, "previous": previous_mode})

            try:
                await asyncio.wait_for(_do_transition(), timeout=TRANSITION_TIMEOUT)
                return {"success": True, "mode": target, "error": None}

            except asyncio.TimeoutError:
                err_msg = f"Quá thời gian chuyển đổi ({TRANSITION_TIMEOUT}s): {previous_mode} → {target}"
                logger.error(err_msg)
                self._last_error = err_msg
                self._current_mode = "idle"
                self._broadcast_mode_event("MODE_ERROR", {"error": err_msg, "from": previous_mode, "to": target})
                try:
                    await self._stop_current_mode()
                except Exception:
                    pass
                return {"success": False, "mode": "idle", "error": err_msg}

            except Exception as e:
                err_msg = f"Lỗi chuyển chế độ {previous_mode}→{target}: {e}"
                logger.error(err_msg)
                self._last_error = err_msg
                self._current_mode = "idle"
                self._broadcast_mode_event("MODE_ERROR", {"error": err_msg, "from": previous_mode, "to": target})

                # Cố gắng phục hồi về trạng thái an toàn
                try:
                    await self._stop_current_mode()
                except Exception:
                    pass

                return {"success": False, "mode": "idle", "error": err_msg}

            finally:
                self._transitioning = False

    # ── Shutdown ─────────────────────────────────────────────────────

    async def shutdown(self) -> dict:
        """Dừng toàn bộ hệ thống qua Dashboard."""
        logger.info("🛑 Shutdown requested via ModeCoordinator")
        try:
            await self._stop_current_mode()
            self._current_mode = "idle"
        except Exception as e:
            logger.error(f"Error during mode shutdown: {e}")

        self._shutdown_event.set()
        return {"success": True, "message": "Shutdown initiated"}

    # ── Internal: stop current mode ──────────────────────────────────

    async def _stop_current_mode(self):
        """Dừng tất cả component đang chạy của chế độ hiện tại."""
        # Nếu đang ở Face mode, phát FACE_LOST + dọn tracks trước khi dừng
        if self._current_mode == "face":
            try:
                if hasattr(self._pipeline, 'tracks'):
                    self._pipeline.tracks.clear()
                self._bus.emit("FACE_LOST", {})
            except Exception as e:
                logger.warning(f"Lỗi dọn face tracks: {e}")

        # Dừng Gesture
        if self._gesture_bridge:
            try:
                self._gesture_bridge.stop()
            except Exception as e:
                logger.warning(f"Lỗi dừng GestureBridge: {e}")
            self._gesture_bridge = None
            await asyncio.sleep(0.5)

        # Dừng AI
        if self._ai_controller:
            try:
                self._ai_controller.stop()
            except Exception as e:
                logger.warning(f"Lỗi dừng GeminiAIController: {e}")
            self._ai_controller = None
            await asyncio.sleep(0.5)

        # Dừng Face Camera
        if self._camera_task and not self._camera_task.done():
            self._camera.stop()
            self._camera_task.cancel()
            try:
                await self._camera_task
            except asyncio.CancelledError:
                pass
            self._camera_task = None
            await asyncio.sleep(0.3)
        else:
            self._camera.stop()
            self._camera_task = None

    # ── Internal: start face mode ────────────────────────────────────

    async def _start_face(self):
        """Khởi động Face Recognition mode."""
        # Dọn dẹp tracks cũ
        if hasattr(self._pipeline, 'tracks'):
            self._pipeline.tracks.clear()
        self._bus.emit("FACE_LOST", {})

        # Bật lại voice controller thường nếu có
        if self._voice_controller and not getattr(self._voice_controller, "is_running", False):
            self._voice_controller.start()

        # Khởi động Camera
        self._camera_task = asyncio.create_task(self._camera.run())
        logger.info("📷 Face mode: Camera + Recognition Pipeline started")

    # ── Internal: start gesture mode ─────────────────────────────────

    async def _start_gesture(self):
        """Khởi động Gesture Recognition mode."""
        await asyncio.sleep(0.5)  # đợi camera nhả resource

        # Đảm bảo Voice recognition luôn chạy ở Gesture mode (chỉ tắt ở AI mode)
        if self._voice_controller and not getattr(self._voice_controller, "is_running", False):
            self._voice_controller.start()

        self._gesture_bridge = self._gesture_bridge_factory()
        self._gesture_bridge.start()
        logger.info("🖐️ Gesture mode: GestureBridge started")

    # ── Internal: start AI mode ──────────────────────────────────────

    async def _start_ai(self):
        """Khởi động Gemini AI mode."""
        # Dừng Voice thường để Gemini AI độc chiếm Micro
        if self._voice_controller and getattr(self._voice_controller, "is_running", False):
            self._voice_controller.stop()

        await asyncio.sleep(0.3)

        self._ai_controller = self._ai_controller_factory()
        self._ai_controller.start()
        logger.info("🧠 AI mode: GeminiAIController started")

    # ── Internal: broadcast event ────────────────────────────────────

    def _broadcast_mode_event(self, event_type: str, payload: dict):
        """Phát sự kiện qua EventBus để Dashboard/WebSocket nhận."""
        try:
            self._bus.emit(event_type, payload)
        except Exception as e:
            logger.warning(f"Lỗi emit {event_type}: {e}")
