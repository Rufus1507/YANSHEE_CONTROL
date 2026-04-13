import threading
import queue
import time
import sys
import socket

from YanAPI import YanAPI
import voice_control as voive_control
import cam_control

# --- Cấu hình IP Yanshee ---
# Danh sách IP của tất cả robot cần điều khiển
ROBOT_IPS = ["10.130.106.75", "10.130.106.21"]

# Danh sách các đối tượng robot ĐÃ kết nối thành công (có thể 1 hoặc nhiều)
robots: list = []         # [(ip, YanAPI_instance), ...]
robots_lock = threading.Lock()

TCP_TIMEOUT = 3  # Thời gian tối đa kiểm tra kết nối TCP (giây)
ROBOT_API_PORT = 9090
VOICE_ENABLED = True
# VOICE_ENABLED = False

def is_robot_reachable(ip: str) -> bool:
    """Kiểm tra TCP thực sự đến port 9090 của robot. Nhanh, không gửi HTTP."""
    try:
        s = socket.create_connection((ip, ROBOT_API_PORT), timeout=TCP_TIMEOUT)
        s.close()
        return True
    except Exception:
        return False

def connect_all_robots():
    """Thử kết nối TẤT CẢ các IP trong ROBOT_IPS. Kiểm tra TCP trước khi thêm vào list.
    Lặp lại mỗi RECONNECT_INTERVAL giây để phục hồi robot bị mất kết nối."""
    RECONNECT_INTERVAL = 10  # giây
    print("[Main Control] Bắt đầu kết nối đến tất cả robot...")
    while True:
        with robots_lock:
            connected_ips = {ip for ip, _ in robots}

        for ip in ROBOT_IPS:
            if ip in connected_ips:
                continue  # Đã kết nối rồi, bỏ qua
            print(f"[Main Control] Kiểm tra kết nối TCP tới {ip}:{ROBOT_API_PORT}...")
            if not is_robot_reachable(ip):
                print(f"[Skip] {ip} không phản hồi trên port {ROBOT_API_PORT}. Bỏ qua.")
                continue
            try:
                r = YanAPI(ip_address=ip)
                with robots_lock:
                    robots.append((ip, r))
                print(f"[Main Control] *** Kết nối thành công: {ip} (Tổng: {len(robots)}/{len(ROBOT_IPS)}) ***")
            except Exception as e:
                print(f"[Skip] Không thể khởi tạo YanAPI cho {ip}: {e}")

        with robots_lock:
            n = len(robots)
        if n == 0:
            print(f"[Main Control] Chưa kết nối được robot nào! Thử lại sau {RECONNECT_INTERVAL}s...")
        elif n < len(ROBOT_IPS):
            print(f"[Main Control] Đã kết nối {n}/{len(ROBOT_IPS)} robot. Thử lại IP còn lại sau {RECONNECT_INTERVAL}s...")
        else:
            print(f"[Main Control] Đã kết nối đủ {n}/{len(ROBOT_IPS)} robot!")

        time.sleep(RECONNECT_INTERVAL)

def health_check_robots():
    """Kiểm tra định kỳ (mỗi 5s) các robot trong list. Nếu TCP timeout -> gỡ khỏi list."""
    HEALTH_INTERVAL = 5
    while True:
        time.sleep(HEALTH_INTERVAL)
        with robots_lock:
            current = list(robots)
        for ip, r in current:
            if not is_robot_reachable(ip):
                with robots_lock:
                    try:
                        robots.remove((ip, r))
                        print(f"[Health Check] {ip} không phản hồi -> Đã gỡ khỏi danh sách.")
                    except ValueError:
                        pass
                # Nhả voice_is_busy nếu robot chết giữa chừng
                if command_queue and getattr(command_queue, 'voice_is_busy', False):
                    with command_queue.mutex:
                        if not any(q[0] == 1 for q in command_queue.queue):
                            command_queue.voice_is_busy = False
                            print(f"[Health Check] Đã nhả voice_is_busy do {ip} mất kết nối.")

# Khởi chạy luồng kết nối ngầm (non-blocking, thử kết nối liên tục)
_t_connect = threading.Thread(target=connect_all_robots, daemon=True)
_t_connect.start()

