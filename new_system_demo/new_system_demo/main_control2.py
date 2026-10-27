import threading
import time
import voice_control2 as voice_system  # Nhập file voice_control2 để lấy biến lệnh dùng chung
import YanAPI  # Thư viện SDK điều khiển độc quyền của Robot Yanshee

def main():
    print("[MAIN SYSTEM] Đang thiết lập kết nối tới phần cứng Robot Yanshee...")
    
    # Địa chỉ IP kết nối Wi-Fi thực tế của con robot trên phòng Lab của bà
    robot_ip = "192.168.137.62" 
    
    try:
        # Thực hiện bắt tay mở cổng truyền nhận tín hiệu tới Robot qua mạng mạng
        YanAPI.set_robot_ip(robot_ip)
        YanAPI.init()
        print(f"[MAIN SYSTEM] Kết nối thành công tới Robot Yanshee tại IP: {robot_ip}!")
    except Exception as init_error:
        print(f"[CONNECTION ERROR] Lỗi kết nối phần cứng, hãy kiểm tra lại Wi-Fi hoặc IP: {init_error}")
        return

    # Khi vừa khởi động hệ thống, ép robot chạy lệnh đứng nghiêm chỉnh để báo hiệu thông suốt phần cứng
    try:
        YanAPI.sync_play_motion(name="Reset")
        print("[MAIN SYSTEM] Đã đưa robot về tư thế đứng thẳng nghiêm chỉnh (Reset).")
    except Exception as motion_error:
        print(f"[MOTION ERROR] Không gửi được lệnh khởi động ban đầu xuống robot: {motion_error}")
    
    # Kích hoạt luồng thu âm giọng nói chạy song song ngầm (Threading) để vừa nghe mic vừa chạy robot
    voice_thread = threading.Thread(target=voice_system.start_voice_control)
    voice_thread.daemon = True  # Đảm bảo luồng ngầm tự tắt khi tắt file chính
    voice_thread.start()
    
    print("[MAIN SYSTEM] Toàn bộ hệ thống kết hợp hoàn chỉnh! Sẵn sàng chờ lệnh ngữ nghĩa từ bà...")
    
    # Vòng lặp vô hạn kiểm tra biến lệnh liên tục từ luồng AI đẩy xuống
    while True:
        # Lấy lệnh hành động hiện tại từ file voice_control2
        voice_command = voice_system.current_voice_command
        
        # Nếu phát hiện có lệnh hành động chuẩn tiếng Anh vừa được nạp vào
        if voice_command != "":
            print(f"\n[MAIN EXECUTE] Nhận kết quả dịch từ bộ não Gemini -> Bắn lệnh phần cứng xuống Robot: '{voice_command}'")
            
            try:
                # Ra lệnh trực tiếp cho robot Yanshee cử động ngoài đời thực
                res = YanAPI.sync_play_motion(name=voice_command)
                print(f"[SUCCESS] Robot đã thực hiện xong hành động: {voice_command}. Phản hồi hệ thống: {res}")
            except Exception as robot_error:
                print(f"[ROBOT ERROR] Gặp sự cố truyền lệnh hoặc kẹt khớp phần cứng: {robot_error}")
            
            # Xóa sạch lệnh cũ ngay lập tức để tránh việc robot bị lặp lại hành động đó vô hạn
            voice_system.current_voice_command = ""
            
        # Kiểm tra biến điều khiển sau mỗi 0.2 giây để đảm bảo độ trễ thấp nhất khi nhận lệnh
        time.sleep(0.2)

if __name__ == "__main__":
    main()