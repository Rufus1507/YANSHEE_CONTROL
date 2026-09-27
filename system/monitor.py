import psutil
import time
import asyncio
from events.event_bus import EventBus
from logs.logger import get_logger

logger = get_logger(__name__)

class SystemMonitor:
    def __init__(self, bus: EventBus):
        self.bus = bus
        self.running = False
        self.start_time = time.time()
        
    async def run(self):
        self.running = True
        logger.info("System Monitor started.")
        while self.running:
            try:
                cpu = psutil.cpu_percent(interval=None)
                ram = psutil.virtual_memory().percent
                uptime = time.time() - self.start_time
                
                self.bus.emit("PERFORMANCE_METRICS", {
                    "cpu": cpu,
                    "ram": ram,
                    "uptime": uptime,
                })
            except Exception as e:
                logger.error(f"Monitor error: {e}")
            await asyncio.sleep(1.0)
            
    def stop(self):
        self.running = False
