"""
=== YANSHEE GESTURE CONTROL ===
Điều khiển robot Yanshee bằng cử chỉ tay qua camera.
Sử dụng thư viện chính thức: openadk (Yan_ADK)
    pip install https://github.com/UBTEDU/Yan_ADK/archive/latest.tar.gz

Cử chỉ:
  - Giơ tay TRÁI  -> robot rẽ trái  (turn_left)
  - Giơ tay PHẢI  -> robot rẽ phải  (turn_right)
  - Giơ 2 tay     -> robot đi thẳng (forward)
  - Bỏ tay xuống  -> robot dừng     (stop)
"""

import cv2
import mediapipe as mp
import threading
import time
import sys

# --- Kiểm tra thư viện openadk ---
from YanAPI import YanAPI

# --- Cấu hình kết nối Yanshee ---
ROBOT_IP = "10.176.138.75"   # IP của Yanshee
try:
    robot = YanAPI(ip_address=ROBOT_IP)
    print(f"Kết nối Yanshee tại {ROBOT_IP} thành công!")
except Exception as e:
    print(f"Lỗi kết nối API: {e}")
    sys.exit(1)

# Chống spam lệnh
last_action = None
last_send_time = 0
COOLDOWN_SEC = 10.0   # Tạm dừng 10s sau khi nhận lệnh đầu tiên


def _send_to_robot(action: str):
    """Xử lý và gửi các chuỗi động tác thông qua YanAPI"""
    print(f"[{time.strftime('%H:%M:%S')}] Nhận lệnh: {action}")
    try:
        if action == "raise_right":
            # Giơ tay phải -> robot giơ tay phải
            robot.sync_play_motion(name="RaiseRightHand")
            
        elif action == "victory":
            # Giơ 2 tay lên cao -> robot chiến thắng
            robot.sync_play_motion(name="Victory")
            
        elif action == "punch_forward":
            # Đấm lên trước -> robot đấm thẳng (Sử dụng Fight_LHit/RHit)
            robot.sync_play_motion(name="Fight_RHit")
            time.sleep(1.5) # Chờ motion thực hiện
            robot.sync_play_motion(name="Fight_LHit")
            
        elif action == "punch_sideways":
            # Đấm sang ngang -> robot đấm ngang (Sử dụng SidePunch)
            robot.sync_play_motion(name="LeftSidePunch")
            time.sleep(1.5)
            robot.sync_play_motion(name="RightSidePunch")
            
        elif action == "stop":
            robot.sync_play_motion(name="Reset")

        print(f"[{time.strftime('%H:%M:%S')}] Hoàn thành: {action}")
    except Exception as e:
        print(f"Lỗi điều khiển robot: {e}")


def send_command_async(action: str):
    threading.Thread(target=_send_to_robot, args=(action,), daemon=True).start()


def send_command(action: str):
    global last_action, last_send_time
    now = time.time()
    
    # 1. Nếu đang trong thời gian phong ấn 10s -> Hủy mọi hành động xâm nhập
    if last_send_time > 0 and (now - last_send_time) < COOLDOWN_SEC:
        return
        
    # 2. Hết phong ấn -> Bắt đầu nhận lệnh mới
    if action != last_action:
        send_command_async(action)
        last_action = action
        
        # Đặc cách 1: Nếu gửi lệnh reset (stop) hoặc chỉ Giơ tay (raise_right)
        # thì KHÔNG bị khóa 10s chờ, giúp người dùng có thể bỏ tay xuống là robot nhả liền.
        if action in ["stop", "raise_right"]:
            last_send_time = 0 
        else:
            last_send_time = now


# --- Khởi tạo MediaPipe Pose ---
mp_pose = mp.solutions.pose
pose = mp_pose.Pose(min_detection_confidence=0.7, min_tracking_confidence=0.7)
mp_drawing = mp.solutions.drawing_utils

cap = cv2.VideoCapture(1)

print("=" * 60)
print(" CHIẾN THẦN CAMERA YANSHEE (YanAPI)  |  Nhấn ESC để thoát ")
print("=" * 60)
print(" Cử chỉ hiện tại:")
print("   1. Giơ tay CÁNH TAY PHẢI lên   -> Yanshee giơ tay phải")
print("   2. Giơ CẢ 2 TAY lên cao        -> Yanshee chiến thắng")
print("   3. Đấm THẲNG TỚI TRƯỚC mặt     -> Yanshee đấm phải, rồi trái")
print("   4. Đấm SANG NGANG (Mở sải tay) -> Yanshee đấm trái ngang, phải ngang")
print("   5. Bỏ tay xuống nghỉ           -> Yanshee Reset đứng im")
print("=" * 60)

