import speech_recognition as sr
import time
import re
from YanAPI import YanAPI

try:
    from rapidfuzz import process, fuzz
    HAS_RAPIDFUZZ = True
except ImportError:
    HAS_RAPIDFUZZ = False

# ==========================================
# CẤU HÌNH IP
# ==========================================
ROBOT_IP = "192.168.91.75"  # IP thực tế của Yanshee
robot = YanAPI(ip_address=ROBOT_IP)

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
    "PuchUp": {
        "hít đất", "hít đất đi", "hít đất lên", "hít đất đi lên"
    },
    "GetUp": {
        "Tập thể dục", "tập thể dục đi", "tập thể dục lên", "tập thể dục đi lên"
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
        "tắt âm thanh", "im lặng", "mute"
    },

    "Unmute": {
        "bật âm thanh", "mở tiếng"
    },
}
def normalize_text(text):
    """Lọc rác và chuẩn hóa văn bản"""
    # Xóa dấu câu
    text = re.sub(r'[^\w\s]', '', text)
    # Bỏ stop-words
    stopwords = ["robot", "ơi", "làm ơn", "hãy", "cho tôi", "nhé", "nha", "đi", "thực hiện"]
    words = text.split()
    words = [w for w in words if w not in stopwords]
    return " ".join(words)

def execute_command(text):
    """Xử lý văn bản sau khi chuyển từ giọng nói và phát lệnh tương ứng"""
    text = text.lower()
    print(f"\n[You said]: {text}")
    
    # 0. Lệnh Dừng Nhạc ưu tiên cao nhất
    if any(k in text for k in ["dừng nhạc", "tắt nhạc",  "dừng phát nhạc","dừng chơi nhạc", "ngừng nhạc"]):
        print("=> Ra lệnh [DỪNG NHẠC] (Stop music)")
        robot.stop_music()
        text = re.sub(r'(dừng|tắt|ngừng)\s*(chơi\s*)?nhạc', '', text).strip()
        if not text:
            return

    # 1. Ưu tiên kiểm tra lệnh DỪNG (Stop)
    if "dừng" in text or "thôi" in text or "ngừng" in text:
        print("=> Ra lệnh [DỪNG LẠI] (Stop motion) và Trở về tư thế mặc định")
        robot.stop_motion()
        time.sleep(0.5)  # Chờ nửa giây để xử lý xong lệnh ngắt
        robot.sync_play_motion(name="Reset")
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

        if motion_name == "VolumeUp":
            vol_resp = robot.get_device_volume()
            curr_vol = vol_resp.get("data", {}).get("volume", 50) if isinstance(vol_resp, dict) else 50
            new_vol = min(100, curr_vol + 15)
            robot.set_device_volume(new_vol)
            print(f"    => Đã tăng âm lượng lên {new_vol}")
        elif motion_name == "VolumeDown":
            vol_resp = robot.get_device_volume()
            curr_vol = vol_resp.get("data", {}).get("volume", 50) if isinstance(vol_resp, dict) else 50
            new_vol = max(0, curr_vol - 15)
            robot.set_device_volume(new_vol)
            print(f"    => Đã giảm âm lượng xuống {new_vol}")
        elif motion_name == "Mute":
            robot.set_device_volume(0)
            print("    => Đã tắt âm thanh (Mute)")
        elif motion_name == "Unmute":
            robot.set_device_volume(50)
            print("    => Đã bật âm thanh")
        elif motion_name == "StopMusic":
            robot.stop_music()
            print("    => Đã dừng phát nhạc")
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
                
                robot.play_music(target_track)
                print(f"    => Đang phát nhạc bài {target_track}")
            else:
                robot.sync_play_motion(name=motion_name, repeat=rep)
        elif motion_name in ["RaiseRightHand", "H_WaveRH"]:
            print("    => Đang thực hiện chuỗi động tác Chào/Tạm biệt (3 lần)")
            for i in range(3):
                robot.sync_play_motion(name="RaiseRightHand")
                time.sleep(0.5)
                robot.sync_play_motion(name="Reset")
                time.sleep(0.5)
        else:
            robot.sync_play_motion(name=motion_name, repeat=rep)

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


