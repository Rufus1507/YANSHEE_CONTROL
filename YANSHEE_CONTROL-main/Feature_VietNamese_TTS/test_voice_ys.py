import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import YanAPI
import time
import speak_vnamese
def main():
    print("[TEST SPEAK] Đang kết nối tới phần cứng Robot Yanshee...")
    
    robot_ip = "192.168.137.251" 
    
    try:
        YanAPI.set_robot_ip(robot_ip)
        print(f"[TEST SPEAK] Kết nối thành công tới Robot tại IP: {robot_ip}")
    except Exception as connect_error:
        print(f"[LỖI KẾT NỐI] Không tìm thấy robot, kiểm tra lại Wi-Fi: {connect_error}")
        return

    print("\n[TEST SPEAK] Chuẩn bị phát giọng nói... Hãy lắng nghe robot!")
    try:
        # Use the new helper to speak "Hello"
        response1 = speak_vnamese.say_hello(text="Xin", voice_type="vi")
        time.sleep(1)
        response2 = speak_vnamese.say_hello(text="chào", voice_type="vi")
        time.sleep(1)
        response3 = speak_vnamese.say_hello(text="mình", voice_type="vi")
        time.sleep(1)
        response4 = speak_vnamese.say_hello(text="là", voice_type="vi")
        time.sleep(1)
        response5 = speak_vnamese.say_hello(text="Yanshee", voice_type="vi")
        time.sleep(1)
        print(f"[SUCCESS] Robot Yanshee_454D phản hồi: {response1} | {response2} | {response3} | {response4} | {response5}")

    except Exception as e:
        print(f"[SAY_HELLO ERROR] {e}")

if __name__ == "__main__":
    main()