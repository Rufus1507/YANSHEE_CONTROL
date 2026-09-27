from abc import ABC, abstractmethod
from typing import Optional, Tuple

class CameraSource(ABC):
    """Abstract interface for any camera source (webcam, Yanshee stream, etc.).
    All implementations must provide the same minimal API so the rest of the
    system can stay unchanged.
    """

    @abstractmethod
    def start(self) -> None:
        """Start the underlying capture (open connections, threads, etc.)."""

    @abstractmethod
    def stop(self) -> None:
        """Stop capture and release resources."""

    @abstractmethod
    def read(self) -> Optional[Tuple[bytes, float]]:
        """Return a tuple ``(jpeg_bytes, timestamp)`` or ``None`` if no frame.
        Timestamp is ``time.time()`` when the frame was received.
        """

    @abstractmethod
    def get_fps(self) -> float:
        """Current frames‑per‑second estimate (updated by the concrete source)."""

    @abstractmethod
    def get_latency(self) -> float:
        """Latency in **milliseconds** between frame capture and this call.
        Used for dashboard metrics.
        """
