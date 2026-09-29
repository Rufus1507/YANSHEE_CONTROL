"""
SystemMonitor — Giám sát tài nguyên hệ thống theo thời gian thực.

Thu thập thông số CPU, RAM, Disk, nhiệt độ (nếu có), và thông tin
tiến trình hiện tại, sau đó phát sự kiện ``SYSTEM_METRICS`` qua EventBus
để Dashboard có thể hiển thị.

Chạy như một asyncio task vô hạn, mặc định thu thập mỗi 3 giây.
"""

import asyncio
import time
import platform
from typing import Dict, Any, Optional

import psutil

from logs.logger import get_logger
from events.event_bus import EventBus

logger = get_logger(__name__)

# Khoảng thời gian giữa các lần thu thập (giây)
_DEFAULT_INTERVAL: float = 3.0


class SystemMonitor:
    """Thu thập và phát tín hiệu thông số tài nguyên hệ thống.

    Parameters
    ----------
    event_bus : EventBus
        Kênh giao tiếp dùng chung của toàn hệ thống.
    interval : float, optional
        Chu kỳ thu thập dữ liệu (giây). Mặc định 3 giây.
    """

    def __init__(self, event_bus: EventBus, interval: float = _DEFAULT_INTERVAL):
        self.bus = event_bus
        self.interval = interval
        self._running = False
        self._process: Optional[psutil.Process] = None
        self._start_time: float = 0.0

    # ------------------------------------------------------------------
    # Thu thập thông số
    # ------------------------------------------------------------------

    def _collect_cpu(self) -> Dict[str, Any]:
        """Thông số CPU."""
        freq = psutil.cpu_freq()
        return {
            "percent": psutil.cpu_percent(interval=None),          # tổng % CPU
            "per_core": psutil.cpu_percent(interval=None, percpu=True),  # % từng core
            "cores_physical": psutil.cpu_count(logical=False) or 0,
            "cores_logical": psutil.cpu_count(logical=True) or 0,
            "freq_current_mhz": round(freq.current, 1) if freq else None,
            "freq_max_mhz": round(freq.max, 1) if freq and freq.max else None,
        }

    def _collect_memory(self) -> Dict[str, Any]:
        """Thông số RAM."""
        vm = psutil.virtual_memory()
        return {
            "total_mb": round(vm.total / (1024 ** 2), 1),
            "used_mb": round(vm.used / (1024 ** 2), 1),
            "available_mb": round(vm.available / (1024 ** 2), 1),
            "percent": vm.percent,
        }

    def _collect_disk(self) -> Dict[str, Any]:
        """Thông số ổ đĩa (phân vùng chứa dự án)."""
        try:
            usage = psutil.disk_usage("/")
            return {
                "total_gb": round(usage.total / (1024 ** 3), 2),
                "used_gb": round(usage.used / (1024 ** 3), 2),
                "free_gb": round(usage.free / (1024 ** 3), 2),
                "percent": usage.percent,
            }
        except Exception:
            return {}

    def _collect_temperature(self) -> Optional[Dict[str, Any]]:
        """Nhiệt độ CPU/GPU (chỉ hỗ trợ Linux / Raspberry Pi).

        Trên Windows thường không khả dụng nên trả về None.
        """
        if not hasattr(psutil, "sensors_temperatures"):
            return None
        try:
            temps = psutil.sensors_temperatures()
            if not temps:
                return None
            result: Dict[str, Any] = {}
            for chip, entries in temps.items():
                for entry in entries:
                    label = entry.label or chip
                    result[label] = {
                        "current": entry.current,
                        "high": entry.high,
                        "critical": entry.critical,
                    }
            return result
        except Exception:
            return None

    def _collect_network(self) -> Dict[str, Any]:
        """Băng thông mạng (bytes gửi/nhận tích lũy)."""
        try:
            counters = psutil.net_io_counters()
            return {
                "bytes_sent": counters.bytes_sent,
                "bytes_recv": counters.bytes_recv,
                "packets_sent": counters.packets_sent,
                "packets_recv": counters.packets_recv,
            }
        except Exception:
            return {}

    def _collect_process(self) -> Dict[str, Any]:
        """Thông số tiến trình Python hiện tại (chính mình)."""
        if self._process is None:
            return {}
        try:
            with self._process.oneshot():
                mem = self._process.memory_info()
                return {
                    "pid": self._process.pid,
                    "cpu_percent": self._process.cpu_percent(interval=None),
                    "rss_mb": round(mem.rss / (1024 ** 2), 1),
                    "threads": self._process.num_threads(),
                }
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return {}

    # ------------------------------------------------------------------
    # Tổng hợp
    # ------------------------------------------------------------------

    def collect_all(self) -> Dict[str, Any]:
        """Thu thập toàn bộ thông số và trả về dict."""
        uptime = round(time.monotonic() - self._start_time, 1) if self._start_time else 0
        data: Dict[str, Any] = {
            "cpu": self._collect_cpu(),
            "memory": self._collect_memory(),
            "disk": self._collect_disk(),
            "network": self._collect_network(),
            "process": self._collect_process(),
            "platform": platform.system(),
            "uptime_seconds": uptime,
        }
        temp = self._collect_temperature()
        if temp:
            data["temperature"] = temp
        return data

    # ------------------------------------------------------------------
    # Vòng lặp chính
    # ------------------------------------------------------------------

    async def run(self) -> None:
        """Chạy vòng lặp thu thập vô hạn (dùng với ``asyncio.create_task``)."""
        self._running = True
        self._start_time = time.monotonic()
        self._process = psutil.Process()

        # Khởi tạo cpu_percent lần đầu (lần gọi đầu luôn trả 0)
        psutil.cpu_percent(interval=None)
        if self._process:
            try:
                self._process.cpu_percent(interval=None)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

        logger.info(
            f"SystemMonitor started — collecting every {self.interval}s "
            f"(platform={platform.system()}, cores={psutil.cpu_count()})"
        )

        while self._running:
            try:
                metrics = self.collect_all()
                self.bus.emit("SYSTEM_METRICS", metrics)

                # Log tóm tắt ở mức DEBUG
                cpu_pct = metrics["cpu"]["percent"]
                mem_pct = metrics["memory"]["percent"]
                proc_rss = metrics["process"].get("rss_mb", "?")
                logger.debug(
                    f"[SysMonitor] CPU={cpu_pct}% | RAM={mem_pct}% | "
                    f"Process RSS={proc_rss}MB | Uptime={metrics['uptime_seconds']}s"
                )
            except Exception as e:
                logger.error(f"SystemMonitor lỗi khi thu thập: {e}")

            await asyncio.sleep(self.interval)

    def stop(self) -> None:
        """Dừng vòng lặp thu thập."""
        self._running = False
        logger.info("SystemMonitor stopped.")
