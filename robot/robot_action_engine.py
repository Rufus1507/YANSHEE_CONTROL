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

        # Subscribe to events
        self.bus.subscribe("USER_VERIFIED", self.handle_verified)
        self.bus.subscribe("UNKNOWN_USER", self.handle_unknown)
        self.bus.subscribe("LIVENESS_STARTED", self.handle_liveness_started)
        self.bus.subscribe("LIVENESS_PROGRESS", self.handle_liveness_progress)
        self.bus.subscribe("LIVENESS_PASSED", self.handle_liveness_passed)
        self.bus.subscribe("LIVENESS_FAILED", self.handle_liveness_failed)
        self.bus.subscribe("ROBOT_STATUS", self.handle_connection_status)

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
    # Greeting for recognized users
    # ---------------------------------------------------------------------
    async def handle_verified(self, payload: dict) -> None:
        user_id = payload.get("user_id", "unknown")
        name = payload.get("full_name", "Guest")
        role = payload.get("role", "Unknown")

        if not self.robot_conn.connected:
            self.set_state("OFFLINE")
            return
        if self.state not in ["READY", "OFFLINE"]:
            logger.debug(f"Skipping action for {name}, robot busy (state={self.state})")
            return
        now = time.time()
        last = self.last_greet.get(user_id, 0.0)
        if now - last < GREETING_COOLDOWN_SECONDS:
            logger.debug(f"Skipping greeting for {name} (cooldown)")
            return
        self.last_greet[user_id] = now
        action = ROLE_ACTIONS.get(role, ROLE_ACTIONS.get("Unknown", {"speech": "Hello", "motion": None}))
        speech = action["speech"].format(name=name)
        motion = action["motion"]

        # If liveness just passed within the last 3 seconds, wait 2s so the
        # "Liveness verification passed." TTS finishes before the greeting starts.
        delay = 0.0
        if self._liveness_passed_at and (now - self._liveness_passed_at) < 3.0:
            delay = 2.0
            logger.debug(f"Delaying greeting {delay}s to let liveness-passed TTS finish")

        self._action_task = asyncio.create_task(self.run_action_flow(user_id, name, speech, motion, delay=delay))

    # ---------------------------------------------------------------------
    # Greeting for unknown/stranger users
    # ---------------------------------------------------------------------
    async def handle_unknown(self, payload: dict) -> None:
        if not self.robot_conn.connected:
            self.set_state("OFFLINE")
            return
        if self.state not in ["READY", "OFFLINE"]:
            logger.debug(f"Skipping unknown action, robot busy (state={self.state})")
            return
        now = time.time()
        last = self.last_greet.get("stranger", 0.0)
        if now - last < GREETING_COOLDOWN_SECONDS:
            logger.debug("Skipping stranger greeting (cooldown)")
            return
        self.last_greet["stranger"] = now
        action = ROLE_ACTIONS.get("Stranger", {"speech": "Hello stranger", "motion": None})
        speech = action["speech"]
        motion = action["motion"]
        self._action_task = asyncio.create_task(self.run_action_flow("stranger", "Stranger", speech, motion))

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
