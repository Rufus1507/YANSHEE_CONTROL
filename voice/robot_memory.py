"""
robot_memory.py — Bộ nhớ thông minh của robot.

Quản lý việc đọc/ghi từ khóa tiếng Việt → tên hành động robot.
Robot tự học thêm từ khóa mới từ người dùng thông qua EventBus.

GIẢI QUYẾT THÁCH THỨC:
- Thread-safe: Dùng threading.Lock để tránh race condition khi
  nhiều thread cùng đọc/ghi bộ nhớ.
- Tích hợp EventBus: Phát sự kiện MEMORY_UPDATED khi học từ mới.
"""
import json
import os
import threading
from pathlib import Path
from logs.logger import get_logger

logger = get_logger(__name__)

# Default memory nằm trong data/ thay vì Feature_Smart_Voice_Memory/
_DEFAULT_MEMORY_PATH = os.path.join(
    Path(__file__).resolve().parent.parent, "data", "robot_memory.json"
)

# Bộ nhớ gốc ban đầu — đầy đủ tất cả action của Yanshee
_DEFAULT_MEMORY = {

    "RaiseRightHand": {
        "giơ tay lên", "giơ tay", "tạm biệt"
    },

    "H_WaveRH": {
        "vẫy tay", "wave", "tạm biệt", "bye", "goodbye"
    },

    "Hug": {
        "ôm", "ôm đi"
    },

    # ================== DI CHUYỂN ==================
    "Forward": {
        "tiến", "tiến lên", "đi tới", "đi lên",
        "forward", "go forward"
    },

    "Backward": {
        "lùi", "đi lùi", "lùi lại",
        "back", "go back"
    },

    "TurnLeft": {
        "rẽ trái", "quay trái",
        "left", "turn left"
    },

    "TurnRight": {
        "rẽ phải", "quay phải",
        "right", "turn right"
    },

    "OneStepForward": {
        "bước tới", "bước lên"
    },

    "OneStepBackward": {
        "bước lùi"
    },

    "OneStepTurnLeft": {
        "xoay trái một bước"
    },

    "OneStepTurnRight": {
        "xoay phải một bước"
    },

    "OneStepMoveLeft": {
        "qua trái"
    },

    "OneStepMoveRight": {
        "qua phải"
    },

    "Move_fast": {
        "đi nhanh", "nhanh lên"
    },

    "Stop": {
        "dừng", "dừng lại", "stop", "đứng yên"
    },

    "Reset": {
        "reset", "đứng thẳng"
    },

    # ================== NĂNG LƯỢNG ==================
    "EnterEnergySavingSquat": {
        "ngồi", "ngồi xuống", "ngồi nghỉ"
    },

    "ExitEnergySavingReset": {
        "đứng lên", "đứng dậy"
    },

    # ================== ÂM THANH ==================
    "WakaWaka": {
        "nhảy", "nhảy waka", "waka", "nhảy đi", "nhảy lên"
    },
    "MerryChristmas": {
        "giáng sinh", "giáng sinh vui vẻ", "merry christmas"
    },
    "HappyBirthday": {
        "sinh nhật", "chúc mừng sinh nhật", "happy birthday"
    },
    "WeAreTakingOff": {
        "cất cánh", "cất cánh thôi", "cất cánh đi", "cất cánh lên","We Are Taking Off"
    },

    "Victory": {
        "xin chào", "ăn mừng", "chào","hi","hello","hey","hey robot"
    },
    "GetupFront": {
        "ngã sấp đứng dậy", "ngã sấp đứng lên", "ngã sấp đứng dậy đi", "ngã sấp đứng dậy lên"
    },
    "GetupRear": {
        "ngã ngửa đứng dậy", "ngã ngửa đứng lên", "ngã ngửa đứng dậy đi", "ngã ngửa đứng dậy lên"
    },
    "PushUp": {
        "hít đất", "hít đất đi", "hít đất lên", "hít đất đi lên","chống đẩy","chống đẩy đi","chống đẩy lên","chống đẩy đi lên"
    },
    "GetUp": {
        "Tập thể dục", "tập thể dục đi", "tập thể dục lên", "tập thể dục đi lên"
    },

    # ================== BÓNG ĐÁ (THỂ THAO) ==================
    "Football_LKick": {
        "sút trái", "đá trái", "sút chân trái", "đá chân trái"
    },
    "Football_RKick": {
        "sút phải", "đá phải", "sút chân phải", "đá chân phải"
    },
    "Football_LShoot": {
        "dứt điểm trái", "sút mạnh trái", "sút bóng trái","sút banh trái","sút banh"
    },
    "Football_RShoot": {
        "dứt điểm phải", "sút mạnh phải", "sút bóng phải", "sút bóng", "đá bóng","đá banh","sút banh phải"
    },
    "GoalKeeper1": {
        "bắt bóng", "thủ môn bắt bóng", "bảo vệ khung thành","bắt banh"
    },
    "GoalKeeper2": {
        "bắt bóng trên", "chuẩn bị bắt bóng", "thủ môn","bắt banh trên"
    },
    "Football_LKeep": {
        "bắt bóng trái", "đổ người bên trái", "đổ người trái","bắt banh trái"
    },
    "Football_RKeep": {
        "bắt bóng phải", "đổ người bên phải", "đổ người phải","bắt banh phải"
    },
    "LeftTackle": {
        "xoạc bóng trái", "cướp bóng trái","xoạc banh trái"
    },
    "RightTackle": {
        "xoạc bóng phải", "cướp bóng phải", "xoạc bóng","xoạc banh phải"
    },
    "Left slide tackle": {
        "chồi bóng trái", "trượt bóng trái","xoạc banh trái"
    },

    # ================== CHIẾN ĐẤU (FIGHT) ==================
    "LeftSidePunch": {
        "đấm ngang trái", "đánh ngang trái", "đấm tay trái", "đánh tay trái"
    },
    "RightSidePunch": {
        "đấm ngang phải", "đánh ngang phải", "đấm tay phải", "đánh tay phải"
    },
    "Fight_LHit": {
        "đấm thẳng trái", "đánh thẳng trái", "tấn công trái"
    },
    "Fight_RHit": {
        "đấm thẳng phải", "đánh thẳng phải", "tấn công phải", "đấm thẳng", "tấn công"
    },
    "Fight_LSideHit": {
        "đòn sườn trái", "đánh sườn trái", "móc trái"
    },
    "Fight_RSideHit": {
        "đòn sườn phải", "đánh sườn phải", "móc phải", "đòn sườn"
    },
    "LeftHitForward": {
        "gạt đòn trái", "đỡ đòn trái", "chặn đòn trái"
    },
    "RightHitForward": {
        "gạt đòn phải", "đỡ đòn phải", "chặn đòn", "gạt đòn"
    },

    "PlayMusic": {
        "phát nhạc", "bật nhạc", "mở nhạc", "play music"
    },

    "StopMusic": {
        "tắt nhạc", "dừng nhạc", "stop music"
    },

    "VolumeUp": {
        "tăng âm lượng", "to lên", "lớn lên"
    },

    "VolumeDown": {
        "giảm âm lượng", "nhỏ lại"
    },

    "Mute": {
        "tắt âm thanh", "im lặng", "mute","tắt tiếng","tắt tiếng đi","tắt tiếng lên","tắt tiếng đi lên"
    },

    "Unmute": {
        "bật âm thanh", "mở tiếng"
    },
}


