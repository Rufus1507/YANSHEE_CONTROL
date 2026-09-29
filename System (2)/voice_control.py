"""
c:\System\voice_control.py  —  System/
==============================
Nhiệm vụ:
  1. Sử dụng microphone cục bộ (SpeechRecognition)
  2. Nhận dạng giọng nói tiếng Việt bằng Google Speech Recognition API (Miễn phí, cực kỳ nhẹ)
  3. Xử lý đa lệnh (Multi-command split) và Fuzzy Matching (Rapidfuzz) trực tiếp
  4. Đẩy lệnh trực tiếp vào command_queue của main_control.py
"""

import os
import sys
import re
import time
import struct
import itertools
import unicodedata
import speech_recognition as sr

# Thử import rapidfuzz để tăng khả năng nhận diện
try:
    from rapidfuzz import process, fuzz
    HAS_RAPIDFUZZ = True
except ImportError:
    HAS_RAPIDFUZZ = False

# Fix encoding console Windows
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
try:
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

_qc = itertools.count()

STOPWORDS = [
    "robot", "ơi", "làm ơn", "hãy", "cho tôi", "nhé", "nha",
    "đi", "thực hiện", "nói", "bạn", "xin", "nhé", "giúp", "làm ơn"
]
NUMBER_WORDS = {
    "một": "1", "hai": "2", "ba": "3", "bốn": "4", "năm": "5",
    "sáu": "6", "bảy": "7", "tám": "8", "chín": "9", "mười": "10",
    "hai mươi": "20", "ba mươi": "30", "bốn mươi": "40", "năm mươi": "50",
    "sáu mươi": "60", "bảy mươi": "70", "tám mươi": "80", "chín mươi": "90",
    "một trăm": "100"
}

# ==============================================================================
# TỪ ĐIỂN ÁNH XẠ: Từ khóa (Tiếng Việt) -> Tên Motion (YanAPI)
# ==============================================================================
MOTION_MAP = {
    "RaiseRightHand": {
        "giơ tay lên", "giơ tay", "tạm biệt"
    },
    "H_WaveRH": {
        "vẫn tay", "wave", "tạm biệt", "bye", "goodbye"
    },
    "Hug": {
        "ôm", "ôm đi"
    },
    # ================== DI CHUYỂN ==================
    "Forward": {
        "tiến", "tiến lên", "đi tới", "đi lên", "forward", "go forward", "tới", "lên"
    },
    "Backward": {
        "lùi", "đi lùi", "lùi lại", "bước lui", "back", "go back"
    },
    "TurnLeft": {
        "rẽ trái", "quay trái", "left", "turn left"
    },
    "TurnRight": {
        "rẽ phải", "quay phải", "right", "turn right"
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
        "nghỉ", "nghỉ ngơi", "nghỉ ngơi đi", "tiết kiệm năng lượng", "vào chế độ tiết kiệm năng lượng"
    },
    "ExitEnergySavingReset": {
        "dừng nghỉ", "dừng nghỉ đi", "dừng nghỉ ngơi", "thoát tiết kiệm năng lượng", "thoát chế độ tiết kiệm năng lượng"
    },
    # ================== ÂM THANH / NHẠC ==================
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
        "cất cánh", "cất cánh thôi", "cất cánh đi", "cất cánh lên", "We Are Taking Off"
    },
    "Victory": {
        "xin chào", "ăn mừng", "chào", "hi", "hello", "hey", "hey robot"
    },
    "GetupFront": {
        "ngã sấp đứng dậy", "ngã sấp đứng lên", "ngã sấp đứng dậy đi", "ngã sấp đứng dậy lên", "nằm sấp đứng dậy", "nằm sấp đứng lên", "nằm sấp đứng dậy đi", "nằm sấp đứng dậy lên", "lật lại", "lật người"
    },
    "GetupRear": {
        "ngã ngửa đứng dậy", "ngã ngửa đứng lên", "ngã ngửa đứng dậy đi", "ngã ngửa đứng dậy lên", "nằm ngửa đứng dậy", "nằm ngửa đứng lên", "nằm ngửa đứng dậy đi", "nằm ngửa đứng dậy lên", "ngồi dậy", "đứng dậy", "đứng lên"
    },
    "PushUp": {
        "hít đất", "hít đất đi", "hít đất lên", "hít đất đi lên", "chống đẩy", "chống đẩy đi", "chống đẩy lên", "chống đẩy đi lên"
    },
    "GetUp": {
        "Tập thể dục", "tập thể dục đi", "tập thể dục lên", "tập thể dục đi lên"
    },
    # ================== BÓNG ĐÁ ==================
    "Football_LKick": {
        "sút trái", "đá trái", "sút chân trái", "đá chân trái"
    },
    "Football_RKick": {
        "sút phải", "đá phải", "sút chân phải", "đá chân phải"
    },
    "Football_LShoot": {
        "dứt điểm trái", "sút mạnh trái", "sút bóng trái", "sút banh trái", "sút banh"
    },
    "Football_RShoot": {
        "dứt điểm phải", "sút mạnh phải", "sút bóng phải", "sút bóng", "đá bóng", "đá banh", "sút banh phải"
    },
    "GoalKeeper1": {
        "bắt bóng", "thủ môn bắt bóng", "bảo vệ khung thành", "bắt banh"
    },
    "GoalKeeper2": {
        "bắt bóng trên", "chuẩn bị bắt bóng", "thủ môn", "bắt banh trên"
    },
    "Football_LKeep": {
        "bắt bóng trái", "đổ người bên trái", "đổ người trái", "bắt banh trái"
    },
    "Football_RKeep": {
        "bắt bóng phải", "đổ người bên phải", "đổ người phải", "bắt banh phải"
    },
    "LeftTackle": {
        "xoạc bóng trái", "cướp bóng trái", "xoạc banh trái"
    },
    "RightTackle": {
        "xoạc bóng phải", "cướp bóng phải", "xoạc bóng", "xoạc banh phải"
    },
    "Left slide tackle": {
        "chồi bóng trái", "trượt bóng trái", "xoạc banh trái"
    },
    # ================== CHIẾN ĐẤU ==================
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
        "tắt âm thanh", "im lặng", "mute", "tắt tiếng", "tắt tiếng đi", "tắt tiếng lên"
    },
    "Unmute": {
        "bật âm thanh", "mở tiếng"
    },
}

