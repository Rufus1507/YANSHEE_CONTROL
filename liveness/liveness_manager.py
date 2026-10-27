import random
import time
from typing import Optional, List
from events.event_bus import EventBus
from logs.logger import get_logger
from config import LIVENESS_TIMEOUT, LIVENESS_RANDOM_CHALLENGE_COUNT, LIVENESS_ENABLED, BLINK_REQUIRED_COUNT
from .blink_detector import BlinkDetector
from .mouth_detector import MouthOpenDetector
from .smile_detector import SmileDetector
from .head_pose_detector import HeadPoseEstimator

logger = get_logger(__name__)

CHALLENGE_POOL = [
    "blink", "smile", "open_mouth",
]

CHALLENGE_TEXT = {
    "blink": "blink your eyes",
    "smile": "smile",
    "open_mouth": "open your mouth"
}

class LivenessManager:
    def __init__(self, bus: EventBus, tracking_id: int = 0):
        self.bus = bus
        self.tracking_id = tracking_id
        self.blink = BlinkDetector()
        self.mouth = MouthOpenDetector()
        self.smile = SmileDetector()
        self.head_pose = HeadPoseEstimator()

        # State
        self.active = False
        self.challenges: List[str] = []
        self.current_idx = 0
        self.start_time: float = 0
        self.passed = False

    def start_session(self) -> List[str]:
        if not LIVENESS_ENABLED:
            self.passed = True
            self.bus.emit("LIVENESS_PASSED", {"tracking_id": self.tracking_id})
            return []

        count = min(LIVENESS_RANDOM_CHALLENGE_COUNT, len(CHALLENGE_POOL))
        self.challenges = random.sample(CHALLENGE_POOL, count)
        self.current_idx = 0
        self.start_time = time.time()
        self.active = True
        self.passed = False

        self.blink.reset()
        self.mouth.reset()
        self.smile.reset()

        challenge_texts = [CHALLENGE_TEXT.get(c, c) for c in self.challenges]

        self.bus.emit("LIVENESS_STARTED", {
            "challenges": challenge_texts,
            "first_challenge": self.challenges[0] if self.challenges else "",
            "timeout": LIVENESS_TIMEOUT,
            "tracking_id": self.tracking_id
        })
        # Do NOT emit progress here — LIVENESS_STARTED handler will speak the first instruction.
        # Progress is emitted when moving to the next challenge in update().
        logger.info(f"Liveness started: {self.challenges}")
        return self.challenges

    def update(self, frame, landmarks) -> Optional[bool]:
        """
        Feed landmarks. Returns:
          True  – all challenges passed
          False – timeout / failed
          None  – still in progress
        """
        if not self.active:
            return None

        elapsed = time.time() - self.start_time
        if elapsed > LIVENESS_TIMEOUT:
            self.active = False
            self.passed = False
            self.bus.emit("LIVENESS_FAILED", {"reason": "timeout", "tracking_id": self.tracking_id})
            logger.warning("Liveness failed (timeout)")
            return False

        if landmarks is None:
            # Không có face, chỉ tiếp tục chờ cho đến khi timeout
            return None

        challenge = self.challenges[self.current_idx]
        ok = self._check_challenge(challenge, landmarks)

        if ok:
            self.current_idx += 1
            if self.current_idx >= len(self.challenges):
                self.active = False
                self.passed = True
                self.bus.emit("LIVENESS_PASSED", {"tracking_id": self.tracking_id})
                logger.info("Liveness passed!")
                return True
            else:
                self._emit_progress()

        return None

    def _emit_progress(self):
        ch = self.challenges[self.current_idx]
        self.bus.emit("LIVENESS_PROGRESS", {
            "current_index": self.current_idx,
            "total": len(self.challenges),
            "current_challenge": ch,
            "text": CHALLENGE_TEXT.get(ch, ch),
            "tracking_id": self.tracking_id
        })

    def _check_challenge(self, ch: str, landmarks) -> bool:
        if ch == "blink":
            return self.blink.update(landmarks) >= BLINK_REQUIRED_COUNT
        if ch == "smile":
            return self.smile.update(landmarks)
        if ch == "open_mouth":
            return self.mouth.update(landmarks)

        # Head-pose challenges
        pose = self.head_pose.estimate(landmarks)
        if pose is None:
            return False
        yaw, pitch, _ = pose

        if ch == "turn_left":
            return yaw < -25
        if ch == "turn_right":
            return yaw > 25
        if ch == "look_up":
            return pitch < -18
        if ch == "look_down":
            return pitch > 18
        return False
