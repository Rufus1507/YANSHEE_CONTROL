import asyncio
import logging
import sys
import os
from pathlib import Path

# Fix Windows console encoding for Vietnamese text
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

# Ensure project root is on sys.path so all local imports work
_PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from config import (
    DATABASE_PATH, DASHBOARD_HOST, DASHBOARD_PORT,
    EXIT_IF_NO_REGISTERED_USERS, REQUIRE_REGISTERED_USER_BEFORE_MAIN,
    UNKNOWN_SHUTDOWN_DELAY_SECONDS, FACE_MODEL_NAME,
    FACE_SIMILARITY_THRESHOLD, FACE_SIMILARITY_MARGIN,
    YANSHEE_CAMERA_ENABLED, YANSHEE_IP, YANSHEE_STREAM_PORT,
)

from logs.logger import get_logger
logger = get_logger(__name__)

from database.db import init_db
from recognition.face_database import FaceDatabase
from events.event_bus import EventBus
from camera.camera_manager import CameraManager
from vision.face_detector import FaceDetector
from recognition.face_matcher import FaceMatcher
from liveness.liveness_manager import LivenessManager
from recognition.pipeline import RecognitionPipeline
from robot.robot_connection import RobotConnectionManager
from robot.robot_action_engine import RobotActionEngine
from dashboard.app import start_dashboard_server
from system.monitor import SystemMonitor

def print_db_warning():
    print("\n" + "="*60)
    print("WARNING: Database chưa có user/embedding.")
    print("Hệ thống sẽ chỉ hiển thị unknown cho đến khi bạn đăng ký user.")
    print("Để đăng ký, chạy lệnh ở terminal khác:")
    print('python -m recognition.register_user --name "Ten Cua Ban" --role Student')
    print("Hệ thống sẽ tự động cập nhật dữ liệu (Auto-Reload) sau khi bạn đăng ký xong!")
    print("="*60 + "\n")

async def db_watchdog(face_matcher: FaceMatcher, db_path: str):
    """Giám sát database để tự động làm mới bộ nhớ khi có người đăng ký mới."""
    db_helper = FaceDatabase(db_path)
    last_count = db_helper.count_embeddings()
    
    while True:
        await asyncio.sleep(3)
        try:
            current_count = db_helper.count_embeddings()
            if current_count != last_count:
                logger.info(f"Phát hiện dữ liệu khuôn mặt thay đổi ({last_count} -> {current_count}). Đang tự động làm mới (Auto-Reload)...")
                face_matcher.refresh_cache()
                last_count = current_count
        except Exception as e:
            logger.error(f"Lỗi khi kiểm tra DB: {e}")


async def main():
    logger.info("Starting Yanshee AI Face Recognition Smart Greeting System")
    
    # Init DB
    init_db(DATABASE_PATH)
    
    # STARTUP CHECK
    db_helper = FaceDatabase(DATABASE_PATH)
    users_count = db_helper.count_users()
    embeddings_count = db_helper.count_embeddings()
    
    print("\n" + "="*60)
    print("  YANSHEE AI FACE RECOGNITION SYSTEM")
    print("="*60)
    print(f"\n[STARTUP CHECK]")
    print(f"  Database path     : {DATABASE_PATH}")
    print(f"  Registered users  : {users_count}")
    print(f"  Face embeddings   : {embeddings_count}")
    print(f"  Model             : {FACE_MODEL_NAME}")
    print(f"  Threshold         : {FACE_SIMILARITY_THRESHOLD}")
    print(f"  Margin            : {FACE_SIMILARITY_MARGIN}")
    
    if users_count == 0 or embeddings_count == 0:
        print_db_warning()
    
    # Camera source info
    if YANSHEE_CAMERA_ENABLED:
        print(f"  Camera source     : Yanshee Head Camera ({YANSHEE_IP}:{YANSHEE_STREAM_PORT})")
    else:
        print(f"  Camera source     : Legacy webcam (DISABLED)")
    
    print("\n[EMBEDDING] Extractor: Enhanced (Pixel + HOG + LBP) v2")
    print("  NOTE: Nếu vừa nâng cấp từ phiên bản cũ, hãy đăng ký lại user bằng:")
    print('  python -m recognition.register_user --name "Tên" --role Student')
    print("")
    print("OK - Starting main system...\n")
    
    # Event Bus
    event_bus = EventBus()
    event_bus.set_loop(asyncio.get_running_loop())
    
    shutdown_event = asyncio.Event()
    # Components
    camera = CameraManager(event_bus)
    face_detector = FaceDetector()
    face_matcher = FaceMatcher()
    liveness_manager = LivenessManager(event_bus)
    pipeline = RecognitionPipeline(event_bus, face_detector, face_matcher, liveness_manager)
    robot_conn = RobotConnectionManager(event_bus)
    robot_action = RobotActionEngine(event_bus, robot_conn)
    sys_monitor = SystemMonitor(event_bus)
    
    logger.info(f"Dashboard running at: http://{DASHBOARD_HOST}:{DASHBOARD_PORT}")
    dashboard_task = asyncio.create_task(
        start_dashboard_server(event_bus, camera, host=DASHBOARD_HOST, port=DASHBOARD_PORT)
    )

    robot_conn_task = asyncio.create_task(robot_conn.run())
    camera_task = asyncio.create_task(camera.run())
    monitor_task = asyncio.create_task(sys_monitor.run())
    watchdog_task = asyncio.create_task(db_watchdog(face_matcher, DATABASE_PATH))

    try:
        # Wait for shutdown event instead of gathering tasks that never end
        await shutdown_event.wait()
        logger.info("Shutdown event triggered.")
    except asyncio.CancelledError:
        logger.info("Main tasks cancelled.")
    finally:
        logger.info("Shutting down system components...")
        camera.stop()
        robot_conn.stop()
        dashboard_task.cancel()
        robot_conn_task.cancel()
        camera_task.cancel()
        watchdog_task.cancel()
        await asyncio.sleep(1)
        logger.info("System has fully stopped.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Shutdown requested by user (Ctrl+C).")
    except Exception as e:
        logger.exception(f"Unhandled system error: {e}")
        sys.exit(1)
