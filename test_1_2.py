import time
import sys
from YanAPI import YanAPI

# ==========================================
# CẤU HÌNH IP
# ==========================================
ROBOT_IP = "10.176.138.75"  # Dùng IP mạng của bạn
try:
    robot = YanAPI(ip_address=ROBOT_IP)
except Exception as e:
    print(f"Lỗi kết nối API: {e}")
    sys.exit(1)

def main():
    print("="*50)
    print(" BẢNG ĐIỀU KHIỂN ÂM THANH & BÀI HÁT YANSHEE")
    print("="*50)
    print(" 1 : Phát nhạc WakaWaka (Chỉ audio, không nhảy)")
    print(" 2 : Tăng âm lượng (+10)")
    print(" 3 : Giảm âm lượng (-10)")
    print(" 4 : Tắt tiếng (Mute)")
    print(" 5 : Dừng (Stop)")
    print(" 0 : Thoát chương trình")
    print("="*50)

    while True:
        try:
            choice = input("\n👉 Hãy chọn lệnh (0-5): ").strip()
            
            if choice == '1':
                print("=> Đang gửi lệnh: Phát nhạc WakaWaka (chỉ Audio)...")
                response = robot.play_music(name="WakaWaka")
                print(f"Phản hồi: {response}")
                
            elif choice == '2':
                print("=> Đang gửi lệnh: Tăng âm lượng...")
                res = robot.get_device_volume()
                vol = res.get("data", {}).get("volume", 50) if isinstance(res, dict) else 50
                new_vol = min(100, vol + 10)
                response = robot.set_device_volume(new_vol)
                print(f"Volume hiện tại: {vol} -> Tăng lên: {new_vol}")
                print(f"Phản hồi: {response}")
            
            elif choice == '3':
                print("=> Đang gửi lệnh: Giảm âm lượng...")
                res = robot.get_device_volume()
                vol = res.get("data", {}).get("volume", 50) if isinstance(res, dict) else 50
                new_vol = max(0, vol - 10)
                response = robot.set_device_volume(new_vol)
                print(f"Volume hiện tại: {vol} -> Giảm xuống: {new_vol}")
                print(f"Phản hồi: {response}")

            elif choice == '4':
                print("=> Đang gửi lệnh: Tắt tiếng (Mute)...")
                response = robot.set_device_volume(0)
                print(f"Volume: Mute (0) - Phản hồi: {response}")

            elif choice == '5':
                print("=> Đang gửi lệnh: DỪNG LẠI (Nhạc & Động tác)...")
                stop_music_resp = robot.stop_music()
                print(f"Phản hồi Stop Music: {stop_music_resp}")
                
                stop_resp = robot.stop_motion()
                print(f"Phản hồi Stop Motion: {stop_resp}")
                
                # Chờ phần cứng xử lý
                time.sleep(0.5)
                
                print("=> Gửi lệnh: Reset tư thế...")
                reset_resp = robot.sync_play_motion(name="Reset")
                print(f"Phản hồi Reset: {reset_resp}")
                
            elif choice == '0':
                print("\nKết thúc test.")
                break
                
            else:
                print("⚠️ Lựa chọn không hợp lệ, vui lòng nhập từ 0 đến 5.")
                
        except KeyboardInterrupt:
            print("\nĐã ép ngắt Ctr+C. Kết thúc chương trình.")
            break
        except Exception as e:
            print(f"Lỗi không xác định: {e}")

if __name__ == "__main__":
    main()
