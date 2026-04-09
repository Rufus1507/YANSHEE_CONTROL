import threading
import queue
import time
import sys

from YanAPI import YanAPI
import voive_control
import cam_control

# --- Cấu hình IP Yanshee ---
# Đổi lại thành "10.176.138.75" nếu mạng đang dùng là mạng của camera cũ
ROBOT_IP = "10.176.138.75" 

try:
    robot = YanAPI(ip_address=ROBOT_IP)
    print(f"[Main Control] Kết nối Yanshee tại {ROBOT_IP} thành công!")
except Exception as e:
    print(f"[Lỗi Main Control] Không thể kết nối API: {e}")
    robot = None

# Priority queue: tuple (priority, source, action_cmd, data_kwargs)
# priority 1 = voice
# priority 2 = cam
command_queue = queue.PriorityQueue()

def execute_command_on_robot(source, action_cmd, data):
    global robot
    if robot is None:
        print(f"[Skip] Robot is NOT connected. Command: {action_cmd} from {source}")
        return

    try:
        if action_cmd == "sync_play_motion":
            m_name = data.get("name")
            repeat = data.get("repeat", 1)
            print(f"  > [Robot API] Thực hiện động tác: {m_name} (repeat={repeat}) từ [{source.upper()}]")
            if source == "cam":
                # Chạy bất đồng bộ qua luồng để không block queue, cho phép bỏ tay xuống là ngắt ngay được
                threading.Thread(target=robot.sync_play_motion, kwargs={"name": m_name, "repeat": repeat}, daemon=True).start()
            else:
                robot.sync_play_motion(name=m_name, repeat=repeat)
                # Dùng luồng chạy ngầm để liên tục hỏi thăm Robot xem nhảy xong chưa (giải phóng hàng đợi để nhận được "DỪNG LẠI")
                if robot and source == "voice":
                    def wait_for_motion():
                        time.sleep(0.5)  # Trễ nhẹ để API trên robot kịp cập nhật trạng thái
                        while True:
                            try:
                                status_resp = robot.get_motions_status()
                                status = status_resp.get("data", {}).get("status", "idle") if isinstance(status_resp, dict) else "idle"
                            except Exception:
                                status = "idle"
                            if status != "run":
                                break
                            time.sleep(0.5)
                        # An toàn mở khóa nếu nó thực sự xong và không còn lệnh chờ
                        with command_queue.mutex:
                            if not any(q_item[0] == 1 for q_item in command_queue.queue):
                                command_queue.voice_is_busy = False
                                
                    threading.Thread(target=wait_for_motion, daemon=True).start()
            
        elif action_cmd == "stop_motion":
            print(f"  > [Robot API] Stop motion từ [{source.upper()}]")
            robot.stop_motion()
            
        elif action_cmd == "stop_music":
            print(f"  > [Robot API] Stop music từ [{source.upper()}]")
            robot.stop_music()

        elif action_cmd == "play_music":
            track = data.get("track", "WakaWaka")
            print(f"  > [Robot API] Play music bài {track} từ [{source.upper()}]")
            robot.play_music(track)

        elif action_cmd == "set_volume":
            vol = data.get("vol", 50)
            print(f"  > [Robot API] Set volume = {vol} từ [{source.upper()}]")
            robot.set_device_volume(vol)
            
        elif action_cmd == "volume_up":
            vol_resp = robot.get_device_volume()
            curr_vol = vol_resp.get("data", {}).get("volume", 50) if isinstance(vol_resp, dict) else 50
            new_vol = min(100, curr_vol + 15)
            robot.set_device_volume(new_vol)
            print(f"  > [Robot API] Volume Up -> {new_vol} từ [{source.upper()}]")
            
        elif action_cmd == "volume_down":
            vol_resp = robot.get_device_volume()
            curr_vol = vol_resp.get("data", {}).get("volume", 50) if isinstance(vol_resp, dict) else 50
            new_vol = max(0, curr_vol - 15)
            robot.set_device_volume(new_vol)
            print(f"  > [Robot API] Volume Down -> {new_vol} từ [{source.upper()}]")

        elif action_cmd == "volume_up_by":
            pct = data.get("pct", 10)
            vol_resp = robot.get_device_volume()
            curr_vol = vol_resp.get("data", {}).get("volume", 50) if isinstance(vol_resp, dict) else 50
            new_vol = min(100, curr_vol + pct)
            robot.set_device_volume(new_vol)
            print(f"  > [Robot API] Volume Up by {pct}% : {curr_vol} -> {new_vol} từ [{source.upper()}]")

        elif action_cmd == "volume_down_by":
            pct = data.get("pct", 10)
            vol_resp = robot.get_device_volume()
            curr_vol = vol_resp.get("data", {}).get("volume", 50) if isinstance(vol_resp, dict) else 50
            new_vol = max(0, curr_vol - pct)
            robot.set_device_volume(new_vol)
            print(f"  > [Robot API] Volume Down by {pct}% : {curr_vol} -> {new_vol} từ [{source.upper()}]")
            
        elif action_cmd == "sleep":
            sleep_time = data.get("time", 0.5)
            print(f"  > [Robot API] Đợi (Sleep) {sleep_time}s từ [{source.upper()}]")
            time.sleep(sleep_time)
            
    except Exception as e:
        print(f"[Lỗi API] API robot lỗi khi gửi {action_cmd}: {e}")

