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
ROBOT_IP = "10.176.138.75"  # IP thực tế của Yanshee
robot = YanAPI(ip_address=ROBOT_IP)

# ==========================================
# TỪ ĐIỂN ÁNH XẠ: Từ khóa (Tiếng Việt) -> Tên Motion
# ==========================================
# Lưu ý: Các tên "SayHello", "RaiseRightHand", "Bow", "WakaWaka" là
# những action tiêu chuẩn phổ biến trên robot Yanshee. 
# Nếu Robot báo không tìm thấy, bạn có thể kiểm tra lại tên đúng nhờ hàm danh sách.
MOTION_MAP = {
    # ================== CHÀO HỎI / GIAO TIẾP ==================
    "chào": "RaiseRightHand",
    "xin chào": "RaiseRightHand",
    "hello": "RaiseRightHand",
    "hi": "RaiseRightHand",
    "vẫy tay": "H_WaveRH",
    "tạm biệt": "H_WaveRH",
    "ôm": "Hug",

    # ================== DI CHUYỂN ==================
    "tiến": "Forward",
    "đi tới": "Forward",
    "tiến lên": "Forward",
    "lùi": "Backward",
    "đi lùi": "Backward",

    "rẽ trái": "TurnLeft",
    "quay trái": "TurnLeft",
    "rẽ phải": "TurnRight",
    "quay phải": "TurnRight",

    "bước tới": "OneStepForward",
    "bước lùi": "OneStepBackward",
    "xoay trái một bước": "OneStepTurnLeft",
    "xoay phải một bước": "OneStepTurnRight",

    "đi nhanh": "Move_fast",
    "dừng": "Stop",
    "stop": "Stop",

    "reset": "Reset",
    "đứng thẳng": "Reset",

    # ================== TIẾT KIỆM NĂNG LƯỢNG ==================
    "ngồi": "EnterEnergySavingSquat",
    "ngồi xuống": "EnterEnergySavingSquat",
    "đứng lên": "ExitEnergySavingReset",

    # ================== BÓNG ĐÁ ==================
    "sút": "Football_RKick",
    "sút trái": "Football_LKick",
    "sút phải": "Football_RKick",

    "thủ môn": "GoalKeeper1",
    "cản bóng": "Football_LKeep",

    "xoạc": "LeftTackle",

    # ================== CHIẾN ĐẤU ==================
    "đấm": "RightSidePunch",
    "đấm trái": "LeftSidePunch",
    "đấm phải": "RightSidePunch",

    "đánh": "Fight_RHit",
    "đánh trái": "Fight_LHit",
    "đánh phải": "Fight_RHit",

    # ================== THỂ DỤC ==================
    "hít đất": "PushUp",
    "chống đẩy": "PushUp",
    "tập thể dục": "PushUp",

    # ================== NHẢY / ÂM NHẠC ==================
    "nhảy": "WakaWaka",
    "nhảy waka": "WakaWaka",
    "waka": "WakaWaka",

    "giáng sinh": "MerryChristmas",
    "sinh nhật": "HappyBirthday",

    # ================== CẢM XÚC ==================
    "chiến thắng": "Victory",
    "ăn mừng": "Victory",

    # ================== HỒI PHỤC ==================
    "đứng dậy": "GetUp",
    "ngã sấp đứng dậy": "GetupFront",
    "ngã ngửa đứng dậy": "GetupRear",

    # ================== ĐẦU ==================
    "nhìn trái": "Hd_Wacth_L",
    "nhìn phải": "Hd_Wacth_R",
    "xoay đầu": "Hd_SwivelH",

    # ================== TAY ==================
    "giơ tay phải": "H_Rise_R",
    "giơ tay trái": "H_Rise_L",

    # ================== DI CHUYỂN NGANG ==================
    "qua trái": "OneStepMoveLeft",
    "qua phải": "OneStepMoveRight"
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
    
    # Tách đa lệnh
    # Tách bằng: "rồi", "và", "sau đó", "tiếp tục"
    chunks = re.split(r'\s+(?:rồi|và|sau đó|tiếp tục)\s+', norm_text)
    
    for chunk in chunks:
        chunk = chunk.strip()
        if not chunk: continue
        
        print(f"\n--- Phân tích lệnh con: '{chunk}' ---")
        
        # Nhận diện số lượng (e.g. "nhảy 3 lần")
        repeat = 1
        num_match = re.search(r'(\d+)\s*(lần|bước)', chunk)
        if num_match:
            repeat = int(num_match.group(1))
            chunk = chunk.replace(num_match.group(0), "").strip() # Bỏ số lượng đi để bắt chữ cho dễ
            print(f"    [Trích xuất Extractor] Tần suất lặp lại: {repeat}")
            
        # Dò tìm bằng Fuzzy Match (rapidfuzz)
        if HAS_RAPIDFUZZ:
            keywords = list(MOTION_MAP.keys())
            match_result = process.extractOne(chunk, keywords, scorer=fuzz.ratio)
            
            if match_result:
                best_match, score, _ = match_result
                # Nếu khớp mờ trên 60%
                if score >= 60:
                    motion = MOTION_MAP[best_match]
                    print(f"    [Fuzzy Match] Khớp '{best_match}' (Độ chính xác {score:.1f}%) -> Motion: [{motion}]")
                    robot.sync_play_motion(name=motion, repeat=repeat)
                else:
                    print(f"    [Fuzzy Match] Tỷ lệ khớp quá thấp (Max: {score:.1f}% for '{best_match}'). Lệnh có thể sai.")
            else:
                 print("    => Không tính toán được từ khóa.")
        else:
            # Fallback nếu người dùng chưa kịp cài rapidfuzz
            executed = False
            for keyword, motion in MOTION_MAP.items():
                if keyword in chunk:
                    print(f"    [Keyword Fallback] Nhận diện '{keyword}' -> Gửi động tác: [{motion}]")
                    robot.sync_play_motion(name=motion, repeat=repeat)
                    executed = True
                    break
            if not executed:
                print("    => Không khớp với cử chỉ nào hỗ trợ.")
        
        # Nghỉ chút nếu có nhiều lệnh con để Robot thực hiện tuần tự
        if len(chunks) > 1:
            time.sleep(1)


def start_voice_control():
    """Khởi động hệ thống nhận diện giọng nói liên tục"""
    
    # Khởi tạo recognizer để phân tích giọng nói
    recognizer = sr.Recognizer()
    
    # --- Tuning Khử ồn và Cấu hình bắt tín hiệu (Acoustic Tuning) ---
    recognizer.energy_threshold = 300
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
            
            print("⏳ Đang xử lý âm thanh...")
            
            try:
                # Ưu tiên nhận dạng Tiếng Việt (vi-VN)
                text = recognizer.recognize_google(audio, language="vi-VN")
            except sr.UnknownValueError:
                # Fallback Tiếng Anh nếu lỗi nhận diện Tiếng Việt
                text = recognizer.recognize_google(audio, language="en-US")
                print("   (Nhận dạng bằng engine en-US)")
            
            # Gọi xử lý
            execute_command(text)
            
        except sr.WaitTimeoutError:
            pass 
        except sr.UnknownValueError:
            print("❓ Không nghe rõ hoặc giọng nói lẫn tạp âm mạnh.")
        except sr.RequestError as e:
            print(f"⚠️ Lỗi kết nối Internet đến máy chủ nhận dạng: {e}")
        except KeyboardInterrupt:
            print("\n[Hệ thống] Đã nhận lệnh ngắt Ctr+C. Đang tắt chương trình...")
            break
        except Exception as e:
            print(f"Lỗi hệ thống: {e}")


if __name__ == "__main__":
    start_voice_control()
