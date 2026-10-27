import speech_recognition as sr
import time
import requests  # Dùng requests để bắn HTTP thẳng lên server Google, né sạch lỗi 401/404

# ==========================================
# CẤU HÌNH BIẾN TOÀN CỤC & API KEY
# ==========================================
# Biến trung gian dùng để truyền tên hành động sau khi AI phân tích sang cho file Main thực thi
current_voice_command = ""

# Lựa chọn thiết bị thu âm (Để None để hệ thống tự động chọn Micro mặc định của máy tính)
choose_mic_num = None 

# Chiếc API Key định dạng mới (AQ...) chuẩn lấy từ Google AI Studio của bà
GEMINI_API_KEY = ""


# ==========================================
# DANH SÁCH FILE HÀNH ĐỘNG CHUẨN CỦA ROBOT YANSHEE
# ==========================================
ROBOT_MOTIONS = [
    # --- Nhóm hành động hệ thống (System HTS Motions) ---
    "Base_TurnR", "ActionAging1", "Stop", "MerryChristmas", "TurnRight1", 
    "SweetAndSour", "Base_Backward", "GoalKeeper2", "calibration", "Football_RShoot", 
    "Base_GetupF", "ShootLeft", "knee right", "OneStepMoveLeft", "TurnLeft", 
    "knee left", "Football_LKeep", "TurnRight", "Fight_LSideHit", "Forward1", 
    "Base_Leftward", "LeftTackle", "ActionAging", "RaiseRightHand", "Base_Forward", 
    "LeftSidePunch", "WakaWaka", "Football_LKick", "OneStepMoveRight", "GetUp", 
    "RightHitForward", "rightmovestep", "Base_GetupB", "OneStepForward", "Base_TurnL", 
    "Victory", "Left slide tackle", "Football_LShoot", "ExitEnergySavingReset", "Reset", 
    "OneStepTurnRight", "OneStepTurnLeft", "Football_RKick", "Shutdown", "TurnLeftSlowly", 
    "Fight_LHit", "Football_RKeep", "Football_LSideK", "PushUp", "TurnL_tiny", 
    "GoalKeeper1", "Fight_RHit", "GetupFront", "TurnR_tiny", "Base_Rightward", 
    "Rightward", "HappyBirthday", "Hug", "ResetSwitch", "LeftHitForward", 
    "TurnLeft1", "Backward1", "ShootRight", "TurnRightSlowly", "WeAreTakingOff", 
    "Leftward", "Fight_RSideHit", "OneStepBackward", "Football_RSideK", "RightSidePunch", 
    "Forward", "leftmovestep", "GetupRear", "RightTackle", "calibration_new", 
    "reset_without_head", "Backward", "EnterEnergySavingSquat", "Move_fast",
    
    # --- Nhóm hành động điều khiển bộ phận (System Layers Motions) ---
    "F_MoveF_E", "H_WaveRH", "H_Rise_R", "F_MoveF_R", "H_Rise_B", 
    "Hd_Wacth_R", "F_Reset_S", "Hd_Reset_S", "F_MoveB_A", "F_TurnR_T", 
    "F_TurnL_T", "F_MoveR", "Track_TurnR", "Hd_Wacth_F", "F_MoveF_A", 
    "CarryBox", "H_HWave_C", "H_Wave_R", "H_Rise_L", "H_Bec_L", 
    "F_MoveF_B", "H_HWave_L", "H_Bec_R", "H_Str_L", "H_Bec_B", 
    "Hd_Wacth_L", "Reset_S", "Track_TurnL", "H_Str_B", "F_MoveB_E", 
    "F_MoveL", "H_Str_R", "H_RBox", "H_Reset_S"
]


