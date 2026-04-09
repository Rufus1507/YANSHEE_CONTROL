"""
=== YANSHEE GESTURE CONTROL (INTEGRATED VERSION) ===
Điều khiển robot Yanshee bằng cử chỉ tay qua camera.
Có hệ thống Khóa/Mở bằng ngón cái (Like/Dislike).
"""

import cv2
import mediapipe as mp
import threading
import time
import sys
import math

# --- Kết nối Yanshee ---
from YanAPI import YanAPI

ROBOT_IP = "10.176.138.75"
try:
    robot = YanAPI(ip_address=ROBOT_IP)
    print(f"Kết nối Yanshee tại {ROBOT_IP} thành công!")
except Exception as e:
    print(f"Lỗi kết nối API: {e}")
    sys.exit(1)

# ==========================================
# BIẾN TRẠNG THÁI VÀ CẤU HÌNH
# ==========================================

fps = 25

# 1. Trạng thái Hệ thống (Khóa/Mở)
is_system_locked = False
unlock_timestamp = 0
WAIT_AFTER_UNLOCK = 3.0 # Mở khóa xong chờ 5s khởi động

# Thời gian tạm dừng 5s sau khi Xoè tay
PALM_HOLD_TIME = 3.0
PALM_PAUSE_DURATION = 3.0
palm_counter = 0
palm_frames_needed = int(PALM_HOLD_TIME * fps)
palm_pause_timestamp = 0

# 2. Đặc quyền & Chống spam lệnh Pose
last_action = None
last_send_time = 0
COOLDOWN_SEC = 5.0

# 3. Ổn định cử chỉ Pose
STABILITY_FRAMES = 8
SPATIAL_THRESHOLD = 0.03
pose_gesture_counter = 0
confirmed_action = "stop"
prev_wrist_pos = (0, 0)

# ==========================================
# CÁC HÀM XỬ LÝ LỆNH
# ==========================================

def _send_to_robot(action: str):
    """Xử lý và gửi lệnh Yanshee ở luồng riêng"""
    print(f"[{time.strftime('%H:%M:%S')}] Nhận lệnh API: {action}")
    try:
        if action == "raise_right":
            robot.sync_play_motion(name="RaiseRightHand")
        elif action == "victory":
            robot.sync_play_motion(name="Victory")
        elif action == "punch_forward_left":
            robot.sync_play_motion(name="Fight_LHit")
        elif action == "punch_forward_right":
            robot.sync_play_motion(name="Fight_RHit")
        elif action == "punch_sideways_left":
            robot.sync_play_motion(name="LeftSidePunch")
        elif action == "punch_sideways_right":
            robot.sync_play_motion(name="RightSidePunch")
        elif action == "stop":
            robot.sync_play_motion(name="Reset")
        print(f"[{time.strftime('%H:%M:%S')}] Hoàn thành: {action}")
    except Exception as e:
        print(f"Lỗi điều khiển robot: {e}")

def send_command(action: str) -> bool:
    """Xử lý logic Khóa, Cooldown và Gửi lệnh"""
    global last_action, last_send_time
    now = time.time()
    
    # NẾU ĐANG KHÓA: Chặn mọi lệnh trừ Reset (stop)
    if is_system_locked and action != "stop":
        return False

    # Kiểm tra đặc quyền bỏ qua cooldown
    bypass_cooldown = False
    if action == "stop" and last_action == "raise_right":
        bypass_cooldown = True

    # Nếu đang trong thời gian phong ấn Pose
    if last_send_time > 0 and (now - last_send_time) < COOLDOWN_SEC and not bypass_cooldown:
        return False
    if action != last_action:
            threading.Thread(target=_send_to_robot, args=(action,), daemon=True).start()
            last_action = action
            
            if action == "stop":
                last_send_time = 0 
            else:
                last_send_time = now
                
    return True

# ==========================================
# CÁC HÀM NHẬN DIỆN CỬ CHỈ BÀN TAY
# ==========================================

def detect_relaxed_thumb(hand_landmarks):
    """Nhận diện Like/Dislike nới lỏng, chỉ cần 1 tay"""
    if not hand_landmarks: return None
    lm = hand_landmarks.landmark
    fingers_folded = all(lm[i].y > lm[i-2].y for i in [8, 12, 16, 20])
    thumb_gap = abs(lm[4].x - lm[5].x)
    palm_width = abs(lm[5].x - lm[17].x) + 0.01
    
    if fingers_folded and thumb_gap > (palm_width * 0.3):
        return "like" if lm[4].y < lm[3].y else "dislike"
    return None

