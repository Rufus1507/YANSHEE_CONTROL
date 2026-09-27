import asyncio
import sys
import os

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _PROJECT_ROOT)

from events.event_bus import EventBus
from robot.robot_connection import RobotConnectionManager
from robot.robot_action_engine import RobotActionEngine

async def main():
    print("Khởi tạo hệ thống giả lập...")
    bus = EventBus()
    bus.set_loop(asyncio.get_running_loop())
    
    robot_conn = RobotConnectionManager(bus)
    robot_action = RobotActionEngine(bus, robot_conn)
    
    # Bắt đầu robot connection (background)
    conn_task = asyncio.create_task(robot_conn.run())
    
    # Đợi một chút để kết nối
    await asyncio.sleep(2)
    
    payload = {
        "user_id": "TEST_001",
        "full_name": "Nguyen Van Test",
        "role": "Student",
        "confidence": 99.9,
        "liveness_passed": True
    }
    
    print("\n Phát sự kiện USER_VERIFIED giả lập...")
    bus.emit("USER_VERIFIED", payload)
    
    print(" Đang đợi xử lý sự kiện (5 giây)...")
    await asyncio.sleep(5)
    
    robot_conn.stop()
    await conn_task
    print("Hoàn tất!")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Đã dừng.")
