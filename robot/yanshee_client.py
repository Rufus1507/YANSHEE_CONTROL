"""
Low-level HTTP client for the Yanshee robot (OpenADK / REST API).

API Reference (discovered from live robot):
  - Ping:   GET  /v1/devices/battery
  - TTS:    PUT  /v1/voice/tts       body: {"tts": "<text>"}
  - Motion: PUT  /v1/motions         body: {"name": "<name>", "operation": "start"}
  - List:   GET  /v1/motions/list
"""
import requests
from logs.logger import get_logger

logger = get_logger(__name__)


class YansheeClient:
    def __init__(self, ip: str, port: int, timeout: int = 3):
        self.base_url = f"http://{ip}:{port}"
        self.timeout = timeout

    def send_motion(self, motion_name: str) -> bool:
        """Send a named motion to the robot. Returns True on success."""
        try:
            resp = requests.put(
                f"{self.base_url}/v1/motions",
                json={"operation": "start", "motion": {"name": motion_name}},
                timeout=self.timeout,
            )
            resp.raise_for_status()
            result = resp.json()
            if result.get("msg") == "success" or result.get("code") == 0:
                logger.info("Motion '{}' gửi thành công", motion_name)
                return True
            else:
                logger.warning("Motion '{}' phản hồi lỗi: {}", motion_name, result.get("msg"))
                return False
        except Exception:
            logger.exception("Gửi motion '{}' thất bại", motion_name)
            return False

    def get_motion_status(self) -> str:
        """Get the current motion status from the robot (e.g., 'idle', 'run')."""
        try:
            resp = requests.get(f"{self.base_url}/v1/motions", timeout=self.timeout)
            resp.raise_for_status()
            data = resp.json().get("data", {})
            return data.get("status", "idle")
        except Exception as e:
            logger.debug(f"Không thể lấy trạng thái motion: {e}")
            return "idle"

    def send_tts(self, text: str) -> bool:
        """Send TTS text to robot via PUT /v1/voice/tts."""
        try:
            resp = requests.put(
                f"{self.base_url}/v1/voice/tts",
                json={"tts": text},
                timeout=self.timeout,
            )
            resp.raise_for_status()
            result = resp.json()
            if result.get("msg") == "Success":
                logger.info("Robot TTS thành công: '{}'", text[:50])
                return True
            else:
                logger.warning("Robot TTS phản hồi lỗi: {}", result.get("msg"))
                return False
        except Exception:
            logger.debug("Robot TTS không khả dụng, dùng local TTS")
            return False

    def ping(self) -> bool:
        """Check if the robot is reachable."""
        try:
            resp = requests.get(
                f"{self.base_url}/v1/devices/battery",
                timeout=self.timeout,
            )
            return resp.ok
        except Exception:
            return False