def detect_open_palm(hand_landmarks):
    """Nhận diện hành động xòe 5 ngón tay (Palm)"""
    if not hand_landmarks: return None
    lm = hand_landmarks.landmark
    fingers_open = all(lm[i].y < lm[i-2].y for i in [8, 12, 16, 20])
    thumb_open = abs(lm[4].x - lm[5].x) > (abs(lm[5].x - lm[17].x) * 0.5)
    
    if fingers_open and thumb_open:
        return "palm"
    return None

# ==========================================
# MAIN LOOP
# ==========================================

mp_holistic = mp.solutions.holistic
holistic = mp_holistic.Holistic(min_detection_confidence=0.6, min_tracking_confidence=0.6)
mp_pose = mp.solutions.pose
mp_drawing = mp.solutions.drawing_utils

cap = cv2.VideoCapture(0)

print("=" * 60)
print(" CHIẾN THẦN CAMERA YANSHEE (INTEGRATED)  |  Nhấn ESC để thoát ")
print("=" * 60)
print(" HƯỚNG DẪN XÁC THỰC 2 LỚP:")
print(" [ĐỂ KHÓA] XÒE TAY 3s -> Chờ màn hình cam -> Đưa DISLIKE")
print(" [ĐỂ MỞ]   XÒE TAY 3s -> Chờ màn hình cam -> Đưa LIKE")
print("  └> Sau khi mở, Hệ thống báo BOOTING 5s trước khi sẵn sàng nhận Pose")
print(" - GIƠ TAY PHẢI lÊN-> Yanshee giơ tay phải")
print(" - GIƠ 2 TAY lÊN CAO -> Yanshee chiến thắng")
print(" - ĐẤM THẲNG TRƯỚC -> Yanshee đấm tới trước")
print(" - ĐẤM NGANG VAI   -> Yanshee đấm ngang")
print(" - BỎ TAY XUỐNG    -> Yanshee Reset đứng im")
print("=" * 60)

while cap.isOpened():
    success, image = cap.read()
    if not success: break

    image = cv2.flip(image, 1)
    rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    results = holistic.process(rgb_image)
    now = time.time()
    h, w = image.shape[:2]

    # --- VẼ KẾT QUẢ LANDMARKS ---
    if results.pose_landmarks:
        mp_drawing.draw_landmarks(image, results.pose_landmarks, mp_holistic.POSE_CONNECTIONS)
    if results.left_hand_landmarks:
        mp_drawing.draw_landmarks(image, results.left_hand_landmarks, mp_holistic.HAND_CONNECTIONS)
    if results.right_hand_landmarks:
        mp_drawing.draw_landmarks(image, results.right_hand_landmarks, mp_holistic.HAND_CONNECTIONS)