class RobotMemory:
    """Thread-safe bộ nhớ từ khóa giọng nói → hành động robot."""

    def __init__(self, memory_path: str | None = None, event_bus=None):
        self._path = memory_path or _DEFAULT_MEMORY_PATH
        self._bus = event_bus
        self._lock = threading.Lock()
        self._memory: dict[str, list[str]] = {}
        self._load()

    # ── I/O ──────────────────────────────────────────────────────────
    def _load(self):
        """Đọc bộ nhớ từ file JSON, hoặc tạo file mặc định nếu chưa có."""
        if os.path.exists(self._path):
            try:
                with open(self._path, "r", encoding="utf-8") as f:
                    self._memory = json.load(f)
                logger.info(f"Đã tải bộ nhớ robot từ: {self._path} "
                            f"({len(self._memory)} hành động)")
                return
            except (json.JSONDecodeError, OSError) as e:
                logger.warning(f"Lỗi đọc bộ nhớ ({e}), dùng bộ nhớ mặc định.")

        # Tạo mới từ default
        self._memory = dict(_DEFAULT_MEMORY)
        self._save()
        logger.info(f"Đã tạo bộ nhớ mặc định: {self._path}")

    def _save(self):
        """Ghi bộ nhớ ra file JSON."""
        os.makedirs(os.path.dirname(self._path), exist_ok=True)
        with open(self._path, "w", encoding="utf-8") as f:
            json.dump(self._memory, f, ensure_ascii=False, indent=4)

    # ── Tra cứu (thread-safe) ────────────────────────────────────────
    def find_motion(self, speech_text: str) -> str:
        """
        Quét bộ nhớ để tìm hành động khớp với câu nói.
        Trả về tên motion (vd: "Forward") hoặc "" nếu không khớp.
        """
        text = speech_text.lower().strip()
        with self._lock:
            for motion, keywords in self._memory.items():
                for kw in keywords:
                    if kw in text:
                        return motion
        return ""

    # ── Học từ mới (thread-safe) ─────────────────────────────────────
    def learn_keyword(self, motion_name: str, new_keyword: str) -> bool:
        """
        Thêm từ khóa mới cho một hành động đã biết.
        Trả về True nếu thành công, False nếu motion_name không tồn tại.
        """
        new_keyword = new_keyword.lower().strip()
        with self._lock:
            if motion_name not in self._memory:
                logger.warning(f"Hành động '{motion_name}' không tồn tại trong bộ nhớ.")
                return False
            if new_keyword in self._memory[motion_name]:
                logger.info(f"Từ khóa '{new_keyword}' đã tồn tại cho '{motion_name}'.")
                return True
            self._memory[motion_name].append(new_keyword)
            self._save()

        logger.info(f"🧠 Robot đã học: '{new_keyword}' → {motion_name}")
        if self._bus:
            self._bus.emit("MEMORY_UPDATED", {
                "motion": motion_name,
                "keyword": new_keyword,
                "total_keywords": len(self._memory[motion_name]),
            })
        return True

    # ── Liệt kê ─────────────────────────────────────────────────────
    def get_all_motions(self) -> list[str]:
        """Trả về danh sách tất cả tên hành động."""
        with self._lock:
            return list(self._memory.keys())

    def get_keywords(self, motion_name: str) -> list[str]:
        """Trả về danh sách từ khóa của một hành động."""
        with self._lock:
            return list(self._memory.get(motion_name, []))

    def get_stats(self) -> dict:
        """Trả về thống kê bộ nhớ."""
        with self._lock:
            total_keywords = sum(len(kws) for kws in self._memory.values())
            return {
                "total_motions": len(self._memory),
                "total_keywords": total_keywords,
                "path": self._path,
            }