while cap.isOpened():
    success, image = cap.read()
    if not success:
        break

    # Lật ngang (mirror) ảnh như gương
    image = cv2.flip(image, 1)
    # Chuyển BGR->RGB cho MediaPipe
    rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    results = pose.process(rgb_image)

    current_action = None

    if results.pose_landmarks:
        mp_drawing.draw_landmarks(image, results.pose_landmarks, mp_pose.POSE_CONNECTIONS)
        landmarks = results.pose_landmarks.landmark

        # Do là ảnh lật gương, MP đánh nhãn bị nghịch bên so với cơ thể thật,
        # vì vậy: MP_LEFT_WRIST sẽ đính vào TAY PHẢI CỦA NGƯỜI
        user_right_wrist = landmarks[mp_pose.PoseLandmark.LEFT_WRIST.value]
        user_left_wrist  = landmarks[mp_pose.PoseLandmark.RIGHT_WRIST.value]
        
        user_right_shoulder = landmarks[mp_pose.PoseLandmark.LEFT_SHOULDER.value]
        user_left_shoulder  = landmarks[mp_pose.PoseLandmark.RIGHT_SHOULDER.value]
        
        nose = landmarks[mp_pose.PoseLandmark.NOSE.value]

        # Độ rộng 2 vai
        shoulder_width = abs(user_left_shoulder.x - user_right_shoulder.x) + 0.01

        # Trạng thái Visiblity chung
        r_vis = user_right_wrist.visibility > 0.5
        l_vis = user_left_wrist.visibility > 0.5

        # 1. Trạng thái GIƠ TAY LÊN CAO (Cao hơn mũi)
        r_up = r_vis and (user_right_wrist.y < nose.y)
        l_up = l_vis and (user_left_wrist.y < nose.y)

        # 2. Trạng thái ĐẤM NGANG (Cổ tay xa cơ thể, cao ngang vai)
        # Trên gương: Tay phải ở sát viền phải (x lớn), tay trái viền trái (x nhỏ)
        r_side = r_vis and (user_right_wrist.x > user_right_shoulder.x + shoulder_width * 0.7) and (abs(user_right_wrist.y - user_right_shoulder.y) < 0.2)
        l_side = l_vis and (user_left_wrist.x < user_left_shoulder.x - shoulder_width * 0.7)  and (abs(user_left_wrist.y - user_left_shoulder.y) < 0.2)

        # 3. Trạng thái ĐẤM TỚI TRƯỚC (Cổ tay dồn về trước khung hình, co vào tọa độ giữa ngực)
        r_fwd = r_vis and (abs(user_right_wrist.x - user_right_shoulder.x) < shoulder_width * 0.4) and (abs(user_right_wrist.y - user_right_shoulder.y) < 0.2) and not r_side and not r_up
        l_fwd = l_vis and (abs(user_left_wrist.x - user_left_shoulder.x) < shoulder_width * 0.4) and (abs(user_left_wrist.y - user_left_shoulder.y) < 0.2) and not l_side and not l_up

        color = (200, 200, 200)
        label = "IDLE"

        # Quyết định chọn action (Ưu tiên đấm -> chiến thắng -> giơ tay)
        if r_side or l_side:
            current_action = "punch_sideways"
            label = "PUNCH SIDEWAYS (Ngang)"
            color = (255, 0, 255)
        elif r_fwd or l_fwd:
            current_action = "punch_forward"
            label = "PUNCH FORWARD (Truoc)"
            color = (0, 0, 255)
        elif r_up and l_up:
            current_action = "victory"
            label = "VICTORY (2 tay)"
            color = (0, 255, 255)
        elif r_up and not l_up:
            current_action = "raise_right"
            label = "RAISE RIGHT HAND"
            color = (0, 255, 0)

        # Vẽ text debug cử chỉ
        cv2.putText(image, f"ACTION: {label}", (30, 50),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.0, color, 2, cv2.LINE_AA)

    # Hiển thị độ trễ phong ấn
    now = time.time()
    time_left = COOLDOWN_SEC - (now - last_send_time)
    
    if last_send_time > 0 and time_left > 0:
        cv2.putText(image, f"WAITING... {int(time_left)}s", (30, 90),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2, cv2.LINE_AA)


    # Gửi tín hiệu thực thi
    if current_action:
        send_command(current_action)
    else:
        if last_action is not None and last_action != "stop":
            send_command("stop")
            last_action = "stop"

    # Giao diện HUD cơ bản
    h, w = image.shape[:2]
    cv2.putText(image, f"API: {ROBOT_IP}", (10, h - 15),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (50, 255, 50), 2)

    cv2.imshow("Yanshee Gesture AI  |  ESC = Thoat", image)

    if cv2.waitKey(5) & 0xFF == 27:
        break

cap.release()
cv2.destroyAllWindows()
print("\n[Hệ thống] Đã tắt Camera và đóng ứng dụng.")