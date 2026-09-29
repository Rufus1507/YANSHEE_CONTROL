import threading
import time
# Nhập file điều khiển giọng nói
import voice_control2 as voice_system

# Nhập thư viện API điều khiển robot Yanshee có sẵn trong thư mục
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import YanAPI

def main():
    # --- BƯỚC 1: KHỞI TẠO KẾT NỐI VỚI ROBOT YANSHEE QUA IP ---
    print("[MAIN SYSTEM] Đang thiết lập kết nối tới phần cứng Robot Yanshee...")
    
    # Giữ nguyên IP mạng đã cấu hình kết nối thành công
    robot_ip = "10.30.89.75" 
    
    try:
        # 1. Khai báo IP đích danh của robot cho thư viện biết
        YanAPI.set_robot_ip(robot_ip)
        
        print(f"[MAIN SYSTEM] Kết nối thành công tới Robot Yanshee tại IP: {robot_ip}!")
    except Exception as init_error:
        print(f"[CONNECTION ERROR] Lỗi kết nối phần cứng, hãy check lại mạng: {init_error}")
        return

    # Đưa robot về tư thế đứng thẳng ban đầu để sẵn sàng nhận lệnh
    try:
        res = YanAPI.sync_play_motion(name="reset")
        if isinstance(res, dict) and "error" in res:
            print(f"[MOTION ERROR] Không gửi được lệnh reset ban đầu: {res['error']}")
        else:
            print(f"[MAIN SYSTEM] Đã đưa robot về tư thế đứng thẳng (Reset). Chi tiết phản hồi: {res}")
    except Exception as motion_error:
        print(f"[MOTION ERROR] Không gửi được lệnh reset ban đầu: {motion_error}")
    
    # --- BƯỚC 2: KÍCH HOẠT LUỒNG GIỌNG NÓI CHẠY NGẦM ---
    voice_thread = threading.Thread(target=voice_system.start_voice_control)
    voice_thread.daemon = True
    voice_thread.start()
    
    print("[MAIN SYSTEM] Hệ thống Voice AI đã sẵn sàng! Đang chờ lệnh từ bà...")
    
    # --- BƯỚC 3: VÒNG LẶP ĐIỀU KHIỂN VÀ THỰC THI THỜI GIAN THỰC ---
    while True:
        # Liên tục bốc câu lệnh giọng nói mới nhất từ biến toàn cục
        voice_command = voice_system.current_voice_command
        
        # Nếu phát hiện bà vừa nói một câu lệnh hợp lệ (biến không trống)
        if voice_command != "":
            print(f"\n[MAIN EXECUTE] Phát hiện lệnh: '{voice_command}' -> Đang bắn lệnh xuống Robot...")
            
            try:
                # GHI THẲNG LỆNH PHẦN CỨNG: sử dụng hàm `sync_play_motion` của YanAPI
                res = YanAPI.sync_play_motion(name=voice_command)
                if isinstance(res, dict) and "error" in res:
                    print(f"[ROBOT ERROR] Gửi lệnh thất bại cho '{voice_command}': {res['error']}")
                else:
                    print(f"[SUCCESS] Robot đã thực thi xong hành động: {voice_command}. Chi tiết phản hồi: {res}")
                
            except Exception as robot_error:
                print(f"[ROBOT ERROR] Lỗi không thể ra lệnh cho robot cử động: {robot_error}")
            
            # Xóa lệnh cũ ngay lập tức để tránh robot bị lặp lại hành động đó vô hạn
            voice_system.current_voice_command = ""
            
        # Nghỉ 0.2 giây trước khi quét lượt tiếp theo để bảo vệ CPU không bị quá tải
        time.sleep(0.2)

if __name__ == "__main__":
    main()