# Khởi chạy luồng health-check ngầm
_t_health = threading.Thread(target=health_check_robots, daemon=True)
_t_health.start()

# Chờ tối đa 15s để kết nối được ít nhất 1 robot trước khi bắt đầu vòng lặp chính
_wait_start = time.time()
while len(robots) == 0 and (time.time() - _wait_start) < 15:
    time.sleep(0.5)
if len(robots) == 0:
    print("[CẢNH BÁO] Không kết nối được robot nào sau 15s. Tiếp tục nhưng lệnh sẽ bị bỏ qua.")

# Priority queue: tuple (priority, source, action_cmd, data_kwargs)
# priority 1 = voice
# priority 2 = cam
command_queue = queue.PriorityQueue()

def _execute_on_single_robot(ip: str, r: YanAPI, source: str, action_cmd: str, data: dict):
    """Thực thi 1 lệnh lên 1 robot cụ thể. Được gọi song song bởi execute_command_on_all_robots."""
    robot_tag = f"[{ip}]"
    try:
        if action_cmd == "sync_play_motion":
            m_name = data.get("name")
            repeat = data.get("repeat", 1)
            print(f"  > {robot_tag} Động tác: {m_name} (repeat={repeat}) [{source.upper()}]")
            if source == "cam":
                # Cam: bất đồng bộ để không block queue
                threading.Thread(
                    target=r.sync_play_motion,
                    kwargs={"name": m_name, "repeat": repeat},
                    daemon=True
                ).start()
            else:
                # Voice: Khóa cam ĐÚNH KHI bắt đầu thực thi động tác trên robot
                command_queue.voice_is_busy = True
                r.sync_play_motion(name=m_name, repeat=repeat)
                def wait_for_motion(robot_ref=r):
                    time.sleep(0.5)
                    while True:
                        try:
                            status_resp = robot_ref.get_motions_status()
                            status = status_resp.get("data", {}).get("status", "idle") if isinstance(status_resp, dict) else "idle"
                        except Exception:
                            status = "idle"
                        if status != "run":
                            break
                        time.sleep(0.5)
                    # Giải phóng khóa cam khi robot chạy xong và không cón lệnh voice đang chờ
                    with command_queue.mutex:
                        if not any(q_item[0] == 1 for q_item in command_queue.queue):
                            command_queue.voice_is_busy = False
                threading.Thread(target=wait_for_motion, daemon=True).start()

        elif action_cmd == "stop_motion":
            print(f"  > {robot_tag} Stop motion [{source.upper()}]")
            r.stop_motion()

        elif action_cmd == "stop_music":
            print(f"  > {robot_tag} Stop music [{source.upper()}]")
            r.stop_music()

        elif action_cmd == "play_music":
            track = data.get("track", "WakaWaka")
            print(f"  > {robot_tag} Play music: {track} [{source.upper()}]")
            r.play_music(track)

        elif action_cmd == "set_volume":
            vol = data.get("vol", 50)
            print(f"  > {robot_tag} Set volume = {vol} [{source.upper()}]")
            r.set_device_volume(vol)

        elif action_cmd == "volume_up":
            vol_resp = r.get_device_volume()
            curr_vol = vol_resp.get("data", {}).get("volume", 50) if isinstance(vol_resp, dict) else 50
            new_vol = min(100, curr_vol + 15)
            r.set_device_volume(new_vol)
            print(f"  > {robot_tag} Volume Up -> {new_vol} [{source.upper()}]")

        elif action_cmd == "volume_down":
            vol_resp = r.get_device_volume()
            curr_vol = vol_resp.get("data", {}).get("volume", 50) if isinstance(vol_resp, dict) else 50
            new_vol = max(0, curr_vol - 15)
            r.set_device_volume(new_vol)
            print(f"  > {robot_tag} Volume Down -> {new_vol} [{source.upper()}]")

        elif action_cmd == "volume_up_by":
            pct = data.get("pct", 10)
            vol_resp = r.get_device_volume()
            curr_vol = vol_resp.get("data", {}).get("volume", 50) if isinstance(vol_resp, dict) else 50
            new_vol = min(100, curr_vol + pct)
            r.set_device_volume(new_vol)
            print(f"  > {robot_tag} Volume Up by {pct}%: {curr_vol} -> {new_vol} [{source.upper()}]")

        elif action_cmd == "volume_down_by":
            pct = data.get("pct", 10)
            vol_resp = r.get_device_volume()
            curr_vol = vol_resp.get("data", {}).get("volume", 50) if isinstance(vol_resp, dict) else 50
            new_vol = max(0, curr_vol - pct)
            r.set_device_volume(new_vol)
            print(f"  > {robot_tag} Volume Down by {pct}%: {curr_vol} -> {new_vol} [{source.upper()}]")

        elif action_cmd == "sleep":
            sleep_time = data.get("time", 0.5)
            print(f"  > {robot_tag} Sleep {sleep_time}s [{source.upper()}]")
            time.sleep(sleep_time)

    except Exception as e:
        print(f"[Lỗi API] {robot_tag} Lỗi khi gửi '{action_cmd}': {e}")
        # Nếu robot bị mất kết nối, gỡ khỏi danh sách để luồng kết nối thử lại
        with robots_lock:
            try:
                robots.remove((ip, r))
                print(f"[Main Control] {robot_tag} Đã ngắt khỏi danh sách. Sẽ thử kết nối lại tự động.")
            except ValueError:
                pass
        # Nếu đây là lệnh sync_play_motion từ voice bị thất bại → nhả cờ ngay
        # để camera không bị block vô thời hạn do robot mất kết nối
        if source == "voice" and action_cmd == "sync_play_motion":
            with command_queue.mutex:
                if not any(q_item[0] == 1 for q_item in command_queue.queue):
                    command_queue.voice_is_busy = False
                    print(f"[Main Control] {robot_tag} Đã nhả voice_is_busy do lỗi kết nối.")