def strip_accents(text: str) -> str:
    """Chuyển ký tự có dấu về không dấu để tăng độ bền khi so khớp."""
    text = unicodedata.normalize("NFD", text)
    return "".join(ch for ch in text if unicodedata.category(ch) != "Mn")


def normalize_text(text: str, strip=False) -> str:
    """Lọc các từ thừa, chuẩn hóa và chuyển số chữ sang số."""
    text = text.lower()
    text = re.sub(r'[^\w\s]', ' ', text)
    for word in STOPWORDS:
        text = text.replace(word, " ")
    for word, digit in sorted(NUMBER_WORDS.items(), key=lambda item: len(item[0]), reverse=True):
        text = re.sub(r'(?<!\w)' + re.escape(word) + r'(?!\w)', digit, text)
    text = " ".join(text.split())
    if strip:
        return strip_accents(text)
    return text


def _compute_rms_from_audio(audio) -> float:
    """Tính RMS chuẩn hóa của PCM để bỏ qua đoạn ghi âm gần như im lặng."""
    raw_data = audio.get_raw_data(convert_width=2)
    if not raw_data:
        return 0.0
    sample_count = len(raw_data) // 2
    samples = struct.unpack(f"<{sample_count}h", raw_data[:sample_count * 2])
    return (sum(sample * sample for sample in samples) / sample_count) ** 0.5 / 32768.0


