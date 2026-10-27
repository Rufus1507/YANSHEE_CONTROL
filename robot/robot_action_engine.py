"""
robot_action_engine.py — Bộ điều phối hành động robot tổng hợp.

Tích hợp đầy đủ:
- Greeting khi nhận diện khuôn mặt (Feature 1-4)
- Lệnh giọng nói tiếng Việt (Feature 5)
- TTS tiếng Việt qua SSH (Feature 7)
- Action Queue có ưu tiên (Giải quyết thách thức #2)
- Liveness feedback

Tất cả hành động robot đều đi qua ActionQueue → tuần tự, không xung đột.
"""
import asyncio
import time
from logs.logger import get_logger
from events.event_bus import EventBus
from config import (
    GREETING_COOLDOWN_SECONDS,
    ROLE_ACTIONS,
    ROBOT_HOME_MOTION,
    ROBOT_RESET_DELAY,
    LIVENESS_ENABLED,
)
from .robot_connection import RobotConnectionManager
from .speech_engine import SpeechEngine
from .action_queue import ActionQueue, RobotAction, ActionPriority

logger = get_logger(__name__)


class RobotActionEngine:
    def __init__(self, bus: EventBus, robot_conn: RobotConnectionManager):
        self.bus = bus
        self.robot_conn = robot_conn
        self.local_tts = SpeechEngine()
        self.last_greet: dict[str, float] = {}
        self.state = "READY"
        self._action_task = None
        self._ever_connected = False
        self._liveness_passed_at: float = 0.0  # timestamp of last liveness pass

        # ── Action Queue (Giải quyết thách thức #2) ──────────────────
        self.action_queue = ActionQueue(event_bus=bus)

        # ── Vietnamese TTS engine (lazy init) ────────────────────────
        self._vn_tts = None

        # Subscribe to events
        self.bus.subscribe("USER_VERIFIED", self.handle_verified)
        self.bus.subscribe("UNKNOWN_USER", self.handle_unknown)
        self.bus.subscribe("LIVENESS_STARTED", self.handle_liveness_started)
        self.bus.subscribe("LIVENESS_PROGRESS", self.handle_liveness_progress)
        self.bus.subscribe("LIVENESS_PASSED", self.handle_liveness_passed)
        self.bus.subscribe("LIVENESS_FAILED", self.handle_liveness_failed)
        self.bus.subscribe("ROBOT_STATUS", self.handle_connection_status)

        # ── Feature 5: Lệnh giọng nói ───────────────────────────────
        self.bus.subscribe("VOICE_COMMAND", self.handle_voice_command)

        # ── Feature 7: TTS tiếng Việt từ dashboard ───────────────────
        self.bus.subscribe("TTS_REQUEST", self.handle_tts_request)

        # ── Feature 11: Lệnh cử chỉ tay/pose (Gesture Control) ────────
        self.bus.subscribe("GESTURE_COMMAND", self.handle_gesture_command)

    async def start(self):
        """Khởi động ActionQueue worker."""
        await self.action_queue.start()
        logger.info("[ACTION-ENGINE] ActionQueue đã khởi động")

    async def stop(self):
        """Dừng ActionQueue worker."""
        await self.action_queue.stop()

    def _get_vn_tts(self):
        """Lazy init Vietnamese TTS (tránh import lỗi nếu chưa cài gTTS/paramiko)."""
        if self._vn_tts is None:
            try:
                from voice.tts_engine import VietnameseTTS
                self._vn_tts = VietnameseTTS()
                logger.info("[ACTION-ENGINE] Vietnamese TTS engine đã khởi tạo")
            except Exception as e:
                logger.warning(f"[ACTION-ENGINE] Không thể khởi tạo VN TTS: {e}")
        return self._vn_tts

    # ---------------------------------------------------------------------
    # Connection handling
    # ---------------------------------------------------------------------
    def handle_connection_status(self, payload: dict):
        status = payload.get("status")
        if status == "offline":
            self._ever_connected = True
            self.set_state("OFFLINE")
            if self._action_task and not self._action_task.done():
                self._action_task.cancel()
        elif status == "connected":
            if not self._ever_connected or self.state == "OFFLINE":
                self._ever_connected = True
                self.state = "READY"
                self.bus.emit("ROBOT_STATUS", {"status": "ready"})

    def set_state(self, new_state: str):
        if self.state != new_state:
            self.state = new_state
            self.bus.emit("ROBOT_STATUS", {"status": new_state.lower()})

    # ---------------------------------------------------------------------
    # Feature 5: Voice Command Handler
    # ---------------------------------------------------------------------
    async def handle_voice_command(self, payload: dict) -> None:
        """
        Xử lý lệnh giọng nói.
        GIẢI QUYẾT THÁCH THỨC #2: Đưa vào ActionQueue với priority VOICE
        (cao hơn GREETING), có thể pre-empt lệnh chào đang chạy.
        """
        motion = payload.get("motion", "")
        raw_text = payload.get("raw_text", "")

        if not motion:
            return

        if not self.robot_conn.connected:
            logger.warning(f"[VOICE] Robot offline, không thể thực thi: {motion}")
            self.bus.emit("VOICE_COMMAND_FAILED", {
                "motion": motion, "reason": "robot_offline"
            })
            return

        logger.info(f"[VOICE] → Enqueue motion: {motion} (từ '{raw_text}')")

        # Tạo action cho voice command (priority cao hơn greeting)
        action = RobotAction(
            priority=ActionPriority.VOICE,
            name=f"voice:{motion}",
            coro_factory=lambda m=motion, t=raw_text: self._execute_voice_motion(m, t),
            metadata={"motion": motion, "raw_text": raw_text, "source": "voice"},
            timeout=20.0,
            cancellable=False,  # Voice command không bị hủy bởi greeting
        )
        self.action_queue.enqueue(action)

    async def _execute_voice_motion(self, motion: str, raw_text: str):
        """Thực thi hành động robot từ lệnh giọng nói."""
        self.set_state("EXECUTING_VOICE")
        self.bus.emit("VOICE_EXECUTING", {"motion": motion, "raw_text": raw_text})

        # Phản hồi TTS (nói lại lệnh)
        confirm_text = f"Đang thực hiện {raw_text}"
        tts_success = await asyncio.to_thread(self.robot_conn.send_tts, confirm_text)
        if not tts_success:
            await asyncio.to_thread(self.local_tts.say, confirm_text)

        # Thực thi motion
        motion_success = await asyncio.to_thread(self.robot_conn.send_motion, motion)
        if motion_success:
            await self._wait_for_motion_finish(timeout=15.0)
            self.bus.emit("VOICE_COMMAND_SUCCESS", {"motion": motion})
            logger.info(f"[VOICE] ✅ Robot đã thực thi: {motion}")
        else:
            self.bus.emit("VOICE_COMMAND_FAILED", {
                "motion": motion, "reason": "motion_error"
            })
            logger.warning(f"[VOICE] ❌ Thất bại: {motion}")

        self.set_state("READY")

    # ---------------------------------------------------------------------
    # Feature 11: Gesture Command Handler
    # ---------------------------------------------------------------------
    async def handle_gesture_command(self, payload: dict) -> None:
        """
        Xử lý lệnh cử chỉ tay/pose từ Gesture Camera.
        Đưa vào ActionQueue với priority GESTURE (giữa VOICE và GREETING).
        """
        action_cmd = payload.get("action", "")
        data = payload.get("data", {})

        if not action_cmd:
            return

        if not self.robot_conn.connected:
            logger.warning(f"[GESTURE] Robot offline, không thể thực thi: {action_cmd}")
            return

        motion_name = data.get("name", action_cmd)
        logger.info(f"[GESTURE] → Enqueue: {action_cmd} (motion={motion_name})")

        action = RobotAction(
            priority=ActionPriority.GESTURE,
            name=f"gesture:{action_cmd}:{motion_name}",
            coro_factory=lambda cmd=action_cmd, d=data: self._execute_gesture_motion(cmd, d),
            metadata={"action": action_cmd, "data": data, "source": "gesture"},
            timeout=15.0,
            cancellable=True,  # Có thể bị hủy bởi voice command
        )
        self.action_queue.enqueue(action)

    async def _execute_gesture_motion(self, action_cmd: str, data: dict):
        """Thực thi hành động robot từ lệnh cử chỉ."""
        self.set_state("EXECUTING_GESTURE")
        self.bus.emit("GESTURE_EXECUTING", {"action": action_cmd, "data": data})

        if action_cmd == "stop_motion":
            # Dừng motion hiện tại
            await asyncio.to_thread(self.robot_conn.send_motion, "Reset")
            logger.info("[GESTURE] ✅ Stop motion (Reset)")
        elif action_cmd == "sync_play_motion":
            motion_name = data.get("name", "")
            if motion_name:
                motion_success = await asyncio.to_thread(
                    self.robot_conn.send_motion, motion_name
                )
                if motion_success:
                    await self._wait_for_motion_finish(timeout=10.0)
                    logger.info(f"[GESTURE] ✅ Robot đã thực thi: {motion_name}")
                else:
                    logger.warning(f"[GESTURE] ❌ Thất bại: {motion_name}")

        self.bus.emit("GESTURE_COMPLETED", {"action": action_cmd, "data": data})
        self.set_state("READY")

    # ---------------------------------------------------------------------
    # Feature 7: TTS tiếng Việt
    # ---------------------------------------------------------------------
    async def handle_tts_request(self, payload: dict) -> None:
        """Xử lý yêu cầu TTS tiếng Việt (từ dashboard hoặc code khác)."""
        text = payload.get("text", "")
        if not text:
            return

        action = RobotAction(
            priority=ActionPriority.TTS,
            name=f"tts:{text[:30]}",
            coro_factory=lambda t=text: self._execute_vn_tts(t),
            metadata={"text": text},
            timeout=30.0,
            cancellable=True,
        )
        self.action_queue.enqueue(action)

    async def _execute_vn_tts(self, text: str):
        """Phát TTS tiếng Việt qua robot hoặc local."""
        self.set_state("SPEAKING_VN")
        self.bus.emit("TTS_STARTED", {"text": text})

        vn_tts = self._get_vn_tts()
        if vn_tts and self.robot_conn.connected:
            success = await asyncio.to_thread(vn_tts.speak, text)
        else:
            # Fallback: dùng robot TTS tiếng Anh hoặc local
            success = await asyncio.to_thread(self.robot_conn.send_tts, text)
            if not success:
                await asyncio.to_thread(self.local_tts.say, text)
                success = True

        self.bus.emit("TTS_FINISHED", {"text": text, "success": success})
        self.set_state("READY")

    # ---------------------------------------------------------------------
    # Liveness event handlers (speech feedback)
    # ---------------------------------------------------------------------
    async def handle_liveness_started(self, payload: dict) -> None:
        """Speak the first challenge instruction when liveness starts."""
        if not self.robot_conn.connected:
            return
        first = payload.get("first_challenge", "")
        challenges = payload.get("challenges", [])
        if first:
            spoken = f"Please {first}."
        elif challenges:
            spoken = f"Please {challenges[0]}."
        else:
            return
        logger.info(f"Robot TTS Liveness start: {spoken}")
        tts_success = await asyncio.to_thread(self.robot_conn.send_tts, spoken)
        if not tts_success:
            await asyncio.to_thread(self.local_tts.say, spoken)

    async def handle_liveness_progress(self, payload: dict) -> None:
        """Speak the current challenge during liveness verification."""
        if not self.robot_conn.connected:
            return
        text = payload.get("text")
        if not text:
            return
        spoken = f"Please {text}."
        logger.info(f"Robot TTS Liveness progress: {spoken}")
        tts_success = await asyncio.to_thread(self.robot_conn.send_tts, spoken)
        if not tts_success:
            await asyncio.to_thread(self.local_tts.say, spoken)

    async def handle_liveness_passed(self, payload: dict) -> None:
        """Announce successful liveness verification."""
        if not self.robot_conn.connected:
            return
        self._liveness_passed_at = time.time()  # record timestamp
        spoken = "Liveness verification passed."
        logger.info(f"Robot TTS Liveness passed: {spoken}")
        tts_success = await asyncio.to_thread(self.robot_conn.send_tts, spoken)
        if not tts_success:
            await asyncio.to_thread(self.local_tts.say, spoken)

    async def handle_liveness_failed(self, payload: dict) -> None:
        """Announce failed liveness verification."""
        if not self.robot_conn.connected:
            return
        spoken = "Liveness verification failed. Please try again."
        logger.info(f"Robot TTS Liveness failed: {spoken}")
        tts_success = await asyncio.to_thread(self.robot_conn.send_tts, spoken)
        if not tts_success:
            await asyncio.to_thread(self.local_tts.say, spoken)

    # ---------------------------------------------------------------------
    # Greeting for recognized users (ĐÃ TÍCH HỢP ActionQueue)
    # ---------------------------------------------------------------------
    async def handle_verified(self, payload: dict) -> None:
        user_id = payload.get("user_id", "unknown")
        name = payload.get("full_name", "Guest")
        role = payload.get("role", "Unknown")

        if not self.robot_conn.connected:
            self.set_state("OFFLINE")
            return

        now = time.time()
        last = self.last_greet.get(user_id, 0.0)
        if now - last < GREETING_COOLDOWN_SECONDS:
            logger.debug(f"Skipping greeting for {name} (cooldown)")
            return
        self.last_greet[user_id] = now
        action_cfg = ROLE_ACTIONS.get(role, ROLE_ACTIONS.get("Unknown", {"speech": "Hello", "motion": None}))
        speech = action_cfg["speech"].format(name=name)
        motion = action_cfg["motion"]

        # Delay nếu liveness vừa pass
        delay = 0.0
        if self._liveness_passed_at and (now - self._liveness_passed_at) < 3.0:
            delay = 2.0

        # ĐƯA VÀO ActionQueue thay vì tạo task trực tiếp
        action = RobotAction(
            priority=ActionPriority.GREETING,
            name=f"greet:{name}",
            coro_factory=lambda: self.run_action_flow(user_id, name, speech, motion, delay=delay),
            metadata={"user_id": user_id, "name": name, "role": role},
            timeout=30.0,
            cancellable=True,  # Có thể bị hủy bởi voice command
        )
        self.action_queue.enqueue(action)

    # ---------------------------------------------------------------------
    # Greeting for unknown/stranger users
    # ---------------------------------------------------------------------
    async def handle_unknown(self, payload: dict) -> None:
        if not self.robot_conn.connected:
            self.set_state("OFFLINE")
            return
        now = time.time()
        last = self.last_greet.get("stranger", 0.0)
        if now - last < GREETING_COOLDOWN_SECONDS:
            logger.debug("Skipping stranger greeting (cooldown)")
            return
        self.last_greet["stranger"] = now
        action_cfg = ROLE_ACTIONS.get("Stranger", {"speech": "Hello stranger", "motion": None})
        speech = action_cfg["speech"]
        motion = action_cfg["motion"]

        action = RobotAction(
            priority=ActionPriority.GREETING,
            name="greet:stranger",
            coro_factory=lambda: self.run_action_flow("stranger", "Stranger", speech, motion),
            metadata={"user_id": "stranger"},
            timeout=20.0,
            cancellable=True,
        )
        self.action_queue.enqueue(action)

    # ---------------------------------------------------------------------
    # Core action flow (speak + optional motion + reset)
    # ---------------------------------------------------------------------
    async def run_action_flow(self, user_id: str, name: str, speech: str, motion: str, delay: float = 0.0):
        try:
            # Optional delay to let a concurrent TTS (e.g. "Liveness passed") finish first
            if delay > 0:
                await asyncio.sleep(delay)

            # 1. Speaking
            self.set_state("SPEAKING")
            self.bus.emit("ROBOT_SPEAKING_STARTED", {"user_id": user_id, "speech": speech})
            logger.info(f"Robot -> Speaking started for {name}")
            tts_success = await asyncio.to_thread(self.robot_conn.send_tts, speech)
            if not tts_success:
                logger.info("Robot TTS unavailable, using local TTS")
                await asyncio.to_thread(self.local_tts.say, speech)
            self.bus.emit("ROBOT_SPEAKING_FINISHED", {"user_id": user_id})
            logger.info("Robot -> Speaking finished")


            # 2. Greeting motion (if any)
            if motion:
                self.set_state("GREETING")
                self.bus.emit("ROBOT_GREETING_STARTED", {"user_id": user_id, "motion": motion})
                logger.info(f"Robot -> Greeting started: {motion}")
                motion_success = await asyncio.to_thread(self.robot_conn.send_motion, motion)
                if not motion_success:
                    self.bus.emit("ROBOT_ACTION_FAILED", {"user_id": user_id, "motion": motion, "reason": "offline_or_error"})
                    self.set_state("READY")
                    return
                await self._wait_for_motion_finish(timeout=15.0)
                self.bus.emit("ROBOT_GREETING_FINISHED", {"user_id": user_id, "motion": motion})
                logger.info(f"Robot -> Greeting finished: {motion}")

            # 3. Wait before reset
            self.set_state("WAITING_RESET")
            self.bus.emit("ROBOT_RESET_WAITING", {"delay": ROBOT_RESET_DELAY})
            logger.info(f"Robot -> Waiting {ROBOT_RESET_DELAY}s before reset")
            await asyncio.sleep(ROBOT_RESET_DELAY)

            # 4. Reset to home position if configured
            if ROBOT_HOME_MOTION:
                self.set_state("RESETTING")
                self.bus.emit("ROBOT_RESET_STARTED", {"motion": ROBOT_HOME_MOTION})
                logger.info(f"Robot -> Reset started: {ROBOT_HOME_MOTION}")
                reset_success = await asyncio.to_thread(self.robot_conn.send_motion, ROBOT_HOME_MOTION)
                if reset_success:
                    await self._wait_for_motion_finish(timeout=10.0)
                self.bus.emit("ROBOT_RESET_FINISHED", {"motion": ROBOT_HOME_MOTION})
                logger.info("Robot -> Reset finished")

            # 5. Ready again
            self.set_state("READY")
            self.bus.emit("ROBOT_READY", {})
            logger.info("Robot -> Ready")
        except asyncio.CancelledError:
            logger.warning("Robot action flow was cancelled.")
            self.set_state("OFFLINE")
        except Exception as e:
            logger.exception("Robot action flow failed.")
            self.set_state("ERROR")
            await asyncio.sleep(2)
            self.set_state("READY" if self.robot_conn.connected else "OFFLINE")

    async def _wait_for_motion_finish(self, timeout: float):
        """Poll the robot motion status until it becomes idle or timeout."""
        start = time.time()
        await asyncio.sleep(0.5)
        while time.time() - start < timeout:
            status = await asyncio.to_thread(self.robot_conn.get_motion_status)
            if status in ("idle", "offline"):
                break
            await asyncio.sleep(0.5)
