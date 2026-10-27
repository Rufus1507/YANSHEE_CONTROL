"""
action_queue.py — Hàng đợi hành động có ưu tiên (Priority Action Queue).

GIẢI QUYẾT THÁCH THỨC #2 (Xung đột điều khiển robot):
Khi Camera nhận diện mặt (→ Robot chào) ĐỒNG THỜI người dùng ra lệnh
giọng nói (→ Robot đi thẳng), hai lệnh sẽ KHÔNG đâm nhau nữa.

Cơ chế:
1. Mọi hành động robot (greeting, voice command, TTS) đều được đưa vào queue.
2. Queue xử lý tuần tự (FIFO), đảm bảo chỉ 1 action chạy tại 1 thời điểm.
3. Hỗ trợ priority: lệnh giọng nói (VOICE) > lời chào (GREETING).
   Khi có lệnh voice ưu tiên cao, nó có thể hủy lệnh greeting đang chạy.
4. Mỗi action có timeout tránh kẹt robot vĩnh viễn.
"""
import asyncio
import enum
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Coroutine
from logs.logger import get_logger

logger = get_logger(__name__)


class ActionPriority(enum.IntEnum):
    """Độ ưu tiên hành động. Số nhỏ = ưu tiên cao."""
    EMERGENCY = 0   # Dừng khẩn cấp (Stop)
    VOICE = 10      # Lệnh giọng nói trực tiếp
    GESTURE = 15    # Lệnh cử chỉ tay/pose (thấp hơn voice, cao hơn greeting)
    GREETING = 20   # Chào khi nhận diện khuôn mặt
    LIVENESS = 25   # Phản hồi liveness (nói hướng dẫn)
    TTS = 30        # Phát TTS tiếng Việt
    RESET = 40      # Reset về vị trí ban đầu
    LOW = 50        # Các hành động ít quan trọng


@dataclass(order=True)
class RobotAction:
    """Một hành động trong hàng đợi."""
    priority: int
    created_at: float = field(compare=False, default_factory=time.time)
    name: str = field(compare=False, default="")
    coro_factory: Callable[[], Coroutine] | None = field(
        compare=False, default=None, repr=False
    )
    metadata: dict[str, Any] = field(compare=False, default_factory=dict)
    timeout: float = field(compare=False, default=30.0)

    # Cho phép hủy action đang chạy nếu action mới ưu tiên hơn?
    cancellable: bool = field(compare=False, default=True)


class ActionQueue:
    """
    Hàng đợi hành động tuần tự có ưu tiên cho robot.

    Sử dụng:
        queue = ActionQueue(event_bus)
        await queue.start()

        # Thêm hành động từ bất kỳ đâu (thread-safe thông qua EventBus)
        queue.enqueue(RobotAction(
            priority=ActionPriority.VOICE,
            name="forward",
            coro_factory=lambda: robot_conn.send_motion("Forward"),
        ))
    """

    def __init__(self, event_bus=None, max_size: int = 20):
        self._bus = event_bus
        self._queue: asyncio.PriorityQueue = asyncio.PriorityQueue(maxsize=max_size)
        self._current_task: asyncio.Task | None = None
        self._current_action: RobotAction | None = None
        self._running = False
        self._worker_task: asyncio.Task | None = None

    async def start(self):
        """Khởi động worker xử lý hàng đợi."""
        if self._running:
            return
        self._running = True
        self._worker_task = asyncio.create_task(self._worker())
        logger.info("[ACTION-QUEUE] ✅ Worker đã khởi động")

    async def stop(self):
        """Dừng worker."""
        self._running = False
        if self._current_task and not self._current_task.done():
            self._current_task.cancel()
        if self._worker_task and not self._worker_task.done():
            self._worker_task.cancel()
        logger.info("[ACTION-QUEUE] ⏹️ Worker đã dừng")

    def enqueue(self, action: RobotAction):
        """
        Thêm hành động vào hàng đợi.
        Nếu action ưu tiên cao hơn action đang chạy VÀ action đang chạy
        là cancellable → hủy action đang chạy.
        """
        try:
            self._queue.put_nowait(action)
            logger.info(f"[ACTION-QUEUE] + Enqueued: {action.name} "
                        f"(priority={action.priority}, queue_size={self._queue.qsize()})")
        except asyncio.QueueFull:
            logger.warning(f"[ACTION-QUEUE] ⚠️ Queue đầy, bỏ: {action.name}")
            return

        # Pre-emption: hủy action hiện tại nếu action mới ưu tiên cao hơn
        if (self._current_action
                and self._current_action.cancellable
                and action.priority < self._current_action.priority
                and self._current_task
                and not self._current_task.done()):
            logger.info(
                f"[ACTION-QUEUE] ⚡ Pre-empt: hủy '{self._current_action.name}' "
                f"(p={self._current_action.priority}) cho '{action.name}' "
                f"(p={action.priority})"
            )
            self._current_task.cancel()

        if self._bus:
            self._bus.emit("ACTION_QUEUE_UPDATE", {
                "queue_size": self._queue.qsize(),
                "current": self._current_action.name if self._current_action else None,
                "enqueued": action.name,
            })

    def clear(self):
        """Xóa toàn bộ hàng đợi (giữ nguyên action đang chạy)."""
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
            except asyncio.QueueEmpty:
                break
        logger.info("[ACTION-QUEUE] 🗑️ Đã xóa toàn bộ hàng đợi")

    @property
    def is_busy(self) -> bool:
        return self._current_action is not None

    @property
    def queue_size(self) -> int:
        return self._queue.qsize()

    # ── Worker chính ─────────────────────────────────────────────────
    async def _worker(self):
        """Vòng lặp worker: lấy action từ queue và thực thi tuần tự."""
        while self._running:
            try:
                action = await asyncio.wait_for(self._queue.get(), timeout=1.0)
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break

            self._current_action = action
            logger.info(f"[ACTION-QUEUE] ▶ Executing: {action.name} (p={action.priority})")

            if self._bus:
                self._bus.emit("ACTION_EXECUTING", {
                    "name": action.name,
                    "priority": action.priority,
                    "metadata": action.metadata,
                })

            try:
                if action.coro_factory:
                    coro = action.coro_factory()
                    self._current_task = asyncio.create_task(coro)
                    await asyncio.wait_for(
                        asyncio.shield(self._current_task),
                        timeout=action.timeout,
                    )

                logger.info(f"[ACTION-QUEUE] ✅ Completed: {action.name}")
                if self._bus:
                    self._bus.emit("ACTION_COMPLETED", {
                        "name": action.name,
                        "metadata": action.metadata,
                    })

            except asyncio.TimeoutError:
                logger.warning(f"[ACTION-QUEUE] ⏰ Timeout: {action.name} "
                               f"(>{action.timeout}s)")
                if self._current_task and not self._current_task.done():
                    self._current_task.cancel()

            except asyncio.CancelledError:
                logger.info(f"[ACTION-QUEUE] 🚫 Cancelled: {action.name}")

            except Exception as e:
                logger.exception(f"[ACTION-QUEUE] ❌ Error in {action.name}: {e}")

            finally:
                self._current_action = None
                self._current_task = None

        logger.info("[ACTION-QUEUE] Worker loop ended.")