def start_voice_control():
    """Khởi động hệ thống nhận diện giọng nói liên tục"""
    
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

    # Khởi tạo recognizer để phân tích giọng nói
    recognizer = sr.Recognizer()
    
    # --- Tuning Khử ồn và Cấu hình bắt tín hiệu (Acoustic Tuning) ---
    recognizer.energy_threshold = 400
    recognizer.dynamic_energy_threshold = True
    recognizer.pause_threshold = 0.8
    # -----------------------------------------------------------------
    
    print("="*60)
    print(" ROBOT YANSHEE: ĐIỀU KHIỂN BẰNG GIỌNG NÓI (NLP TỐI ƯU)")
    print("="*60)
    print(" 🔥 Hỗ trợ Đa lệnh (Multi-command split) & Fuzzy Matching")
    if not HAS_RAPIDFUZZ:
         print(" ⚠️ CHÚ Ý: Chưa cài thư viện `rapidfuzz`. Không thể kháng nhiễu từ vựng.")
         print("    Hãy gõ: pip install rapidfuzz")
    print("="*60)

    try:
        # Sử dụng microphone hệ thống
        microphone = sr.Microphone()
        
        print("[Hệ thống] Đang kiểm tra tạp âm môi trường... Vui lòng đợi.")
        with microphone as source:
            recognizer.adjust_for_ambient_noise(source, duration=1.5)
            
        print("[Hệ thống] Cài đặt xong! Sẵn sàng lắng nghe.")
        print("-"*60)
        
    except OSError as e:
        print(f"\n[Lỗi] Không tìm thấy Microphone trên máy tính của bạn!")
        print(f"Chi tiết: {e}")
        return

    while True:
        try:
            with microphone as source:
                print("\n🎤 Đang nghe... (Ctr+C để thoát)")
                # Tăng giới hạn đệm nghe (Timeout) để ổn định hơn
                audio = recognizer.listen(source, timeout=6, phrase_time_limit=8)
            
            print("⏳ Đang xử lý âm thanh AI...")
            
            try:
                # Chuyển đổi chuẩn hóa âm thanh sang dạng Float Array cho AI
                wav_bytes = audio.get_raw_data(convert_rate=16000, convert_width=2)
                audio_np = np.frombuffer(wav_bytes, np.int16).flatten().astype(np.float32) / 32768.0

                # Lọc năng lượng, triệt tiêu tạp âm quạt gió (ngăn ảo giác chép sai của Whisper)
                rms = np.sqrt(np.mean(audio_np**2))
                if rms < 0.005:
                    continue

                result = whisper_model.transcribe(
                    audio_np, 
                    language="vi",    # Khóa chặt chỉ nghe Tiếng Việt
                    fp16=torch.cuda.is_available(),
                    condition_on_previous_text=False, # Không cho phép máy tự lặp lại từ cũ sai
                    initial_prompt="Đây là lệnh điều khiển robot bằng tiếng Việt rõ ràng." 
                )
                
                text = result["text"].strip()
                if not text or len(text) <= 2:
                    continue
                    
            except Exception as e:
                print(f"⚠️ Lỗi xử lý âm thanh AI: {e}")
                continue
            
            # Gọi xử lý điều khiển Robot Yanshee
            execute_command(text)
            
        except sr.WaitTimeoutError:
            pass 
        except KeyboardInterrupt:
            print("\n[Hệ thống] Đã nhận lệnh ngắt Ctr+C. Đang tắt chương trình...")
            break
        except Exception as e:
            print(f"Lỗi hệ thống: {e}")


if __name__ == "__main__":
    start_voice_control()