def collect_commands(text: str) -> list:
    """Xử lý ngôn ngữ tự nhiên, tách đa lệnh và khớp từ khóa bằng Fuzzy Match"""
    commands = []
    text = text.lower().strip()
    if not text:
        return commands

    print(f"\n[NLP] Phân tích lệnh: '{text}'")

    def _add(priority, action, data):
        commands.append({"priority": priority, "source": "voice", "action": action, "data": data})

    # 0. Lệnh tắt chương trình
    if any(k in text for k in ["tắt chương trình", "kết thúc chương trình", "thoát chương trình", "đóng chương trình", "dừng chương trình"]):
        print("=> [Hệ thống] Ra lệnh TẮT HỆ THỐNG")
        _add(0, "exit", {})
        return commands

    # 1. Dừng nhạc
    if any(k in text for k in ["dừng nhạc", "tắt nhạc", "dừng phát nhạc", "dừng chơi nhạc", "ngừng nhạc"]):
        print("=> [Âm thanh] Dừng nhạc")
        _add(1, "stop_music", {})
        text = re.sub(r'(dừng|tắt|ngừng)\s*(chơi\s*)?nhạc', '', text).strip()
        if not text:
            return commands

    # 1.5. Lệnh chỉnh âm lượng cụ thể
    _nw = {"một":"1","hai":"2","ba":"3","bốn":"4","năm":"5","sáu":"6","bảy":"7","tám":"8","chín":"9","mười":"10",
           "hai mươi":"20","ba mươi":"30","bốn mươi":"40","năm mươi":"50","sáu mươi":"60","bảy mươi":"70","tám mươi":"80","chín mươi":"90","một trăm":"100"}
    vt = text
    for w, d in sorted(_nw.items(), key=lambda item: len(item[0]), reverse=True):
        vt = re.sub(r'(?<!\w)' + w + r'(?!\w)', d, vt)

    # Tăng âm lượng X%
    m = re.search(r'tăng\s+âm\s+lượng\s+(\d+)\s*(%|phần\s*trăm)', vt)
    if m:
        pct = int(m.group(1))
        _add(1, "volume_up_by", {"pct": pct})
        return commands

    # Giảm âm lượng X%
    m = re.search(r'giảm\s+âm\s+lượng\s+(\d+)\s*(%|phần\s*trăm)', vt)
    if m:
        pct = int(m.group(1))
        _add(1, "volume_down_by", {"pct": pct})
        return commands

    # Set âm lượng X%
    m = re.search(r'(?:đặt|chỉnh|set)\s+âm\s+lượng\s+(?:về\s*)?(\d+)\s*(%|phần\s*trăm)', vt)
    if m:
        pct = min(100, max(0, int(m.group(1))))
        _add(1, "set_volume", {"vol": pct})
        return commands

    # 2. Lệnh dừng khẩn cấp
    if any(k in text for k in ["dừng", "thôi", "ngừng"]):
        _add(1, "stop_motion", {})
        _add(1, "sync_play_motion", {"name": "Reset", "repeat": 1})
        return commands

    # 3. Chuẩn hóa và lọc đa lệnh
    norm_text = normalize_text(text)

    def do_action(motion_name, chunk_text, rep, is_counted=False):
        if is_counted:
            step_map = {"Forward": "OneStepForward", "Backward": "OneStepBackward",
                        "TurnLeft": "OneStepTurnLeft", "TurnRight": "OneStepTurnRight"}
            if motion_name in step_map:
                motion_name = step_map[motion_name]

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
            track = motion_name if motion_name != "PlayMusic" else "WakaWaka"
            if motion_name == "PlayMusic":
                if "giáng sinh" in chunk_text or "christmas" in chunk_text:
                    track = "MerryChristmas"
                elif "sinh nhật" in chunk_text or "birthday" in chunk_text:
                    track = "HappyBirthday"
                elif "cất cánh" in chunk_text or "taking off" in chunk_text:
                    track = "WeAreTakingOff"
            _add(1, "play_music", {"track": track})
        elif motion_name in ["RaiseRightHand", "H_WaveRH"]:
            # Giơ tay chào 3 lần tuần tự
            for _ in range(3):
                _add(1, "sync_play_motion", {"name": "RaiseRightHand", "repeat": 1})
                _add(1, "sleep", {"time": 0.5})
                _add(1, "sync_play_motion", {"name": "Reset", "repeat": 1})
                _add(1, "sleep", {"time": 0.5})
        else:
            _add(1, "sync_play_motion", {"name": motion_name, "repeat": rep})

    # Tách các liên từ để thực hiện chuỗi lệnh (Ví dụ: "tiến lên 2 bước rồi ôm")
    chunks = re.split(r'\s+(?:rồi|và|sau đó|tiếp tục)\s+', norm_text)
    for chunk in chunks:
        chunk = chunk.strip()
        if not chunk:
            continue
        
        # Đổi số chữ sang số
        text_num = {"một":"1","hai":"2","ba":"3","bốn":"4","năm":"5","sáu":"6","bảy":"7","tám":"8","chín":"9","mười":"10"}
        for w, d in text_num.items():
            chunk = re.sub(r'(?<!\w)' + w + r'(?!\w)', d, chunk)
            
        repeat = 1
        num_match = re.search(r'(\d+)\s*(lần|bước)', chunk)
        if num_match:
            repeat = int(num_match.group(1))
            chunk = chunk.replace(num_match.group(0), "").strip()

        # Dùng Fuzzy Match để chống nhiễu
        chunk_norm = normalize_text(chunk, strip=True)
        exact_match = False
        # Ưu tiên khớp chính xác trên phiên bản không dấu
        for mn, phrases in MOTION_MAP.items():
            for ph in phrases:
                if strip_accents(ph.lower()) in chunk_norm:
                    print(f"   [Exact Match] Khớp '{ph}' -> Lệnh: [{mn}]")
                    do_action(mn, chunk, repeat, is_counted=bool(num_match))
                    exact_match = True
                    break
            if exact_match:
                break

        if exact_match:
            continue

        if HAS_RAPIDFUZZ:
            all_phrases, phrase_to_motion = [], {}
            for mn, phrases in MOTION_MAP.items():
                for ph in phrases:
                    norm_ph = strip_accents(ph.lower())
                    all_phrases.append(norm_ph)
                    phrase_to_motion[norm_ph] = mn
            res = process.extractOne(chunk_norm, all_phrases, scorer=fuzz.token_set_ratio)
            if res:
                best_match, score, _ = res
                threshold = 60 if len(chunk_norm) < 20 else 65
                if score >= threshold:
                    mn = phrase_to_motion[best_match]
                    print(f"   [Fuzzy Match] Khớp '{best_match}' ({score:.0f}%) -> Lệnh: [{mn}]")
                    do_action(mn, chunk, repeat, is_counted=bool(num_match))
                else:
                    print(f"   [Fuzzy Match] Không tìm thấy từ khóa trùng khớp (Max: {score:.0f}%)")
        else:
            # Fallback nếu không có rapidfuzz
            executed = False
            for mn, phrases in MOTION_MAP.items():
                for ph in phrases:
                    if strip_accents(ph.lower()) in chunk_norm:
                        print(f"   [Keyword Match] Khớp '{ph}' -> Lệnh: [{mn}]")
                        do_action(mn, chunk, repeat, is_counted=bool(num_match))
                        executed = True
                        break
                if executed:
                    break
            if not executed:
                print("   [Keyword Match] Không tìm thấy cử chỉ nào tương thích.")
                
    return commands