def execute_command_on_robot(source: str, action_cmd: str, data: dict):
    """Gửi lệnh đến TẤT CẢ robot đang kết nối, chạy song song qua threading."""
    with robots_lock:
        current_robots = list(robots)  # Snapshot tránh race condition

    if not current_robots:
        print(f"[Skip] Không có robot nào đang kết nối. Lệnh '{action_cmd}' bị bỏ qua.")
        return

    # Lệnh sleep chỉ cần thực hiện 1 lần (không cần phát đến từng robot)
    if action_cmd == "sleep":
        sleep_time = data.get("time", 0.5)
        print(f"  > [Sleep] {sleep_time}s")
        time.sleep(sleep_time)
        return

    print(f"  > Phát lệnh '{action_cmd}' đến {len(current_robots)} robot: {[ip for ip, _ in current_robots]}")

    # Tạo 1 luồng cho mỗi robot và chạy song song
    threads = [
        threading.Thread(
            target=_execute_on_single_robot,
            args=(ip, r, source, action_cmd, data),
            daemon=True
        )
        for ip, r in current_robots
    ]
    for t in threads:
        t.start()

    # Với lệnh voice sync_play_motion: chờ cả 2 robot hoàn thành trước khi tiếp tục
    if source == "voice" and action_cmd == "sync_play_motion":
        for t in threads:
            t.join(timeout=30)  # Timeout 30s phòng trường hợp robot treo

def main_loop():
    print("============================================================")
    print("   HỆ THỐNG ĐIỀU KHIỂN YANSHEE (VOICE + CAMERA AI)")
    print(f"   IP Robot cấu hình: {ROBOT_IPS}")
    with robots_lock:
        connected = [ip for ip, _ in robots]
    print(f"   Đã kết nối: {connected} ({len(connected)}/{len(ROBOT_IPS)} robot)")
    print("============================================================")
    print(" * Khởi tạo thuật toán đa luồng (Multi-threading)...")
    
    # Khởi chạy luồng giọng nói Whisper
    if VOICE_ENABLED == True:
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
                # Giải phóng khóa cam ngay với lệnh tức thời (không phải sync_play_motion)
                # (voice_is_busy=True chỉ được set trong luồng _execute_on_single_robot khi thực hiện động tác)
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
