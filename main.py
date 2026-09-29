"""
main.py — HỆ THỐNG TỔNG HỢP YANSHEE AI (10+ TÍNH NĂNG)

Gộp tất cả tính năng vào một entry point duy nhất:
  1. Nhận diện khuôn mặt (Face Detection + Embedding + Cosine Similarity)
  2. Chống giả mạo (Liveness Detection)
  3. Camera & Streaming (MJPEG từ đầu robot)
  4. Điều khiển Robot (Greeting theo vai trò)
  5. Giọng nói tiếng Việt (Speech-to-Text → lệnh voice)
  6. Bộ nhớ thông minh (Robot tự học từ khóa mới)
  7. TTS tiếng Việt (gTTS → SSH → phát trên robot)
  8. Dashboard Web (FastAPI + WebSocket realtime)
  9. System Monitor (CPU, RAM, Disk, Network)
 10. Hạ tầng (EventBus, Database, Logger, Pipeline)
 11. Nhận diện cử chỉ tay/pose (Gesture — chuyển đổi on-the-fly qua CLI)

CHẾ ĐỘ CHUYỂN ĐỔI ON-THE-FLY (CLI trong terminal):
  Gõ  1  hoặc  face    → Bật Nhận diện Khuôn mặt (tắt Gesture)
  Gõ  2  hoặc  gesture → Bật Nhận diện Cử chỉ   (tắt Face camera)
  Gõ  quit / exit      → Dừng toàn bộ hệ thống
"""
import asyncio
import threading
import sys
import os

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
    GESTURE_CAMERA_INDEX,
    VOICE_ENABLED, VOICE_MIC_INDEX,
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
from System.monitor import SystemMonitor
from voice.robot_memory import RobotMemory
from voice.voice_controller import VoiceController
from gesture.gesture_bridge import GestureBridge

# ── Voice: dùng trực tiếp từ config.py (VOICE_ENABLED, VOICE_MIC_INDEX) ───


# ════════════════════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ════════════════════════════════════════════════════════════════════

def print_db_warning():
    print("\n" + "="*60)
    print("WARNING: Database chưa có user/embedding.")
    print("Hệ thống sẽ chỉ hiển thị unknown cho đến khi bạn đăng ký user.")
    print("Để đăng ký, chạy lệnh ở terminal khác:")
    print('python -m recognition.register_user --name "Ten Cua Ban" --role Student')
    print("Hệ thống sẽ tự động cập nhật dữ liệu (Auto-Reload) sau khi bạn đăng ký xong!")
    print("="*60 + "\n")


def print_cli_menu(current_mode: str):
    """In menu CLI — gọi lại mỗi khi chuyển chế độ."""
    print("\n" + "─"*60)
    print("  🎮  BẢNG ĐIỀU KHIỂN YANSHEE AI  (gõ lệnh + Enter)")
    print("─"*60)
    marker_face    = "▶ ĐANG CHẠY" if current_mode == "face"    else "  chờ      "
    marker_gesture = "▶ ĐANG CHẠY" if current_mode == "gesture" else "  chờ      "
    print(f"  [1 / face   ]  {marker_face}   — Nhận diện Khuôn mặt")
    print(f"  [2 / gesture]  {marker_gesture}   — Nhận diện Cử chỉ tay")
    print(f"  [quit / exit]               — Dừng toàn bộ hệ thống")
    print("─"*60)
    print(">> ", end="", flush=True)


async def db_watchdog(face_matcher: FaceMatcher, db_path: str):
    """Giám sát database để tự động làm mới bộ nhớ khi có người đăng ký mới."""
    db_helper = FaceDatabase(db_path)
    last_count = db_helper.count_embeddings()
    while True:
        await asyncio.sleep(3)
        try:
            current_count = db_helper.count_embeddings()
            if current_count != last_count:
                logger.info(
                    f"Phát hiện dữ liệu khuôn mặt thay đổi "
                    f"({last_count} -> {current_count}). Auto-Reload..."
                )
                face_matcher.refresh_cache()
                last_count = current_count
        except Exception as e:
            logger.error(f"Lỗi khi kiểm tra DB: {e}")


# ════════════════════════════════════════════════════════════════════
# CLI THREAD — đọc stdin không-blocking, đẩy lệnh vào asyncio Queue
# ════════════════════════════════════════════════════════════════════

def _cli_reader_thread(loop: asyncio.AbstractEventLoop,
                       cmd_queue: asyncio.Queue):
    """
    Chạy trên thread riêng (daemon).
    Đọc stdin và đẩy lệnh vào asyncio Queue để main loop xử lý.
    """
    while True:
        try:
            raw = input()          # blocking — OK vì đang ở thread riêng
            cmd = raw.strip().lower()
            asyncio.run_coroutine_threadsafe(cmd_queue.put(cmd), loop)
            if cmd in ("quit", "exit"):
                break
        except EOFError:
            asyncio.run_coroutine_threadsafe(cmd_queue.put("quit"), loop)
            break
        except Exception:
            break


