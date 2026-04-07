import time
import sys
from YanAPI import YanAPI

# ==========================================
# CẤU HÌNH IP
# ==========================================
ROBOT_IP = "192.168.235.75"  # Dùng IP mạng của bạn
try:
    robot = YanAPI(ip_address=ROBOT_IP)
except Exception as e:
    print(f"Lỗi kết nối API: {e}")
    sys.exit(1)

def main():
    print("="*50)
    print(" CÔNG CỤ TEST NHANH BÀN PHÍM")
    print("="*50)
    print(" 1 : Hít Đất (PushUp) -> [CẢNH BÁO: HÀNH ĐỘNG RỦI RO CAO / HIGH RISK]")
    print(" 3 : Giơ Tay Phải (RaiseRightHand) -> [HÀNH ĐỘNG AN TOÀN / LOW RISK]")
    print(" 2 : Gửi ngắt Dừng lại và Reset (Stop + Reset)")
    print(" 0 : Thoát chương trình")
    print("="*50)

    while True:
        try:
            choice = input("\n👉 Hãy chọn lệnh (1, 2, 3 hoặc 0): ").strip()
            
            if choice == '1':
                print("=> Đang gửi lệnh: Chống Đẩy (PushUp)...")
                response = robot.sync_play_motion(name="H_WaveRH")
                print(f"Phản hồi: {response}")
                
            elif choice == '3':
                print("=> Đang gửi lệnh: Giơ Tay Phải (RaiseRightHand)...")
                response = robot.sync_play_motion(name="H_Rise_L")
                print(f"Phản hồi: {response}")
            
            elif choice == '2':
                print("=> Đang gửi lệnh: DỪNG LẠI...")
                # Gửi lệnh ngắt nếu bạn đã cấu hình bypass trong YanAPI
                stop_resp = robot.stop_motion()
                print(f"Phản hồi Stop: {stop_resp}")
                
                # Chờ phần cứng xử lý
                time.sleep(0.5)
                
                print("=> Gửi lệnh: Reset tư thế...")
                reset_resp = robot.sync_play_motion(name="Reset")
                print(f"Phản hồi Reset: {reset_resp}")
                
            elif choice == '0':
                print("\nKết thúc test.")
                break
                
            else:
                print("⚠️ Lựa chọn không hợp lệ, vui lòng nhập '1' hoặc '2'.")
                
        except KeyboardInterrupt:
            print("\nĐã ép ngắt Ctr+C. Kết thúc chương trình.")
            break
        except Exception as e:
            print(f"Lỗi không xác định: {e}")

if __name__ == "__main__":
    main()
