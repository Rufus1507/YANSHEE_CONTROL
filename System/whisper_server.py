import speech_recognition as sr
import time
import re
import itertools
import socket
import struct
import threading
import json
_qc = itertools.count()

# ═══════════════════════════════════════════════════════════
# CẤU HÌNH TCP SERVER (nhận audio từ mic_client.py)
# ═══════════════════════════════════════════════════════════
SERVER_HOST = "0.0.0.0"   # Lắng nghe trên mọi interface
SERVER_PORT = 9999         # Cổng mặc định, đổi nếu cần
from YanAPI import YanAPI

try:
    from rapidfuzz import process, fuzz
    HAS_RAPIDFUZZ = True
except ImportError:
    HAS_RAPIDFUZZ = False

# ==========================================
# Đã dời CẤU HÌNH IP sang main_control.py
# ==========================================
command_queue = None

# ==========================================
# TỪ ĐIỂN ÁNH XẠ: Từ khóa (Tiếng Việt) -> Tên Motion
# ==========================================
# Lưu ý: Các tên "SayHello", "RaiseRightHand", "Bow", "WakaWaka" là
# những action tiêu chuẩn phổ biến trên robot Yanshee. 
# Nếu Robot báo không tìm thấy, bạn có thể kiểm tra lại tên đúng nhờ hàm danh sách.
MOTION_MAP = {

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
        "forward", "go forward",
        "tới", "lên",  # Thêm từ khóa ngắn hỗ trợ "tới 3 bước"
    },

    "Backward": {
        "lùi", "đi lùi", "lùi lại","bước lui"
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
        "nghỉ","nghỉ ngơi","nghỉ ngơi đi","tiết kiệm năng lượng","vào chế độ tiết kiệm năng lượng"
    },

    "ExitEnergySavingReset": {
        "dừng nghỉ","dừng nghỉ đi","dừng nghỉ ngơi","thoát tiết kiệm năng lượng","thoát chế độ tiết kiệm năng lượng"
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
        "ngã sấp đứng dậy", "ngã sấp đứng lên", "ngã sấp đứng dậy đi", "ngã sấp đứng dậy lên","nằm sấp đứng dậy","nằm sấp đứng lên","nằm sấp đứng dậy đi","nằm sấp đứng dậy lên","lật lại","lật người"
    },
    "GetupRear": {
        "ngã ngửa đứng dậy", "ngã ngửa đứng lên", "ngã ngửa đứng dậy đi", "ngã ngửa đứng dậy lên","nằm ngửa đứng dậy","nằm ngửa đứng lên","nằm ngửa đứng dậy đi","nằm ngửa đứng dậy lên","ngồi dậy","đứng dậy","đứng lên"
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
    "LeftHitForward": {
        "đấm thẳng trái", "đánh thẳng trái", "tấn công trái"
    },
    "RightHitForward": {
        "đấm thẳng phải", "đánh thẳng phải", "tấn công phải", "đấm thẳng", "tấn công"
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
def normalize_text(text):
    """Lọc rác và chuẩn hóa văn bản"""
    text = re.sub(r'[^\w\s]', '', text)
    # Thêm 'nói', 'bạn' vào stopwords để lọc prefix rác như "nói 3 bước"
    stopwords = ["robot", "ơi", "làm ơn", "hãy", "cho tôi", "nhé", "nha", "đi", "thực hiện", "nói", "bạn"]
    for word in stopwords:
        text = text.replace(word, " ")
    return " ".join(text.split())


def collect_commands(text: str) -> list:
    """
    Nhận text từ Whisper → xử lý NLP → trả về list[dict] các lệnh.
    Mỗi dict có dạng: {"priority": int, "action": str, "data": dict}
    Hàm này KHÔNG push vào bất kỳ queue nào, chỉ trả về dữ liệu.
    """
    commands = []  # Danh sách lệnh sẽ được trả về
    text = text.lower().strip()
    if not text:
        return commands

    print(f"\n[NLP] Xử lý: '{text}'")

    def _add(priority, action, data):
        commands.append({"priority": priority, "source": "voice",
                         "action": action, "data": data})

    # 0. Thoát chương trình
    if any(k in text for k in ["tắt chương trình", "kết thúc chương trình",
                                "thoát chương trình", "đóng chương trình",
                                "dừng chương trình"]):
        print("=> [TẮT HỆ THỐNG]")
        _add(0, "exit", {})
        return commands

    # 1. Dừng nhạc
    if any(k in text for k in ["dừng nhạc", "tắt nhạc", "dừng phát nhạc",
                                "dừng chơi nhạc", "ngừng nhạc",
                                "ngừng phát nhạc", "ngừng chơi nhạc"]):
        print("=> [DỪNG NHẠC]")
        _add(1, "stop_music", {})
        text = re.sub(r'(dừng|tắt|ngừng)\s*(chơi\s*)?nhạc', '', text).strip()
        if not text:
            return commands

    # 1.5. Âm lượng %
    _nw = {"một":"1","hai":"2","ba":"3","bốn":"4","năm":"5","sáu":"6",
           "bảy":"7","tám":"8","chín":"9","mười":"10","hai mươi":"20",
           "ba mươi":"30","bốn mươi":"40","năm mươi":"50","sáu mươi":"60",
           "bảy mươi":"70","tám mươi":"80","chín mươi":"90","một trăm":"100"}
    vt = text
    for w, d in _nw.items():
        vt = re.sub(r'(?<!\w)' + w + r'(?!\w)', d, vt)

    m = re.search(r'tăng\s+âm\s+lượng\s+(\d+)\s*(%|phần\s*trăm)', vt)
    if m:
        pct = int(m.group(1))
        print(f"=> [TĂNG ÂM LƯỢNG {pct}%]")
        _add(1, "volume_up_by", {"pct": pct})
        return commands

    m = re.search(r'giảm\s+âm\s+lượng\s+(\d+)\s*(%|phần\s*trăm)', vt)
    if m:
        pct = int(m.group(1))
        print(f"=> [GIẢM ÂM LƯỢNG {pct}%]")
        _add(1, "volume_down_by", {"pct": pct})
        return commands

    m = re.search(r'(?:đặt|chỉnh|set)\s+âm\s+lượng\s+(?:về\s*)?(\d+)\s*(%|phần\s*trăm)', vt)
    if m:
        pct = min(100, max(0, int(m.group(1))))
        print(f"=> [ĐẶT ÂM LƯỢNG {pct}]")
        _add(1, "set_volume", {"vol": pct})
        return commands

    # 2. Dừng motion
    if any(k in text for k in ["dừng", "thôi", "ngừng"]):
        print("=> [DỪNG MOTION]")
        _add(1, "stop_motion", {})
        _add(1, "sync_play_motion", {"name": "Reset", "repeat": 1})
        return commands

    # 3. Chuẩn hóa & NLP
    norm_text = normalize_text(text)
    print(f"   NLP: '{norm_text}'")

    def do_action(motion_name, chunk_text, rep, is_counted=False):
        if is_counted:
            step_map = {"Forward": "OneStepForward", "Backward": "OneStepBackward",
                        "TurnLeft": "OneStepTurnLeft", "TurnRight": "OneStepTurnRight"}
            if motion_name in step_map:
                motion_name = step_map[motion_name]
                print(f"    => Chuyển sang bước đơn: [{motion_name}]")

        if motion_name == "VolumeUp":
            _add(1, "volume_up", {})
        elif motion_name == "VolumeDown":
            _add(1, "volume_down", {})
        elif motion_name == "Mute":
            _add(1, "set_volume", {"vol": 0})
        elif motion_name == "Unmute":
            _add(1, "set_volume", {"vol": 50})
        elif motion_name == "StopMusic":
            _add(1, "stop_music", {})
        elif motion_name in ["PlayMusic", "WakaWaka", "MerryChristmas", "HappyBirthday", "WeAreTakingOff"]:
            is_music = (motion_name == "PlayMusic") or any(
                w in chunk_text for w in ["nhạc", "bật", "phát", "chơi", "hát"])
            if is_music:
                track = "WakaWaka"
                if motion_name != "PlayMusic":
                    track = motion_name
                else:
                    if "giáng sinh" in chunk_text or "christmas" in chunk_text:
                        track = "MerryChristmas"
                    elif "sinh nhật" in chunk_text or "birthday" in chunk_text:
                        track = "HappyBirthday"
                    elif "cất cánh" in chunk_text or "taking off" in chunk_text:
                        track = "WeAreTakingOff"
                _add(1, "play_music", {"track": track})
            else:
                _add(1, "sync_play_motion", {"name": motion_name, "repeat": rep})
        elif motion_name in ["RaiseRightHand", "H_WaveRH"]:
            for _ in range(3):
                _add(1, "sync_play_motion", {"name": "RaiseRightHand", "repeat": 1})
                _add(1, "sleep", {"time": 0.5})
                _add(1, "sync_play_motion", {"name": "Reset", "repeat": 1})
                _add(1, "sleep", {"time": 0.5})
        else:
            _add(1, "sync_play_motion", {"name": motion_name, "repeat": rep})

    chunks = re.split(r'\s+(?:rồi|và|sau đó|tiếp tục)\s+', norm_text)
    for chunk in chunks:
        chunk = chunk.strip()
        if not chunk:
            continue
        print(f"   Chunk: '{chunk}'")
        text_num = {"một":"1","hai":"2","ba":"3","bốn":"4","năm":"5",
                    "sáu":"6","bảy":"7","tám":"8","chín":"9","mười":"10"}
        for w, d in text_num.items():
            chunk = re.sub(r'(?<!\w)' + w + r'(?!\w)', d, chunk)
        repeat = 1
        num_match = re.search(r'(\d+)\s*(lần|bước)', chunk)
        if num_match:
            repeat = int(num_match.group(1))
            chunk = chunk.replace(num_match.group(0), "").strip()
        if HAS_RAPIDFUZZ:
            all_phrases, phrase_to_motion = [], {}
            for mn, phrases in MOTION_MAP.items():
                for ph in phrases:
                    all_phrases.append(ph)
                    phrase_to_motion[ph] = mn
            res = process.extractOne(chunk, all_phrases, scorer=fuzz.ratio)
            if res:
                best_match, score, _ = res
                if score >= 60:
                    mn = phrase_to_motion[best_match]
                    print(f"   [Fuzzy] '{best_match}' ({score:.0f}%) → [{mn}]")
                    do_action(mn, chunk, repeat, is_counted=bool(num_match))
                else:
                    print(f"   [Fuzzy] Khớp thấp ({score:.0f}%). Bỏ qua.")
        else:
            executed = False
            for mn, phrases in MOTION_MAP.items():
                for ph in phrases:
                    if ph in chunk:
                        print(f"   [Keyword] '{ph}' → [{mn}]")
                        do_action(mn, chunk, repeat, is_counted=bool(num_match))
                        executed = True
                        break
                if executed:
                    break
            if not executed:
                print("   Không khớp lệnh nào.")

    return commands


def execute_command(text):
    """Standalone mode: xử lý lệnh và đẩy thẳng vào command_queue cục bộ."""
    cmds = collect_commands(text)
    if command_queue:
        for cmd in cmds:
            command_queue.put((cmd["priority"], next(_qc),
                               cmd["source"], cmd["action"], cmd["data"]))


# === PHẦN NÀY GIỮ NGUYÊN ĐỂ TƯƠNG THÍCH STANDALONE MODE ===
def _old_execute_command(text):
    """Xử lý văn bản sau khi chuyển từ giọng nói và phát lệnh tương ứng"""
    text = text.lower()
    print(f"\n[You said]: {text}")
    
    # 0. Lệnh Thoát Chương Trình (Ưu tiên Tuyệt đối #0)
    if any(k in text for k in ["tắt chương trình", "kết thúc chương trình", "thoát chương trình", "đóng chương trình","dừng chương trình"]):
        print("=> Ra lệnh [TẮT HỆ THỐNG] (Exit program)")
        if command_queue:
            command_queue.put((0, next(_qc), "voice", "exit", {}))
        return

    # 1. Lệnh Dừng Nhạc
    if any(k in text for k in ["dừng nhạc", "tắt nhạc",  "dừng phát nhạc","dừng chơi nhạc", "ngừng nhạc",'ngừng phát nhạc',"ngừng chơi nhạc"]):
        print("=> Ra lệnh [DỪNG NHẠC] (Stop music)")
        if command_queue:
            command_queue.put((1, next(_qc), "voice", "stop_music", {}))
        text = re.sub(r'(dừng|tắt|ngừng)\s*(chơi\s*)?nhạc', '', text).strip()
        if not text:
            return

    # 1.5. Lệnh âm lượng theo phần trăm cụ thể
    # Hỗ trợ: "tăng âm lượng 30 phần trăm", "giảm âm lượng 20%", "đặt âm lượng 70 phần trăm"
    vol_text_num = {"một": "1", "hai": "2", "ba": "3", "bốn": "4", "năm": "5",
                    "sáu": "6", "bảy": "7", "tám": "8", "chín": "9", "mười": "10",
                    "hai mươi": "20", "ba mươi": "30", "bốn mươi": "40",
                    "năm mươi": "50", "sáu mươi": "60", "bảy mươi": "70",
                    "tám mươi": "80", "chín mươi": "90", "một trăm": "100"}
    vol_check = text
    for word, digit in vol_text_num.items():
        vol_check = re.sub(r'(?<!\w)' + word + r'(?!\w)', digit, vol_check)

    # Tăng âm lượng X%
    m = re.search(r'tăng\s+âm\s+lượng\s+(\d+)\s*(%|phần\s*trăm)', vol_check)
    if m:
        pct = int(m.group(1))
        print(f"=> Ra lệnh [TĂNG ÂM LƯỢNG {pct}%]")
        if command_queue:
            command_queue.put((1, next(_qc), "voice", "volume_up_by", {"pct": pct}))
        return

    # Giảm âm lượng X%
    m = re.search(r'giảm\s+âm\s+lượng\s+(\d+)\s*(%|phần\s*trăm)', vol_check)
    if m:
        pct = int(m.group(1))
        print(f"=> Ra lệnh [GIẢM ÂM LƯỢNG {pct}%]")
        if command_queue:
            command_queue.put((1, next(_qc), "voice", "volume_down_by", {"pct": pct}))
        return

    # Đặt/chỉnh âm lượng về X%
    m = re.search(r'(?:đặt|chỉnh|set)\s+âm\s+lượng\s+(?:về\s*)?(\d+)\s*(%|phần\s*trăm)', vol_check)
    if m:
        pct = min(100, max(0, int(m.group(1))))
        print(f"=> Ra lệnh [ĐẶT ÂM LƯỢNG = {pct}]")
        if command_queue:
            command_queue.put((1, next(_qc), "voice", "set_volume", {"vol": pct}))
        return

    # 2. Ưu tiên kiểm tra lệnh DỪNG (Stop)
    if "dừng" in text or "thôi" in text or "ngừng" in text:
        print("=> Ra lệnh [DỪNG LẠI] (Stop motion) và Trở về tư thế mặc định")
        if command_queue:
            command_queue.put((1, next(_qc), "voice", "stop_motion", {}))
            command_queue.put((1, next(_qc), "voice", "sync_play_motion", {"name": "Reset", "repeat": 1}))
        return

    # Chuẩn hóa
    norm_text = normalize_text(text)
    print(f"[NLP Normalized]: {norm_text}")
    
    def do_action(motion_name, chunk_text, rep, is_counted=False):
        if is_counted:
            step_map = {
                "Forward": "OneStepForward",
                "Backward": "OneStepBackward",
                "TurnLeft": "OneStepTurnLeft",
                "TurnRight": "OneStepTurnRight"
            }
            if motion_name in step_map:
                motion_name = step_map[motion_name]
                print(f"    => [Tự động chuyển] Lệnh liên tục -> Lệnh đếm bước: [{motion_name}]")

        if not command_queue: return

        if motion_name == "VolumeUp":
            command_queue.put((1, next(_qc), "voice", "volume_up", {}))
            print("    => Đã gửi lệnh tăng âm lượng")
        elif motion_name == "VolumeDown":
            command_queue.put((1, next(_qc), "voice", "volume_down", {}))
            print("    => Đã gửi lệnh giảm âm lượng")
        elif motion_name == "Mute":
            command_queue.put((1, next(_qc), "voice", "set_volume", {"vol": 0}))
            print("    => Đã gửi lệnh tắt âm thanh (Mute)")
        elif motion_name == "Unmute":
            command_queue.put((1, next(_qc), "voice", "set_volume", {"vol": 50}))
            print("    => Đã gửi lệnh bật âm thanh")
        elif motion_name == "StopMusic":
            command_queue.put((1, next(_qc), "voice", "stop_music", {}))
            print("    => Đã gửi lệnh dừng phát nhạc")
        elif motion_name in ["PlayMusic", "WakaWaka", "MerryChristmas", "HappyBirthday", "WeAreTakingOff"]:
            is_music_intent = (motion_name == "PlayMusic") or any(w in chunk_text for w in ["nhạc", "bật", "phát", "chơi", "hát"])
            if is_music_intent:
                target_track = "WakaWaka"
                if motion_name != "PlayMusic":
                    target_track = motion_name
                else:
                    if "giáng sinh" in chunk_text or "christmas" in chunk_text:
                        target_track = "MerryChristmas"
                    elif "sinh nhật" in chunk_text or "birthday" in chunk_text:
                        target_track = "HappyBirthday"
                    elif "cất cánh" in chunk_text or "taking off" in chunk_text:
                        target_track = "WeAreTakingOff"
                
                command_queue.put((1, next(_qc), "voice", "play_music", {"track": target_track}))
                print(f"    => Đang gửi lệnh phát nhạc bài {target_track}")
            else:
                command_queue.put((1, next(_qc), "voice", "sync_play_motion", {"name": motion_name, "repeat": rep}))
        elif motion_name in ["RaiseRightHand", "H_WaveRH"]:
            print("    => Đang thực hiện chuỗi động tác Chào/Tạm biệt (3 lần)")
            for i in range(3):
                command_queue.put((1, next(_qc), "voice", "sync_play_motion", {"name": "RaiseRightHand", "repeat": 1}))
                command_queue.put((1, next(_qc), "voice", "sleep", {"time": 0.5}))  # Chờ 1 giây để tay giơ lên hẳn
                command_queue.put((1, next(_qc), "voice", "sync_play_motion", {"name": "Reset", "repeat": 1}))
                command_queue.put((1, next(_qc), "voice", "sleep", {"time": 0.5}))  # Chờ 1 giây để tay thả xuống hẳn
        else:
            command_queue.put((1, next(_qc), "voice", "sync_play_motion", {"name": motion_name, "repeat": rep}))

    # Tách đa lệnh
    # Tách bằng: "rồi", "và", "sau đó", "tiếp tục"
    chunks = re.split(r'\s+(?:rồi|và|sau đó|tiếp tục)\s+', norm_text)
    
    for chunk in chunks:
        chunk = chunk.strip()
        if not chunk: continue
        
        print(f"\n--- Phân tích lệnh con: '{chunk}' ---")
        
        # Đổi số chữ tiếng Việt sang số để regex tìm được (tiến hai bước -> tiến 2 bước)
        text_num = {"một": "1", "hai": "2", "ba": "3", "bốn": "4", "năm": "5", "sáu": "6", "bảy": "7", "tám": "8", "chín": "9", "mười": "10"}
        for word, digit in text_num.items():
            chunk = re.sub(r'(?<!\w)' + word + r'(?!\w)', digit, chunk)

        # Nhận diện số lượng (e.g. "nhảy 3 lần")
        repeat = 1
        num_match = re.search(r'(\d+)\s*(lần|bước)', chunk)
        if num_match:
            repeat = int(num_match.group(1))
            chunk = chunk.replace(num_match.group(0), "").strip() # Bỏ số lượng đi để bắt chữ cho dễ
            print(f"    [Trích xuất Extractor] Tần suất lặp lại: {repeat}")
            
        # Dò tìm bằng Fuzzy Match (rapidfuzz)
        if HAS_RAPIDFUZZ:
            # Thu thập tất cả các cụm từ tiếng Việt để fuzzy match
            all_phrases = []
            phrase_to_motion = {}
            for motion_name, phrases in MOTION_MAP.items():
                for phrase in phrases:
                    all_phrases.append(phrase)
                    phrase_to_motion[phrase] = motion_name
                    
            match_result = process.extractOne(chunk, all_phrases, scorer=fuzz.ratio)
            
            if match_result:
                best_match, score, _ = match_result
                # Nếu khớp mờ trên 60%
                if score >= 60:
                    motion_name = phrase_to_motion[best_match]
                    print(f"    [Fuzzy Match] Khớp '{best_match}' (Độ chính xác {score:.1f}%) -> Motion: [{motion_name}]")
                    do_action(motion_name, chunk, repeat, is_counted=bool(num_match))
                else:
                    print(f"    [Fuzzy Match] Tỷ lệ khớp quá thấp (Max: {score:.1f}% for '{best_match}'). Lệnh có thể sai.")
            else:
                 print("    => Không tính toán được từ khóa.")
        else:
            # Fallback nếu người dùng chưa kịp cài rapidfuzz
            executed = False
            for motion_name, phrases in MOTION_MAP.items():
                for phrase in phrases:
                    if phrase in chunk:
                        print(f"    [Keyword Fallback] Nhận diện '{phrase}' -> Gửi động tác: [{motion_name}]")
                        do_action(motion_name, chunk, repeat, is_counted=bool(num_match))
                        executed = True
                        break
                if executed:
                    break
            if not executed:
                print("    => Không khớp với cử chỉ nào hỗ trợ.")
        
        # Nghỉ chút nếu có nhiều lệnh con để Robot thực hiện tuần tự
        if len(chunks) > 1:
            time.sleep(1)


# ═══════════════════════════════════════════════════════════
# HÀM SOCKET SERVER — Nhận audio từ mic_client.py
# ═══════════════════════════════════════════════════════════

def _recv_exact(sock: socket.socket, n: int):
    """Đọc đúng n bytes từ socket, trả về None nếu kết nối đứt."""
    data = b""
    while len(data) < n:
        chunk = sock.recv(n - len(data))
        if not chunk:
            return None
        data += chunk
    return data


def handle_client(conn: socket.socket, addr, whisper_model, torch, np):
    """
    Xử lý một client kết nối:
      1. Đọc gói audio (header 4 bytes + payload PCM)
      2. Transcribe bằng Whisper
      3. Gọi execute_command (đẩy lệnh vào command_queue)
      4. Gửi lại text lệnh đã nhận dạng về client
    """
    print(f"\n[Server] Client kết nối: {addr}")
    try:
        while True:
            # ── Đọc header độ dài ────────────────────────────────────────── #
            raw_len = _recv_exact(conn, 4)
            if raw_len is None:
                print(f"[Server] Client {addr} đã ngắt kết nối.")
                break
            payload_len = struct.unpack(">I", raw_len)[0]
            if payload_len == 0:
                continue

            # ── Đọc payload audio ────────────────────────────────────────── #
            pcm_bytes = _recv_exact(conn, payload_len)
            if pcm_bytes is None:
                print(f"[Server] Client {addr} đã ngắt kết nối (giữa payload).")
                break

            print(f"\n[Server] Nhận {payload_len:,} bytes audio từ {addr}. Đang xử lý...")

            # ── Chuyển PCM → float array ─────────────────────────────────── #
            audio_np = (
                np.frombuffer(pcm_bytes, np.int16)
                .flatten()
                .astype(np.float32)
                / 32768.0
            )

            # Bỏ qua nếu âm lượng quá nhỏ (im lặng)
            rms = float(np.sqrt(np.mean(audio_np ** 2)))
            if rms < 0.005:
                print("  (Phát hiện im lặng, bỏ qua)")
                _send_response(conn, "")
                continue

            # ── Transcribe bằng Whisper ──────────────────────────────────── #
            recognized_text = ""
            try:
                result = whisper_model.transcribe(
                    audio_np,
                    language="vi",
                    fp16=torch.cuda.is_available(),
                    condition_on_previous_text=False,
                    initial_prompt="Đây là lệnh điều khiển robot bằng tiếng Việt rõ ràng.",
                )
                recognized_text = result["text"].strip()
            except Exception as e:
                print(f"⚠️ Lỗi Whisper: {e}")

            if recognized_text and len(recognized_text) > 2:
                # Xử lý NLP → lấy danh sách lệnh → gửi JSON về voice_control
                cmds = collect_commands(recognized_text)
            else:
                cmds = []

            # ── Gửi JSON commands về client ──────────────────────────────── #
            _send_response(conn, json.dumps(cmds, ensure_ascii=False))

    except (ConnectionResetError, BrokenPipeError, OSError) as e:
        print(f"[Server] Kết nối với {addr} bị đứt: {e}")
    finally:
        conn.close()
        print(f"[Server] Đã đóng kết nối với {addr}")


def _send_response(conn: socket.socket, text: str):
    """Gửi phản hồi text về client: header 4 bytes + UTF-8 payload."""
    encoded = text.encode("utf-8")
    header  = struct.pack(">I", len(encoded))
    conn.sendall(header + encoded)


# ═══════════════════════════════════════════════════════════
# HÀM CHÍNH
# ═══════════════════════════════════════════════════════════

def start_voice_control(cmd_queue=None, server_mode: bool = False,
                        server_host: str = SERVER_HOST,
                        server_port: int = SERVER_PORT):
    """
    Khởi động hệ thống điều khiển giọng nói.

    Tham số:
        cmd_queue   -- PriorityQueue dùng chung với main_control.py
        server_mode -- True  → Chạy TCP server, nhận audio từ mic_client.py
                       False → Chạy standalone, tự mở mic cục bộ
        server_host -- Địa chỉ IP lắng nghe (server_mode=True)
        server_port -- Cổng TCP (server_mode=True)
    """
    global command_queue
    command_queue = cmd_queue

    print("\n[Hệ thống] Đang tải mô hình AI Whisper... Vui lòng đợi.")
    import torch
    import whisper
    import numpy as np

    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"    -> Đang chạy trên: {device.upper()}")

    try:
        whisper_model = whisper.load_model("large-v3", device=device)
        print("    -> Tải model thành công!")
    except Exception as e:
        print(f"    -> Lỗi khi tải Whisper: {e}")
        return

    print("="*60)
    print(" ROBOT YANSHEE: ĐIỀU KHIỂN BẰNG GIỌNG NÓI (NLP TỐI ƯU)")
    print("="*60)
    print(" 🔥 Hỗ trợ Đa lệnh (Multi-command split) & Fuzzy Matching")
    if not HAS_RAPIDFUZZ:
        print(" ⚠️  CHÚ Ý: Chưa cài `rapidfuzz`. Fallback keyword matching.")
        print("    Hãy gõ: pip install rapidfuzz")
    print("="*60)

    # ════════════════════════════════════════════════════════
    # CHẾ ĐỘ SERVER — nhận audio từ mic_client.py
    # ════════════════════════════════════════════════════════
    if server_mode:
        print(f"\n[Server] Chạy ở chế độ SERVER trên {server_host}:{server_port}")
        print("[Server] Chờ mic_client.py kết nối...")
        print("-"*60)

        srv_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv_sock.bind((server_host, server_port))
        srv_sock.listen(5)

        try:
            while True:
                conn, addr = srv_sock.accept()
                # Mỗi client chạy trên một thread riêng
                t = threading.Thread(
                    target=handle_client,
                    args=(conn, addr, whisper_model, torch, np),
                    daemon=True,
                )
                t.start()
        except KeyboardInterrupt:
            print("\n[Server] Đã nhận Ctrl+C. Đang tắt server...")
        finally:
            srv_sock.close()
        return

    # ════════════════════════════════════════════════════════
    # CHẾ ĐỘ STANDALONE — tự mở mic cục bộ (giữ nguyên logic cũ)
    # ════════════════════════════════════════════════════════
    recognizer = sr.Recognizer()
    recognizer.energy_threshold        = 400
    recognizer.dynamic_energy_threshold = True
    recognizer.pause_threshold         = 0.8

    try:
        microphone = sr.Microphone()
        print("[Hệ thống] Đang kiểm tra tạp âm môi trường... Vui lòng đợi.")
        with microphone as source:
            recognizer.adjust_for_ambient_noise(source, duration=1.5)
        print("[Hệ thống] Cài đặt xong! Sẵn sàng lắng nghe.")
        print("-"*60)
    except OSError as e:
        print(f"\n[Lỗi] Không tìm thấy Microphone: {e}")
        return

    while True:
        try:
            with microphone as source:
                print("\n🎤 Đang nghe... (Ctrl+C để thoát)")
                audio = recognizer.listen(source, timeout=6, phrase_time_limit=8)

            print("⏳ Đang xử lý âm thanh AI...")

            try:
                wav_bytes = audio.get_raw_data(convert_rate=16000, convert_width=2)
                audio_np  = np.frombuffer(wav_bytes, np.int16).flatten().astype(np.float32) / 32768.0

                rms = np.sqrt(np.mean(audio_np**2))
                if rms < 0.005:
                    continue

                result = whisper_model.transcribe(
                    audio_np,
                    language="vi",
                    fp16=torch.cuda.is_available(),
                    condition_on_previous_text=False,
                    initial_prompt="Đây là lệnh điều khiển robot bằng tiếng Việt rõ ràng.",
                )

                text = result["text"].strip()
                if not text or len(text) <= 2:
                    continue

            except Exception as e:
                print(f"⚠️ Lỗi xử lý âm thanh AI: {e}")
                continue

            execute_command(text)

        except sr.WaitTimeoutError:
            pass
        except KeyboardInterrupt:
            print("\n[Hệ thống] Đã nhận Ctrl+C. Đang tắt chương trình...")
            break
        except Exception as e:
            print(f"Lỗi hệ thống: {e}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Whisper Voice Server / Standalone cho Robot Yanshee"
    )
    parser.add_argument(
        "--server",
        action="store_true",
        default=True,
        help="Chạy ở chế độ TCP server (nhận audio từ mic_client.py). Mặc định: BẬT",
    )
    parser.add_argument(
        "--standalone",
        action="store_true",
        default=False,
        help="Chạy độc lập với microphone cục bộ (chế độ cũ)",
    )
    parser.add_argument(
        "--host",
        default=SERVER_HOST,
        help=f"Địa chỉ IP lắng nghe (mặc định: {SERVER_HOST})",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=SERVER_PORT,
        help=f"Cổng TCP (mặc định: {SERVER_PORT})",
    )
    args = parser.parse_args()

    use_server = args.server and not args.standalone
    start_voice_control(
        server_mode=use_server,
        server_host=args.host,
        server_port=args.port,
    )