# ════════════════════════════════════════════════════════════════════
# MAIN
# ════════════════════════════════════════════════════════════════════

async def main():
    logger.info("Starting Yanshee AI — INTEGRATED SYSTEM (10+ Features)")

    # ── Init DB ──────────────────────────────────────────────────────
    init_db(DATABASE_PATH)
    db_helper = FaceDatabase(DATABASE_PATH)
    users_count     = db_helper.count_users()
    embeddings_count = db_helper.count_embeddings()

    print("\n" + "="*60)
    print("  🤖 YANSHEE AI — HỆ THỐNG TỔNG HỢP 10+ TÍNH NĂNG")
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

    if YANSHEE_CAMERA_ENABLED:
        print(f"  Camera source     : Yanshee Head Camera ({YANSHEE_IP}:{YANSHEE_STREAM_PORT})")
    else:
        print(f"  Camera source     : Legacy webcam (DISABLED)")

    print(f"\n[EMBEDDING] Extractor: Enhanced (Pixel + HOG + LBP) v2")
    print(f"  NOTE: Nếu vừa nâng cấp từ phiên bản cũ, hãy đăng ký lại user bằng:")
    print(f'  python -m recognition.register_user --name "Tên" --role Student')

    print(f"\n[FEATURES]")
    print(f"  ✅  1. Nhận diện khuôn mặt")
    print(f"  ✅  2. Chống giả mạo (Liveness)")
    print(f"  ✅  3. Camera & Streaming")
    print(f"  ✅  4. Điều khiển Robot (ActionQueue)")
    print(f"  {'✅' if VOICE_ENABLED else '❌'}  5. Giọng nói tiếng Việt")
    print(f"  ✅  6. Bộ nhớ thông minh")
    print(f"  ✅  7. TTS tiếng Việt")
    print(f"  ✅  8. Dashboard Web")
    print(f"  ✅  9. System Monitor")
    print(f"  ✅ 10. Hạ tầng (EventBus, DB, Logger)")
    print(f"  🔄 11. Gesture — chuyển đổi on-the-fly qua CLI")

    print(f"\n[CHALLENGES SOLVED]")
    print(f"  ✅ #1 Anti-Blocking : Voice chạy trên thread riêng")
    print(f"  ✅ #2 Anti-Conflict : ActionQueue có priority (Voice > Greeting)")
    print(f"  ✅ #3 Resource Mgmt : Camera được nhả trước khi chuyển chế độ")

    print(f"\nOK - Starting main system...\n")

    # ── Shutdown Event ───────────────────────────────────────────────
    shutdown_event = asyncio.Event()

    # ── Event Bus ────────────────────────────────────────────────────
    event_bus = EventBus()
    loop = asyncio.get_running_loop()
    event_bus.set_loop(loop)

    # ── Core Components ──────────────────────────────────────────────
    camera           = CameraManager(event_bus)
    face_detector    = FaceDetector()
    face_matcher     = FaceMatcher()
    liveness_manager = LivenessManager(event_bus)
    pipeline         = RecognitionPipeline(event_bus, face_detector, face_matcher, liveness_manager)
    robot_conn       = RobotConnectionManager(event_bus)
    robot_action     = RobotActionEngine(event_bus, robot_conn)
    sys_monitor      = SystemMonitor(event_bus)

    # ── Feature 6: Bộ nhớ thông minh ────────────────────────────────
    robot_memory = RobotMemory(event_bus=event_bus)
    mem_stats = robot_memory.get_stats()
    print(f"[MEMORY] Loaded: {mem_stats['total_motions']} motions, "
          f"{mem_stats['total_keywords']} keywords")

    # ── Feature 5: Voice Controller (luôn chạy, không phụ thuộc chế độ)
    voice_controller = None
    if VOICE_ENABLED:
        voice_controller = VoiceController(
            event_bus=event_bus,
            robot_memory=robot_memory,
            mic_index=VOICE_MIC_INDEX,
        )

    # ── Khởi động các task nền bất biến ─────────────────────────────
    logger.info(f"Dashboard running at: http://{DASHBOARD_HOST}:{DASHBOARD_PORT}")
    dashboard_task   = asyncio.create_task(
        start_dashboard_server(event_bus, camera, host=DASHBOARD_HOST, port=DASHBOARD_PORT, shutdown_event=shutdown_event)
    )
    robot_conn_task  = asyncio.create_task(robot_conn.run())
    monitor_task     = asyncio.create_task(sys_monitor.run())
    watchdog_task    = asyncio.create_task(db_watchdog(face_matcher, DATABASE_PATH))

    await robot_action.start()

    if voice_controller:
        voice_controller.start()
        logger.info("🎤 Voice Controller đã khởi động trên thread riêng")

    # ── Trạng thái chế độ hiện tại ───────────────────────────────────
    # Mặc định: bắt đầu bằng chế độ FACE
    current_mode:  str                        = "face"
    camera_task:   asyncio.Task | None        = asyncio.create_task(camera.run())
    gesture_bridge: GestureBridge | None      = None

    logger.info("📷 Chế độ mặc định: Nhận diện Khuôn mặt (Face)")

    # ── CLI Queue & Thread ───────────────────────────────────────────
    cmd_queue: asyncio.Queue = asyncio.Queue()
    cli_thread = threading.Thread(
        target=_cli_reader_thread,
        args=(loop, cmd_queue),
        name="CLIReader",
        daemon=True,
    )
    cli_thread.start()

    # Đợi hệ thống khởi động xong rồi mới hiện menu
    await asyncio.sleep(2)
    print_cli_menu(current_mode)

    # ════════════════════════════════════════════════════════════════
    # VÒNG LẶP XỬ LÝ LỆNH CLI
    # ════════════════════════════════════════════════════════════════
    try:
        while True:
            cmd = await cmd_queue.get()

            # ── Thoát ────────────────────────────────────────────────
            if cmd in ("quit", "exit", "q"):
                print("\n[CLI] Đang dừng hệ thống...")
                shutdown_event.set()
                break

            # ── Chuyển sang chế độ FACE ──────────────────────────────
            elif cmd in ("1", "face") and current_mode != "face":
                print("\n[CLI] ⏳ Đang chuyển sang chế độ Nhận diện Khuôn mặt...")

                # 1. Dừng Gesture (nhả camera gesture)
                if gesture_bridge:
                    gesture_bridge.stop()
                    gesture_bridge = None
                    await asyncio.sleep(1)   # đợi camera nhả resource

                # 2. Khởi động Face camera
                camera_task = asyncio.create_task(camera.run())
                current_mode = "face"
                logger.info("📷 Đã chuyển sang chế độ: Nhận diện Khuôn mặt")
                print("[CLI] ✅ Đã bật Nhận diện Khuôn mặt!")
                print_cli_menu(current_mode)

            # ── Chuyển sang chế độ GESTURE ───────────────────────────
            elif cmd in ("2", "gesture") and current_mode != "gesture":
                print("\n[CLI] ⏳ Đang chuyển sang chế độ Nhận diện Cử chỉ...")

                # 1. Dừng Face camera (nhả resource camera 0)
                if camera_task and not camera_task.done():
                    camera.stop()
                    camera_task.cancel()
                    try:
                        await camera_task
                    except asyncio.CancelledError:
                        pass
                    camera_task = None
                    await asyncio.sleep(1)   # đợi camera nhả resource

                # 2. Khởi động Gesture bridge
                gesture_bridge = GestureBridge(
                    event_bus=event_bus,
                    action_queue=robot_action.action_queue,
                    camera_index=GESTURE_CAMERA_INDEX,
                )
                gesture_bridge.start()
                current_mode = "gesture"
                logger.info(f"🖐️ Đã chuyển sang chế độ: Nhận diện Cử chỉ (camera={GESTURE_CAMERA_INDEX})")
                print("[CLI] ✅ Đã bật Nhận diện Cử chỉ! (Cửa sổ camera sẽ mở ra)")
                print_cli_menu(current_mode)

            # ── Lệnh không hợp lệ ────────────────────────────────────
            elif cmd in ("1", "face") or cmd in ("2", "gesture"):
                print(f"[CLI] ℹ️  Đang ở chế độ '{current_mode}' rồi, không cần chuyển.")
                print(">> ", end="", flush=True)

            elif cmd == "":
                # Enter trống — chỉ hiện lại dấu nhắc
                print(">> ", end="", flush=True)

            else:
                print(f"[CLI] ❓ Lệnh không nhận ra: '{cmd}'")
                print("      Gõ  1/face  |  2/gesture  |  quit")
                print(">> ", end="", flush=True)

    except asyncio.CancelledError:
        logger.info("Main loop cancelled.")

    finally:
        # ── GRACEFUL SHUTDOWN ─────────────────────────────────────────
        logger.info("Shutting down system components...")

        if gesture_bridge:
            gesture_bridge.stop()
            logger.info("🖐️  Gesture Controller đã dừng")

        if camera_task and not camera_task.done():
            camera.stop()
            camera_task.cancel()

        if voice_controller:
            voice_controller.stop()
            logger.info("🎤 Voice Controller đã dừng")

        await robot_action.stop()
        logger.info("📋 ActionQueue đã dừng")

        robot_conn.stop()

        dashboard_task.cancel()
        robot_conn_task.cancel()
        monitor_task.cancel()
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
