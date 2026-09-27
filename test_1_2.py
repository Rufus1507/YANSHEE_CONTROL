import time
import sys
import threading
from YanAPI import YanAPI

# ==========================================
# CẤU HÌNH IP - 2 robot
# ==========================================
ROBOT_IPS = ["192.168.91.21", "192.168.91.75"]

robots = []  # danh sách [(ip, YanAPI), ...] đã kết nối thành công

print("\n[Init] Đang kết nối các robot...")
for ip in ROBOT_IPS:
    try:
        r = YanAPI(ip_address=ip)
        robots.append((ip, r))
        print(f"[Init] *** Kết nối thành công: {ip} ***")
    except Exception as e:
        print(f"[Init] [SKIP] Không thể kết nối {ip}: {e}")

if not robots:
    print("[Init] Không kết nối được robot nào! Thoát.")
    sys.exit(1)

print(f"[Init] Đã kết nối: {len(robots)}/{len(ROBOT_IPS)} robot\n")

def send_all(fn_name: str, *args, **kwargs):
    """
    Gửi lệnh đến TẤT CẢ robot đang kết nối song song.
    fn_name: tên phương thức của YanAPI (ví dụ: 'sync_play_motion')
    Trả về dict {ip: response}
    """
    results = {}
    lock = threading.Lock()

    def _call(ip, r):
        try:
            resp = getattr(r, fn_name)(*args, **kwargs)
            with lock:
                results[ip] = resp
        except Exception as e:
            with lock:
                results[ip] = f"Lỗi: {e}"

    threads = [threading.Thread(target=_call, args=(ip, r), daemon=True) for ip, r in robots]
    for t in threads: t.start()
    for t in threads: t.join(timeout=15)
    return results

def main():
    print("="*50)
    print(" BẢNG ĐIỀU KHIỂN ÂM THANH & BÀI HÁT YANSHEE")
    print(f" Robot đang kết nối: {[ip for ip, _ in robots]}")
    print("="*50)
    print(" 1 : Giơ tay phải (3 lần)")
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
                print("=> Đang gửi lệnh: Giơ tay phải (3 lần) cho cả 2 robot...")
                for i in range(3):
                    resps = send_all("sync_play_motion", name="RaiseRightHand")
                    for ip, resp in resps.items():
                        print(f"  [{ip}] Phản hồi RaiseRightHand: {resp}")
                    time.sleep(0.5)
                    resps = send_all("sync_play_motion", name="Reset")
                    for ip, resp in resps.items():
                        print(f"  [{ip}] Phản hồi Reset: {resp}")
                    time.sleep(0.5)
                
            elif choice == '2':
                resps = send_all("sync_play_motion", name="Fight_RSideHi")
            
            elif choice == '3':
                resps = send_all("sync_play_motion", name="Fight_LSideHi")

            elif choice == '4':
                print("=> Đang gửi lệnh: Tắt tiếng (Mute)...")
                resps = send_all("set_device_volume", 0)
                for ip, resp in resps.items():
                    print(f"  [{ip}] Mute | Phản hồi: {resp}")

            elif choice == '5':
                print("=> Đang gửi lệnh: DỮNG LẠI cho cả 2 robot...")
                resps = send_all("stop_music")
                for ip, resp in resps.items():
                    print(f"  [{ip}] Stop Music: {resp}")
                
                resps = send_all("stop_motion")
                for ip, resp in resps.items():
                    print(f"  [{ip}] Stop Motion: {resp}")
                
                time.sleep(0.5)
                print("=> Gửi lệnh: Reset tư thế...")
                resps = send_all("sync_play_motion", name="Reset")
                for ip, resp in resps.items():
                    print(f"  [{ip}] Reset: {resp}")
                
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
