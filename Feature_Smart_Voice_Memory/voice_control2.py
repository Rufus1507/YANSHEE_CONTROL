import speech_recognition as sr
import time
import json
import os

# Biến toàn cục để lưu câu lệnh giọng nói mới nhất gửi cho file Main
current_voice_command = ""

# Đường dẫn tới file bộ nhớ của robot để lưu từ khóa lâu dài
file_memory = "robot_memory.json"

# Lựa chọn thiết bị thu âm
choose_mic_num = None 

# Hàm đọc ghi file .json
def read_memory():
    if not os.path.exists(file_memory):
        memory_ori = {
            # --- Nhóm hành động hệ thống (Bắt buộc viết hoa chữ cái đầu) ---
            "Forward": ["đi thẳng", "tiến lên", "đi tới"],
            "Backward": ["đi lùi", "lùi lại"],
            "TurnLeft": ["rẽ trái", "quay trái"],
            "TurnRight": ["rẽ phải", "quay phải"],
            "Stop": ["dừng lại", "đứng yên", "thôi", "dừng"],
            "Reset": ["khởi động lại", "về vị trí cũ", "đứng nghiêm"],
            
            # --- Nhóm hành động một bước ---
            "OneStepForward": ["tiến một bước", "bước lên"],
            "OneStepBackward": ["lùi một bước", "bước lùi"],
            "OneStepTurnLeft": ["xoay trái một bước"],
            "OneStepTurnRight": ["xoay phải một bước"],
            "OneStepMoveLeft": ["nhích sang trái", "bước sang trái"],
            "OneStepMoveRight": ["nhích sang phải", "bước sang phải"],
            "Move_fast": ["chạy nhanh", "tăng tốc"],
            
            # --- Nhóm tương tác (Đã sửa chữ W viết hoa) ---
            "RaiseRightHand": ["giơ tay phải"],
            "Wave": ["vẫy tay", "tạm biệt", "xin chào"], # Chữ W viết hoa chuẩn hệ thống
            "Hug": ["ôm cái nào", "ôm"],
            "Victory": ["chiến thắng", "vô địch"],
            
            # --- Nhóm trạng thái ---
            "EnterEnergySavingSquat": ["tiết kiệm pin", "ngồi xổm xuống"],
            "ExitEnergySavingReset": ["thoát tiết kiệm pin", "đứng dậy đi"],
            
            # --- Nhóm nhảy và giải trí ---
            "WakaWaka": ["nhảy waka waka", "vũ điệu waka"],
            "MerryChristmas": ["giáng sinh", "nhảy noel"],
            "HappyBirthday": ["sinh nhật", "chúc mừng sinh nhật"],
            "SweetAndSour": ["nhảy chua ngọt"],
            
            # --- Nhóm võ thuật và thể thao ---
            "PushUp": ["hít đất", "chống đẩy"],
            "Football_RKick": ["đá chân phải", "sút bằng chân phải"],
            "Football_LKick": ["đá chân trái", "sút bằng chân trái"],
            "LeftSidePunch": ["đấm bên trái"],
            "RightSidePunch": ["đấm bên phải"],
            "LeftHitForward": ["đấm thẳng tay trái"],
            "RightHitForward": ["đấm thẳng tay phải"]
        }
        
        with open(file_memory, "w", encoding="utf-8") as f:
            json.dump(memory_ori, f, ensure_ascii=False, indent=4)
        print(f"Đã tự động tạo file bộ nhớ ban đầu: '{file_memory}' thành công!")
        return memory_ori
        
    with open(file_memory, "r", encoding="utf-8") as f:
        return json.load(f)

def save_memory(new_memory):
    with open(file_memory, "w", encoding="utf-8") as f:
        json.dump(new_memory, f, ensure_ascii=False, indent=4)

# THUẬT TOÁN QUÉT TỪ KHÓA CỐT LÕI
def find_motions(speech_ori, memory):
    for motion, keywords in memory.items():
        for kwords in keywords:
            if kwords in speech_ori:
                return motion
    return ""

def print_list_mic():
    print("\n=== DANH SÁCH THIẾT BỊ THU ÂM MÁY TÍNH ĐANG NHẬN ===")
    list_mic = sr.Microphone.list_microphone_names()
    for i, mic_name in enumerate(list_mic):
        print(f"Số [{i}]: {mic_name}")
    print("===================================================\n")

# HÀM VẬN HÀNH CHÍNH
def start_voice_control():
    global current_voice_command
    recognizer = sr.Recognizer()
    
    memory = read_memory()
    print_list_mic()
    
    with sr.Microphone(device_index=choose_mic_num) as source:
        print(f"[VOICE AI] Đang mở thiết bị thu âm số: {choose_mic_num}...")
        recognizer.adjust_for_ambient_noise(source, duration=1)
        print("[VOICE AI] Đã sẵn sàng nhận lệnh")
        
        while True:
            try:
                print("\n[VOICE] Đang lắng nghe...")
                audio_data = recognizer.listen(source, phrase_time_limit=8)
                text_result = recognizer.recognize_google(audio_data, language="vi-VN")
                text_result = text_result.lower().strip()
                print(f"[VOICE] Hệ thống nghe thấy: '{text_result}'")
                
                instruc_find = find_motions(text_result, memory)
                
                if instruc_find != "":
                    print(f"KHỚP LỆNH: -> Gửi lệnh '{instruc_find}' tới robot")
                    current_voice_command = instruc_find
                else:
                    # --- CHẾ ĐỘ AI TỰ HỌC TỪ MỚI ---
                    print(f"Từ lạ: '{text_result}' không nằm trong bộ nhớ.")
                    print("Gán cụm từ này cho hành động nào của Yanshee?")
                    print("Hãy gõ chính xác tên hành động tiếng Anh (Nhớ viết hoa đúng chuẩn, vd: WakaWaka): ")
                    
                    motion_assign = input().strip()
                    
                    # Đã sửa: Đối chiếu chính xác và phân biệt chữ hoa/thường để tránh sai key
                    if motion_assign in memory:
                        memory[motion_assign].append(text_result)
                        save_memory(memory)
                        print(f"ĐÃ HỌC XONG! Từ nay khi nghe thấy '{text_result}', sẽ thực hiện hành động phần cứng '{motion_assign}'!")
                    else:
                        print(f"Lỗi: Tên hành động '{motion_assign}' gõ không tồn tại trong danh sách hệ thống của robot. Hủy lượt học.")
                    
                    current_voice_command = ""
                    
            except sr.UnknownValueError:
                pass
            except Exception as e:
                print(f"[VOICE ERROR] Gặp lỗi hệ thống: {e}")
                
            time.sleep(0.5)

if __name__ == "__main__":
    start_voice_control()