# ==============================================================================
# HÀM BẮT ĐẦU LUỒNG GIỌNG NÓI (Called by main_control.py)
# ==============================================================================
def start_voice_control(cmd_queue=None):
    """Khởi động luồng Voice Control độc lập chạy offline bằng Google Speech API"""
    print("\n" + "═"*50)
    print("  🎤 VOICE CONTROL  (RMS Noise Gate + Google API)")
    print("  🔥 Kháng nhiễu từ vựng: " + ("BẬT (Fuzz)" if HAS_RAPIDFUZZ else "TẮT"))
    print("  🔥 Phương thức: Local Mic + Google Speech API")
    print("═"*50)

    recognizer = sr.Recognizer()
    recognizer.energy_threshold = 400
    recognizer.dynamic_energy_threshold = True
    recognizer.pause_threshold = 0.8

    try:
        microphone = sr.Microphone()
        print("[VoiceCtrl] Đang đo tạp âm môi trường (1.5s)... Vui lòng giữ im lặng.")
        with microphone as source:
            recognizer.adjust_for_ambient_noise(source, duration=1.5)
        print("[VoiceCtrl] Cân bằng môi trường thành công! Bắt đầu lắng nghe...")
    except OSError as e:
        print(f"[VoiceCtrl] ❌ Lỗi microphone cục bộ: {e}")
        return

    while not getattr(cmd_queue, "shutdown_requested", False):
        try:
            with microphone as source:
                print("\n🎤 Đang nghe lệnh... (Nói đi)")
                audio = recognizer.listen(source, timeout=6, phrase_time_limit=8)

            rms = _compute_rms_from_audio(audio)
            if rms < 0.008:
                print(f"[VoiceCtrl] Bỏ qua âm thanh quá nhỏ (RMS={rms:.4f})")
                continue

            print("⏳ Đang xử lý giọng nói cục bộ...")
            try:
                # Dùng Google Speech Recognition API miễn phí, hỗ trợ tiếng Việt cực chuẩn
                text = recognizer.recognize_google(audio, language="vi-VN")
                print(f"[VoiceCtrl] Transcribed: \"{text}\"")
                
                if text and len(text.strip()) > 1:
                    cmds = collect_commands(text)
                    if cmds and cmd_queue:
                        for cmd in cmds:
                            cmd_queue.put((
                                cmd["priority"],
                                next(_qc),
                                cmd["source"],
                                cmd["action"],
                                cmd["data"]
                            ))
                        if any(cmd["priority"] == 1 for cmd in cmds):
                            cmd_queue.voice_is_busy = True
                        print(f"✅ Đã gửi {len(cmds)} lệnh vào hệ thống.")
            except sr.UnknownValueError:
                # Không phát hiện giọng nói rõ ràng
                pass
            except sr.RequestError as e:
                print(f"⚠️ Lỗi kết nối Google Speech API: {e}")
                time.sleep(1)

        except sr.WaitTimeoutError:
            pass
        except KeyboardInterrupt:
            print("\n[VoiceCtrl] Dừng luồng giọng nói.")
            break
        except Exception as e:
            print(f"[VoiceCtrl] Có lỗi xảy ra: {e}")
            time.sleep(0.5)

if __name__ == "__main__":
    start_voice_control()
