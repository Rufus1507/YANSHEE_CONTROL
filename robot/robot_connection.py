import asyncio
from logs.logger import get_logger
from events.event_bus import EventBus
from config import ROBOT_IP, ROBOT_PORT, ROBOT_TIMEOUT, AUTO_RECONNECT, ROBOT_ENABLED
from .yanshee_client import YansheeClient

logger = get_logger(__name__)

class RobotConnectionManager:
    def __init__(self, bus: EventBus):
        self.bus = bus
        self.client = YansheeClient(ROBOT_IP, ROBOT_PORT, timeout=ROBOT_TIMEOUT)
        self.connected = False
        self._stop = False

    async def run(self) -> None:
        if not ROBOT_ENABLED:
            logger.info("Robot integration is disabled in config.")
            self.bus.emit("ROBOT_STATUS", {"status": "disabled"})
            return

        logger.info(f"Khởi động Robot Connection Manager (IP={ROBOT_IP}:{ROBOT_PORT})")
        
        while not self._stop:
            is_ok = await self._probe()
            if is_ok != self.connected:
                self.connected = is_ok
                status_str = "connected" if is_ok else "offline"
                logger.info(f"Trạng thái Robot thay đổi: {status_str}")
                self.bus.emit("ROBOT_STATUS", {"status": status_str})

            if not self.connected and AUTO_RECONNECT:
                await asyncio.sleep(5)  # Reconnect backoff
            else:
                await asyncio.sleep(2)  # Normal heartbeat

    async def _probe(self) -> bool:
        """Run blocking ping in thread to avoid stalling the async loop."""
        try:
            return await asyncio.to_thread(self.client.ping)
        except Exception:
            return False

    def stop(self) -> None:
        self._stop = True

    def send_motion(self, motion_name: str) -> bool:
        if not self.connected:
            return False
        return self.client.send_motion(motion_name)

    def send_tts(self, text: str) -> bool:
        if not self.connected:
            return False
        return self.client.send_tts(text)

    def get_motion_status(self) -> str:
        if not self.connected:
            return "offline"
        return self.client.get_motion_status()
