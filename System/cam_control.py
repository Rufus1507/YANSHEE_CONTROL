"""
=== YANSHEE GESTURE CONTROL (INTEGRATED VERSION) ===
Điều khiển robot Yanshee bằng cử chỉ tay qua camera.
Có hệ thống Khóa/Mở bằng ngón cái (Like/Dislike).
Tích hợp gửi lệnh vào main_control.py qua Queue và hiển thị tiếng Việt mượt mà.
"""

import cv2
import mediapipe as mp
import threading
import time
import sys
import itertools
_qc = itertools.count()
import math
import numpy as np

# Cố gắng import PIL để in tiếng Việt
try:
    from PIL import Image, ImageDraw, ImageFont
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

# ==========================================
# CẤU HÌNH QUEUE (Nhận từ main_control.py)
# ==========================================
command_queue = None

# ==========================================
# BIẾN TRẠNG THÁI VÀ CẤU HÌNH
# ==========================================

fps = 25

# 1. Trạng thái Hệ thống (Khóa/Mở)
is_system_locked = False
unlock_timestamp = 0
WAIT_AFTER_UNLOCK = 3.0 # Ngoảnh mặt làm ngơ 3s sau khi Mở khóa

# Thời gian tạm dừng khi Xoè tay
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
# CÁC HÀM XỬ LÝ LỆNH TỚI QUEUE
# ==========================================

def _send_to_robot(action: str):
    """Xử lý và đẩy lệnh qua Hàng Luân phiên Queue (thay vì call API trực tiếp)"""
    if not command_queue: return
    
    # Rà soát nếu Voice đang bận thì không cho vào hàng đợi (Bỏ qua hoàn toàn lệnh của Cam)
    if getattr(command_queue, "voice_is_busy", False):
        print(f"[{time.strftime('%H:%M:%S')}] Lệnh Cam BỊ LOẠI bỏ thẳng vì Voice đang độc chiếm!")
        return
        
    print(f"[{time.strftime('%H:%M:%S')}] Nhận lệnh Cam: {action}")
    try:
        import itertools
        if not hasattr(command_queue, '_cam_c'):
            command_queue._cam_c = itertools.count()
        _qc = command_queue._cam_c
        
        if action == "raise_right":
            command_queue.put((2, next(_qc), "cam", "sync_play_motion", {"name": "RaiseRightHand"}))
        elif action == "victory":
            command_queue.put((2, next(_qc), "cam", "sync_play_motion", {"name": "Victory"}))
        elif action == "punch_forward_left":
            command_queue.put((2, next(_qc), "cam", "sync_play_motion", {"name": "Fight_LHit"}))
        elif action == "punch_forward_right":
            command_queue.put((2, next(_qc), "cam", "sync_play_motion", {"name": "Fight_RHit"}))
        elif action == "punch_sideways_left":
            command_queue.put((2, next(_qc), "cam", "sync_play_motion", {"name": "LeftSidePunch"}))
        elif action == "punch_sideways_right":
            command_queue.put((2, next(_qc), "cam", "sync_play_motion", {"name": "RightSidePunch"}))
        elif action == "stop":
            # Gửi tín hiệu ngắt mọi tư thế hiện có
            command_queue.put((2, next(_qc), "cam", "stop_motion", {}))
            command_queue.put((2, next(_qc), "cam", "sync_play_motion", {"name": "Reset"}))
    except Exception as e:
        print(f"Lỗi đẩy lệnh Queue: {e}")