# ================================================
    # 1. LOGIC HỆ THỐNG: LIKE / DISLIKE KHÓA MỞ / XÒE TAY ĐỂ TẠM DỪNG
    # ================================================
    l_ges = detect_relaxed_thumb(results.left_hand_landmarks)
    r_ges = detect_relaxed_thumb(results.right_hand_landmarks)
    l_palm = detect_open_palm(results.left_hand_landmarks)
    r_palm = detect_open_palm(results.right_hand_landmarks)
    
    active_sys_gesture = l_ges if l_ges else r_ges
    active_palm_gesture = l_palm if l_palm else r_palm

    # Tính toán trạng thái PAUSE chung (Dùng cho cả lúc Khóa và lúc Mở)
    time_since_palm = now - palm_pause_timestamp
    is_palm_paused = (time_since_palm < PALM_PAUSE_DURATION)

    # 1A. Nhận diện Like / Dislike (Lập tức Không chờ đợi)
    # DISLIKE: CHỈ khóa cứng hệ thống khi đang xòe tay nghỉ 5s
    if active_sys_gesture == "dislike" and not is_system_locked and is_palm_paused:
        is_system_locked = True
        send_command("stop")
        confirmed_action = "stop"
        palm_pause_timestamp = 0 # Thoát pause, vào khóa cứng
    # LIKE: CHỈ mở khóa khi đang bị khóa VÀ đang trong cửa sổ xòe tay
    elif active_sys_gesture == "like" and is_system_locked and is_palm_paused:
        is_system_locked = False
        unlock_timestamp = now # Bắt đầu đếm ngược 5 giây chờ khởi động lại
        palm_pause_timestamp = 0 # Thoát pause

    # 1B. Nhận diện Xòe tay trong 3 giây (Kể cả khi đang Khóa hay Mở)
    if active_palm_gesture == "palm":
        palm_counter += 1
        if palm_counter >= palm_frames_needed:
            if not is_system_locked:
                send_command("stop")
                confirmed_action = "stop"
            palm_pause_timestamp = now  # Kích hoạt tạm khóa 5s
            palm_counter = 0            # Reset bộ đếm
    else:
        palm_counter = 0

    # ================================================
    # 2. LOGIC POSE: GIƠ TAY, ĐẤM
    # ================================================
    current_pose_action = None
    label = "IDLE"
    color = (200, 200, 200)
    wrist_now = (0, 0)
    
    time_since_palm = now - palm_pause_timestamp
    is_palm_paused = (time_since_palm < PALM_PAUSE_DURATION) and not is_system_locked
    
    time_since_unlock = now - unlock_timestamp
    is_booting = (time_since_unlock < WAIT_AFTER_UNLOCK) and not is_system_locked
    
    # Chỉ nhận Pose khi KHÔNG bị khóa, KHÔNG chờ boot mở khóa, và KHÔNG ở trong trạng thái nghỉ 5s xòe tay
    if not is_system_locked and not is_palm_paused and not is_booting:
        if results.pose_landmarks:
            landmarks = results.pose_landmarks.landmark
            
            user_right_wrist = landmarks[mp_pose.PoseLandmark.LEFT_WRIST.value]
            user_left_wrist  = landmarks[mp_pose.PoseLandmark.RIGHT_WRIST.value]
            user_right_shoulder = landmarks[mp_pose.PoseLandmark.LEFT_SHOULDER.value]
            user_left_shoulder  = landmarks[mp_pose.PoseLandmark.RIGHT_SHOULDER.value]
            nose = landmarks[mp_pose.PoseLandmark.NOSE.value]

            shoulder_width = abs(user_left_shoulder.x - user_right_shoulder.x) + 0.01

            r_vis = user_right_wrist.visibility > 0.5
            l_vis = user_left_wrist.visibility > 0.5

            r_up = r_vis and (user_right_wrist.y < nose.y)
            l_up = l_vis and (user_left_wrist.y < nose.y)

            r_side = r_vis and (user_right_wrist.x > user_right_shoulder.x + shoulder_width * 0.7) and (abs(user_right_wrist.y - user_right_shoulder.y) < 0.2)
            l_side = l_vis and (user_left_wrist.x < user_left_shoulder.x - shoulder_width * 0.7)  and (abs(user_left_wrist.y - user_left_shoulder.y) < 0.2)

            r_fwd = r_vis and (abs(user_right_wrist.x - user_right_shoulder.x) < shoulder_width * 0.4) and (abs(user_right_wrist.y - user_right_shoulder.y) < 0.2) and not r_side and not r_up
            l_fwd = l_vis and (abs(user_left_wrist.x - user_left_shoulder.x) < shoulder_width * 0.4) and (abs(user_left_wrist.y - user_left_shoulder.y) < 0.2) and not l_side and not l_up

            # Quyết định chọn action
            if r_side:
                current_pose_action = "đấm ngang tay phải"
                label = "đấm ngang tay phải"
                color = (255, 0, 255)
            elif l_side:
                current_pose_action = "đấm ngang tay trái"
                label = "đấm ngang tay trái"
                color = (255, 0, 255)
            elif r_fwd:
                current_pose_action = "đấm thẳng tay phải"
                label = "đấm thẳng tay phải"
                color = (0, 0, 255)
            elif l_fwd:
                current_pose_action = "đấm thẳng tay trái"
                label = "đấm thẳng tay trái"
                color = (0, 0, 255)
            elif r_up and l_up:
                current_pose_action = "chào"
                label = "chào"
                color = (0, 255, 255)
            elif r_up and not l_up:
                current_pose_action = "tạm biệt"
                label = "tạm biệt"
                color = (0, 255, 0)
                
            # Lưu tọa độ để đo độ ổn định
            if current_pose_action and "left" in current_pose_action:
                if l_vis: wrist_now = (user_left_wrist.x, user_left_wrist.y)
            else:
                if r_vis: wrist_now = (user_right_wrist.x, user_right_wrist.y)

        # ================================================
        # 3. BỘ ĐẾM ỔN ĐỊNH CỬ CHỈ POSE
        # ================================================
        movement = math.hypot(wrist_now[0] - prev_wrist_pos[0], wrist_now[1] - prev_wrist_pos[1])
        
        if current_pose_action and current_pose_action == confirmed_action:
            pose_gesture_counter = 0
        elif current_pose_action and movement < SPATIAL_THRESHOLD:
            pose_gesture_counter += 1
        else:
            pose_gesture_counter = 0
            if not current_pose_action: 
                if confirmed_action != "stop":
                    if send_command("stop"):
                        confirmed_action = "stop"

        prev_wrist_pos = wrist_now

        if pose_gesture_counter >= STABILITY_FRAMES:
            if send_command(current_pose_action):
                confirmed_action = current_pose_action
                pose_gesture_counter = 0

    # ================================================
    # 4. GIAO DIỆN HUD CỤ THỂ
    # ================================================
    if is_system_locked:
        if is_palm_paused:
            cd = int(PALM_PAUSE_DURATION - time_since_palm)
            status_txt, col = f"WAITING UNLOCK: {cd}s", (0, 165, 255)
            sys_label = "SHOW LIKE NOW TO UNLOCK"
        else:
            status_txt, col = "SYSTEM LOCKED", (0, 0, 255)
            sys_label = "SHOW PALM 3s TO BEGIN UNLOCK"
    elif is_booting:
        cd = int(WAIT_AFTER_UNLOCK - time_since_unlock)
        status_txt, col = f"BOOTING... {cd}s", (0, 165, 255)
        sys_label = "WARMING UP (WAIT 5s)"
    elif is_palm_paused:
        cd = int(PALM_PAUSE_DURATION - time_since_palm)
        status_txt, col = f"WAITING LOCK: {cd}s", (0, 165, 255)
        sys_label = "SHOW DISLIKE NOW TO LOCK"
    else:
        status_txt, col = "SYSTEM READY", (0, 255, 0)
        sys_label = "HOLD PALM 3s TO PAUSE"

    # Trạng thái chung
    cv2.putText(image, status_txt, (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.8, col, 2)
    cv2.putText(image, sys_label, (20, 70), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255,255,255), 1)

    # Thanh Progress Bar Khóa/Mở (dành cho Palm 3s)
    if palm_counter > 0:
        bar_w = int((palm_counter / palm_frames_needed) * w)
        cv2.rectangle(image, (0, h-15), (bar_w, h), (0, 255, 255), -1)

    # Trạng thái Cử chỉ
    if not is_system_locked and not is_palm_paused and not is_booting:
        if confirmed_action != "stop":
            p_stat = confirmed_action.upper()
            p_col = (0, 255, 0)
        elif pose_gesture_counter > 0:
            pct = int((pose_gesture_counter / STABILITY_FRAMES) * 100)
            p_stat = f"STABILIZING... {pct}%"
            p_col = (0, 165, 255)
        else:
            p_stat = "IDLE"
            p_col = (200, 200, 200)

        cv2.putText(image, f"ACTION: {label}", (w - 300, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)
        cv2.putText(image, p_stat, (w - 300, 70), cv2.FONT_HERSHEY_SIMPLEX, 0.6, p_col, 2)
        
        # Trạng thái Phong ấn tay (Cooldown)
        time_left = COOLDOWN_SEC - (now - last_send_time)
        if last_send_time > 0 and time_left > 0:
            cv2.putText(image, f"WAITING... {int(time_left)}s", (w - 300, 100), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)

    cv2.putText(image, f"API: {ROBOT_IP}", (10, h - 20), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (50, 255, 50), 2)
    cv2.imshow("Yanshee Gesture AI  |  ESC = Thoat", image)
    if cv2.waitKey(5) & 0xFF == 27:
        break

cap.release()
cv2.destroyAllWindows()
print("\n[Hệ thống] Đã tắt Camera và đóng ứng dụng.")