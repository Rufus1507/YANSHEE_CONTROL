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
    # --- Di chuyển ---
    "Forward": ["đi thẳng", "tiến lên", "đi tới"],
    "Backward": ["đi lùi", "lùi lại"],
    "TurnLeft": ["rẽ trái", "quay trái"],
    "TurnRight": ["rẽ phải", "quay phải"],
    "Stop": ["dừng lại", "đứng yên", "thôi", "dừng"],
    "Reset": ["khởi động lại", "về vị trí cũ", "đứng nghiêm"],
    # --- Bước đơn ---
    "OneStepForward": ["tiến một bước", "bước lên"],
    "OneStepBackward": ["lùi một bước", "bước lùi"],
    "OneStepTurnLeft": ["xoay trái một bước"],
    "OneStepTurnRight": ["xoay phải một bước"],
    "OneStepMoveLeft": ["nhích sang trái", "bước sang trái"],
    "OneStepMoveRight": ["nhích sang phải", "bước sang phải"],
    "Move_fast": ["chạy nhanh", "tăng tốc"],
    # --- Tương tác ---
    "RaiseRightHand": ["giơ tay phải"],
    "Wave": ["vẫy tay", "tạm biệt", "xin chào"],
    "Hug": ["ôm cái nào", "ôm"],
    "Victory": ["chiến thắng", "vô địch"],
    # --- Trạng thái ---
    "EnterEnergySavingSquat": ["tiết kiệm pin", "ngồi xổm xuống"],
    "ExitEnergySavingReset": ["thoát tiết kiệm pin", "đứng dậy đi"],
    # --- Giải trí ---
    "WakaWaka": ["nhảy waka waka", "vũ điệu waka", "waka waka"],
    "MerryChristmas": ["giáng sinh", "nhảy noel", "merry christmas"],
    "HappyBirthday": ["sinh nhật", "chúc mừng sinh nhật"],
    "SweetAndSour": ["nhảy chua ngọt"],
    # --- Thể thao ---
    "PushUp": ["hít đất", "chống đẩy"],
    "Football_RKick": ["đá chân phải", "sút bằng chân phải"],
    "Football_LKick": ["đá chân trái", "sút bằng chân trái"],
    "LeftSidePunch": ["đấm bên trái"],
    "RightSidePunch": ["đấm bên phải"],
    "LeftHitForward": ["đấm thẳng tay trái"],
    "RightHitForward": ["đấm thẳng tay phải"],
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