def send_command(action: str) -> bool:
    """Xử lý logic Khóa, Cooldown và Gửi lệnh qua _send_to_robot"""
    global last_action, last_send_time
    now = time.time()
    
    # NẾU ĐANG KHÓA: Chặn mọi lệnh trừ Reset (stop)
    if is_system_locked and action != "stop":
        return False

    # Đưa tay xuống về trạng thái nghỉ thì luôn cho phép, không chờ phong ấn
    bypass_cooldown = (action == "stop")

    # Nếu đang trong thời gian phong ấn Pose
    if last_send_time > 0 and (now - last_send_time) < COOLDOWN_SEC and not bypass_cooldown:
        return False
        
    if action != last_action:
        _send_to_robot(action)
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
# HỖ TRỢ HIỂN THỊ CHỮ TIẾNG VIỆT LÊN FRAME
# ==========================================
def put_text_vi(img, text, position, font_size=20, color=(255, 255, 255)):
    """ Hàm vẽ text tiếng Việt chuẩn UTF-8 sử dụng Pillow """
    if not HAS_PIL:
        # Fallback về opencv text nếu k có thư viện Pillow
        cv2.putText(img, text, position, cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)
        return img
        
    # OpenCV đang dùng BGR, Pillow dùng RGB. 
    # Convert BGR -> RGB trước khi vẽ
    img_pil = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
    draw = ImageDraw.Draw(img_pil)
    
    try:
        # Load font Arial mặc định cực chuẩn của Windows
        font = ImageFont.truetype("arial.ttf", font_size)
    except IOError:
        font = ImageFont.load_default()
            
    # Vẽ chữ (tọa độ position x, y)
    b, g, r = color
    draw.text(position, text, font=font, fill=(r, g, b))
    
    # Ép trở lại OpenCV (RGB -> BGR)
    return cv2.cvtColor(np.array(img_pil), cv2.COLOR_RGB2BGR)

# ==========================================
# MAIN LOOP ĐƯỢC CHẠY TỪ LUỒNG MAIN_CONTROL
# ==========================================

