import asyncio
from collections import defaultdict
from typing import Callable, Dict, List, Any
import logging

from logs.logger import get_logger

logger = get_logger(__name__)

class Event:
    def __init__(self, type: str, payload: Dict[str, Any]):
        self.type = type
        self.payload = payload

class EventBus:
    def __init__(self):
        self._subscribers: Dict[str, List[Callable]] = defaultdict(list)
        self._loop = None
        self.dashboard_ready_event = asyncio.Event()


    def set_loop(self, loop: asyncio.AbstractEventLoop):
        """Lưu trữ tham chiếu đến main event loop."""
        self._loop = loop

    def subscribe(self, event_type: str, callback: Callable) -> None:
        """Đăng ký *callback* cho *event_type*."""
        if callback not in self._subscribers[event_type]:
            self._subscribers[event_type].append(callback)

    def unsubscribe(self, event_type: str, callback: Callable) -> None:
        """Hủy đăng ký *callback* khỏi *event_type*."""
        if event_type in self._subscribers and callback in self._subscribers[event_type]:
            self._subscribers[event_type].remove(callback)

    def emit(self, event_or_type, payload: Dict[str, Any] | None = None) -> None:
        """
        Phát sự kiện.
        Thread-safe: có thể gọi từ cả sync code và background thread.
        """
        if isinstance(event_or_type, Event):
            event = event_or_type
        else:
            event = Event(type=event_or_type, payload=payload or {})

        # Tránh spam log với FRAME_READY
        if event.type != "FRAME_READY":
            logger.debug(f"Emit Event: {event.type}")

        listeners = self._subscribers.get(event.type, [])
        if not listeners:
            return

        for cb in listeners:
            try:
                if asyncio.iscoroutinefunction(cb):
                    if self._loop and self._loop.is_running():
                        # Dùng call_soon_threadsafe để thread-safe
                        self._loop.call_soon_threadsafe(
                            self._loop.create_task, cb(event.payload)
                        )
                    else:
                        # Fallback nếu không có loop lưu trữ
                        try:
                            loop = asyncio.get_running_loop()
                            loop.create_task(cb(event.payload))
                        except RuntimeError:
                            pass
                else:
                    if self._loop and self._loop.is_running():
                        self._loop.call_soon_threadsafe(cb, event.payload)
                    else:
                        cb(event.payload)
            except Exception as e:
                logger.exception(f"Lỗi trong event handler của {event.type}: {e}")