# ==========================================
# HÀM XỬ LÝ LÝ LUẬN NGỮ NGHĨA QUA GEMINI API
# ==========================================
def ask_gemini_intent(user_speech):
    """Gửi câu văn thoại vu vơ lên Gemini AI, ép AI suy luận ra hành động phần cứng tương ứng"""
    
    # Địa chỉ URL Endpoint v1 chính thức và ổn định nhất của Google AI Studio
    url = f"https://generativelanguage.googleapis.com/v1/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
    
    # Thiết lập Prompt huấn luyện tư duy phân tích ngữ nghĩa cho AI
    prompt = f"""
    Bạn là bộ não phân tích ý định (Intent Recognition) cho robot thông minh Yanshee.
    Dưới đây là danh sách tên các file hành động chính xác mà phần cứng robot này hỗ trợ:
    {ROBOT_MOTIONS}
    
    Người dùng vừa nói một câu thoại vu vơ bằng tiếng Việt sau đây: "{user_speech}"
    
    Nhiệm vụ của bạn:
    1. Phân tích ngữ nghĩa ẩn ý, mong muốn thực sự của câu nói đó.
    2. Dò tìm và bắt cặp với MỘT tên hành động phù hợp nhất trong danh sách chuẩn phía trên.
       Gợi ý hướng tư duy:
       - "chào", "tạm biệt", "nóng nực quá", "quạt mát", "bye bye" -> Chọn "H_Wave_R", "H_WaveRH" hoặc "RaiseRightHand"
       - "mệt mỏi", "tập thể dục thôi", "hít đất", "chống đẩy" -> Chọn "PushUp"
       - "nhảy đi", "quẩy đi", "waka waka" -> Chọn "WakaWaka"
       - "tiến lên", "bước tới", "đi thẳng" -> Chọn "Forward" hoặc "OneStepForward"
       - "lùi lại", "bước lùi", "đi lùi" -> Chọn "Backward" hoặc "OneStepBackward"
       - "vui quá", "chiến thắng", "yeah", "vô địch" -> Chọn "Victory"
       - "sinh nhật", "tuổi mới" -> Chọn "HappyBirthday"
       - "giáng sinh", "noel" -> Chọn "MerryChristmas"
       - "dừng lại", "đứng yên", "thôi" -> Chọn "Stop"
       - "về tư thế chuẩn", "khởi động lại", "đứng nghiêm" -> Chọn "Reset"
       - "đá bóng", "sút", "phá bóng" -> Chọn "Football_RShoot", "Football_LKick", "Football_RKick"
       - "ôm", "ôm cái nào" -> Chọn "Hug"
    3. Nếu câu nói hoàn toàn vô nghĩa, vu vơ không liên quan đến hành động nào -> Chỉ trả về duy nhất chữ "None".
    
    QUY TẮC BẮT BUỘC: Chỉ trả ra đúng tên hành động tiếng Anh chính xác từ danh sách được cung cấp (Ví dụ: PushUp), không giải thích dòng nào khác, không thêm dấu câu, không viết thừa chữ.
    """
    
    headers = {'Content-Type': 'application/json'}
    payload = {
        "contents": [
            {
                "parts": [{"text": prompt}]
            }
        ]
    }
    
    try:
        # Thực hiện bắn request POST trực tiếp lên server Google
        response = requests.post(url, headers=headers, json=payload, timeout=10)
        
        # Nếu server xử lý thành công (Mã phản hồi 200)
        if response.status_code == 200:
            res_json = response.json()
            # Bóc tách chuỗi chữ kết quả do AI trả về
            ai_decision = res_json['candidates'][0]['content']['parts'][0]['text'].strip()
            
            # Kiểm tra tính hợp lệ: Nếu tên hành động nằm trong danh sách robot hỗ trợ thì mới gửi đi
            if ai_decision in ROBOT_MOTIONS:
                return ai_decision
        else:
            print(f"[GEMINI HTTP ERROR] Mã lỗi server: {response.status_code} - {response.text}")
            
        return ""
    except Exception as e:
        print(f"[GEMINI CONNECTION LỖI] Trục trặc kết nối Internet hoặc quá thời gian chờ: {e}")
        return ""


# ==========================================
# HÀM KHỞI CHẠY LUỒNG THU ÂM (VOICE CONTROL)
# ==========================================
def start_voice_control():
    """Vòng lặp liên tục lắng nghe giọng nói thông qua Micro và kích hoạt luồng xử lý AI"""
    recognizer = sr.Recognizer()
    
    with sr.Microphone(device_index=choose_mic_num) as source:
        print("[VOICE AI] Đang quét cấu hình micro, lọc tạp âm môi trường...")
        recognizer.adjust_for_ambient_noise(source, duration=1)
        print("[VOICE AI] Bộ não phân tích Gemini (Cổng HTTP v1) đã ON! Hãy nói chuyện thoải mái với robot...")
        
        while True:
            try:
                print("\n[VOICE] Đang lắng nghe âm thanh...")
                # Thu âm giọng nói trong giới hạn tối đa câu nói dài 7 giây
                audio_data = recognizer.listen(source, phrase_time_limit=7)
                
                # BƯỚC 1: Chuyển giọng nói tiếng Việt thành văn bản chữ qua Google Speech-to-Text
                text_result = recognizer.recognize_google(audio_data, language="vi-VN")
                text_result = text_result.strip()
                print(f"[VOICE] Nghe thấy câu văn: '{text_result}'")
                
                # BƯỚC 2: Đẩy thẳng câu văn đó lên Gemini AI để phân tích mục đích ngữ nghĩa
                print("[VOICE] Đang gửi nội dung lên Gemini AI để phân tích ngữ nghĩa...")
                intent_motion = ask_gemini_intent(text_result)
                
                # BƯỚC 3: Nếu AI tìm được hành động khớp lệnh, nạp vào biến toàn cục để chuyển sang file Main
                if intent_motion != "":
                    print(f"[AI MATCHED] Thành công! AI diễn dịch câu nói thành tên file hành động: '{intent_motion}'")
                    global current_voice_command
                    current_voice_command = intent_motion
                else:
                    print("[AI REFUSED] Câu thoại này ko liên quan, AI không tìm thấy chuyển động nào phù hợp.")
                    current_voice_command = ""
                    
            except sr.UnknownValueError:
                # Không nghe rõ âm thanh cụ thể thì tự động bỏ qua để quét tiếp lượt sau
                pass
            except Exception as e:
                print(f"[VOICE ERROR] Hệ thống thu âm gặp sự cố vật lý: {e}")
                
            # Nghỉ 0.5 giây giữa các lượt quét giọng để CPU không bị quá tải
            time.sleep(0.5)

if __name__ == "__main__":
    start_voice_control()