def start_cam_control(cmd_queue=None):
    global command_queue
    global is_system_locked, unlock_timestamp, palm_pause_timestamp, palm_counter
    global last_action, last_send_time, pose_gesture_counter, confirmed_action, prev_wrist_pos
    
    command_queue = cmd_queue

    mp_holistic = mp.solutions.holistic
    holistic = mp_holistic.Holistic(min_detection_confidence=0.6, min_tracking_confidence=0.6)
    mp_pose = mp.solutions.pose
    mp_drawing = mp.solutions.drawing_utils

    cap = cv2.VideoCapture(1)

    print("=" * 60)
    print(" CHIẾN THẦN CAMERA YANSHEE (INTEGRATED)  |  Nhấn ESC để thoát ")
    print("=" * 60)
    print(" HƯỚNG DẪN XÁC THỰC 2 LỚP:")
    print(" [ĐỂ KHÓA] XÒE TAY 3s -> Chờ màn hình cam -> Đưa DISLIKE")
    print(" [ĐỂ MỞ]   XÒE TAY 3s -> Chờ màn hình cam -> Đưa LIKE")
    print("  └> Sau khi mở, Hệ thống báo BOOTING 3s trước khi sẵn sàng nhận Pose")
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
        # DISLIKE: CHỈ khóa cứng hệ thống khi đang xòe tay nghỉ 3s
        if active_sys_gesture == "dislike" and not is_system_locked and is_palm_paused:
            is_system_locked = True
            send_command("stop")
            confirmed_action = "stop"
            palm_pause_timestamp = 0 # Thoát pause, vào khóa cứng
        # LIKE: CHỈ mở khóa khi đang bị khóa VÀ đang trong cửa sổ xòe tay
        elif active_sys_gesture == "like" and is_system_locked and is_palm_paused:
            is_system_locked = False
            unlock_timestamp = now # Bắt đầu đếm ngược 3 giây chờ khởi động lại
            palm_pause_timestamp = 0 # Thoát pause

        # 1B. Nhận diện Xòe tay trong 3 giây (Kể cả khi đang Khóa hay Mở)
        if active_palm_gesture == "palm":
            palm_counter += 1
            if palm_counter >= palm_frames_needed:
                if not is_system_locked:
                    send_command("stop")
                    confirmed_action = "stop"
                palm_pause_timestamp = now  # Kích hoạt tạm khóa
                palm_counter = 0            # Reset bộ đếm
        else:
            palm_counter = 0

        # ================================================
        # 2. LOGIC POSE: GIƠ TAY, ĐẤM
        # ================================================
        current_pose_action = None
        label = "Trạng thái nhàn rỗi (IDLE)"
        color = (200, 200, 200)
        wrist_now = (0, 0)
        
        time_since_palm = now - palm_pause_timestamp
        is_palm_paused = (time_since_palm < PALM_PAUSE_DURATION) and not is_system_locked
        
        time_since_unlock = now - unlock_timestamp
        is_booting = (time_since_unlock < WAIT_AFTER_UNLOCK) and not is_system_locked
        
        # Chỉ nhận Pose khi KHÔNG bị khóa, KHÔNG chờ boot mở khóa, và KHÔNG ở trong trạng thái nghỉ xòe tay
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
                    current_pose_action = "punch_sideways_right"
                    label = "Đấm ngang móc (tay phải)"
                    color = (255, 0, 255)
                elif l_side:
                    current_pose_action = "punch_sideways_left"
                    label = "Đấm ngang móc (tay trái)"
                    color = (255, 0, 255)
                elif r_fwd:
                    current_pose_action = "punch_forward_right"
                    label = "Đấm thẳng (tay phải)"
                    color = (0, 0, 255)
                elif l_fwd:
                    current_pose_action = "punch_forward_left"
                    label = "Đấm thẳng (tay trái)"
                    color = (0, 0, 255)
                elif r_up and l_up:
                    current_pose_action = "victory"
                    label = "Hai tay (Chiến thắng)"
                    color = (0, 255, 255)
                elif r_up and not l_up:
                    current_pose_action = "raise_right"
                    label = "Một tay (Chào tạm biệt)"
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
        # 4. GIAO DIỆN HUD (GHI CHỮ TIẾNG VIỆT)
        # ================================================
        if is_system_locked:
            if is_palm_paused:
                cd = int(PALM_PAUSE_DURATION - time_since_palm)
                status_txt, col = f"ĐANG CHỜ MỞ KHÓA: {cd}s", (0, 165, 255)
                sys_label = "CHỈ NÚT LIKE BÂY GIỜ ĐỂ MỞ"
            else:
                status_txt, col = "HỆ THỐNG ĐÃ KHÓA (LOCKED)", (0, 0, 255)
                sys_label = "CẦN LẮC TAY (PALM) 3s TRƯỚC KHI MỞ"
        elif is_booting:
            cd = int(WAIT_AFTER_UNLOCK - time_since_unlock)
            status_txt, col = f"ĐANG KHỞI ĐỘNG... {cd}s", (0, 165, 255)
            sys_label = "ĐỢI TÍ TÍ (CÒN VÀI GIÂY CHUẨN BỊ)"
        elif is_palm_paused:
            cd = int(PALM_PAUSE_DURATION - time_since_palm)
            status_txt, col = f"ĐANG CHỜ KHÓA: {cd}s", (0, 165, 255)
            sys_label = "CHỈ NÚT DISLIKE BÂY GIỜ ĐỂ KHÓA"
        else:
            status_txt, col = "HỆ THỐNG ĐÃ SẴN SÀNG", (0, 255, 0)
            sys_label = "GIỮ TAY NHƯ VẬY (PALM) 3s ĐỂ TẠM DỪNG"

        # In chữ tiếng Việt
        image = put_text_vi(image, status_txt, (20, 30), font_size=24, color=col)
        image = put_text_vi(image, sys_label, (20, 65), font_size=18, color=(255, 255, 255))

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
                p_stat = f"ĐANG XÁC THỰC... {pct}%"
                p_col = (0, 165, 255)
            else:
                p_stat = "IDLE (Chờ Lệnh)"
                p_col = (200, 200, 200)

            # In tiếng Việt
            image = put_text_vi(image, f"HÀNH ĐỘNG: {label}", (w - 380, 40), font_size=20, color=color)
            image = put_text_vi(image, p_stat, (w - 380, 75), font_size=16, color=p_col)
            
            # Trạng thái Phong ấn tay (Cooldown)
            time_left = COOLDOWN_SEC - (now - last_send_time)
            if last_send_time > 0 and time_left > 0:
                image = put_text_vi(image, f"PHONG ẤN LỆNH... {int(time_left)}s", (w - 380, 100), font_size=16, color=(0, 0, 255))

        image = put_text_vi(image, "GIAO TIẾP QUA: QUEUE_MAIN_CONTROL", (10, h - 30), font_size=16, color=(50, 255, 50))
        cv2.imshow("Yanshee Gesture AI  |  ESC = Thoat", image)
        
        if cv2.waitKey(5) & 0xFF == 27:
            break

    cap.release()
    cv2.destroyAllWindows()
    print("\n[Hệ thống] Đã tắt Camera và đóng ứng dụng.")

if __name__ == "__main__":
    start_cam_control()