def main_loop():
    print("============================================================")
    print("   HỆ THỐNG ĐIỀU KHIỂN YANSHEE (VOICE + CAMERA AI)")
    print(f"   IP Robot cấu hình: {ROBOT_IP}")
    print("============================================================")
    print(" * Khởi tạo thuật toán đa luồng (Multi-threading)...")
    
    # Khởi chạy luồng giọng nói Whisper
    t_voice = threading.Thread(target=voive_control.start_voice_control, args=(command_queue,), daemon=True)
    t_voice.start()
    print(" [+] Luồng nhận diện bằng Giọng nói ĐÃ KÍCH HOẠT.")
    
    # Khởi chạy luồng Camera MediaPipe
    t_cam = threading.Thread(target=cam_control.start_cam_control, args=(command_queue,), daemon=True)
    t_cam.start()
    print(" [+] Luồng nhận diện bằng Camera ĐÃ KÍCH HOẠT.")
    
    # Cấm camera ra lệnh khi có voice vừa cất lên
    voice_lock_until = 0

    print("\n[READY] Đang chờ lệnh điều khiển...\n")
    while True:
        try:
            # Block chờ lệnh từ hàng đợi với cờ timeout 0.5s để có thể bắt được tín hiệu Ctrl+C
            try:
                item = command_queue.get(timeout=0.5)
            except queue.Empty:
                continue
            
            # Bóc tách tuple: (priority, seq, source, action_cmd, data)
            priority, seq, source, action_cmd, data = item
            
            if action_cmd == "exit":
                print("\n[HỆ THỐNG] Đã nhận lệnh Tắt Chương Trình từ người dùng! Đang tắt toàn bộ tiến trình...")
                break
            
            print(f"\n[MAIN THREAD] Nhận lệnh từ {source.upper()} -> '{action_cmd}'")
            execute_command_on_robot(source, action_cmd, data)
            
            if source == "voice":
                # Nếu là lệnh tức thời (như stop_motion, volume) hoặc sleep, thả cờ rảnh khi xong
                if action_cmd != "sync_play_motion":
                    with command_queue.mutex:
                        has_more_voice = any(q_item[0] == 1 for q_item in command_queue.queue)
                    if not has_more_voice:
                        command_queue.voice_is_busy = False
                    
            command_queue.task_done()
            
        except KeyboardInterrupt:
            print("\n[Hệ thống] Đang thoát Main Control...")
            break
        except Exception as e:
            print(f"[Lỗi Main] Có lỗi trong loop: {e}")

if __name__ == "__main__":
    main_loop()
