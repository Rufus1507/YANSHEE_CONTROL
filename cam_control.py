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
try:
    import openadk
    from openadk.rest import ApiException
except ImportError as e:
    if "chardet" in str(e):
        print("[LỖI] Thiếu thư viện 'chardet' (dependency của openadk)!")
        print("      Vui lòng chạy lệnh: pip install chardet\n")
    else:
        print("[LỖI] Thư viện openadk bị thiếu hoặc lỗi:", e)
        print("      Vui lòng chạy: pip install https://github.com/UBTEDU/Yan_ADK/archive/latest.tar.gz")
    sys.exit(1)

# --- Cấu hình kết nối Yanshee ---
ROBOT_IP = "192.168.150.75"   # Thay bằng IP thật của Yanshee
BASE_URL = f"http://{ROBOT_IP}:9090/v1"

# Khởi tạo openadk client
_configuration = openadk.Configuration()
_configuration.host = BASE_URL
_client = openadk.ApiClient(_configuration)
_motions_api = openadk.MotionsApi(_client)

# Chống spam lệnh
last_action = None
last_send_time = 0
COOLDOWN_SEC = 3.0   # Giây chờ tối thiểu giữa 2 lần gửi cùng action

# Ánh xạ tên cử chỉ -> tên motion hợp lệ của Yanshee (phân biệt hoa thường)
# Các Motion của Yanshee đã được NSX giới hạn góc servo an toàn để không gãy tay
MOTION_MAP = {
    "raise_left": "LeftSidePunch",   # Yanshee không có RaiseLeftHand, dùng tạm đấm tay trái
    "raise_right": "RaiseRightHand", # Giơ tay phải
    "stop": "Reset",                 # Đưa robot về tư thế đứng nghỉ an toàn
}


def _send_to_robot(action: str):
    """Gọi API openadk để gửi motion command tới Yanshee."""
    motion_name = MOTION_MAP.get(action, action)
    try:
        print(f"[{time.strftime('%H:%M:%S')}] Đang gửi: {action} (motion: {motion_name})...")
        motion_param = openadk.MotionsParameter(
            name=motion_name,
            repeat=1,
            speed="normal"
        )
        motion_request = openadk.MotionsOperation(
            operation="start",
            motion=motion_param
        )
        response = _motions_api.put_motions(body=motion_request)
        print(f"[{time.strftime('%H:%M:%S')}] Thành công: {action} | {response.msg if hasattr(response, 'msg') else 'OK'}")
    except ApiException as e:
        print(f"[{time.strftime('%H:%M:%S')}] API lỗi ({e.status}): {e.reason}")
    except Exception as e:
        print(f"[{time.strftime('%H:%M:%S')}] Không kết nối được Yanshee ({type(e).__name__})")


def send_command_async(action: str):
    """Gửi lệnh ngầm (thread riêng) để camera không bị giật lag."""
    threading.Thread(target=_send_to_robot, args=(action,), daemon=True).start()


def send_command(action: str):
    """Gửi lệnh nếu hành động thay đổi hoặc sau COOLDOWN_SEC giây."""
    global last_action, last_send_time
    now = time.time()
    if action != last_action or (now - last_send_time) > COOLDOWN_SEC:
        send_command_async(action)
        last_action = action
        last_send_time = now


# --- Khởi tạo MediaPipe Pose ---
mp_pose = mp.solutions.pose
pose = mp_pose.Pose(min_detection_confidence=0.7, min_tracking_confidence=0.7)
mp_drawing = mp.solutions.drawing_utils

cap = cv2.VideoCapture(0)

print("=" * 50)
print(" Yanshee Gesture Control  |  Nhấn ESC để thoát")
print("=" * 50)
print(f" Robot IP : {ROBOT_IP}")
print(f" Port     : 9090  |  Library: openadk")
print("=" * 50)
print(" Cử chỉ (Hướng như soi gương):")
print("   Giơ tay TRÁI   -> Yanshee đánh tay trái (LeftSidePunch)")
print("   Giơ tay PHẢI   -> Yanshee giơ tay phải (RaiseRightHand)")
print("   Bỏ tay xuống   -> Yanshee nghỉ (Reset)")
print("=" * 50)

while cap.isOpened():
    success, image = cap.read()
    if not success:
        break

    # Lật ngang (mirror) rồi chuyển BGR->RGB cho MediaPipe
    image = cv2.cvtColor(cv2.flip(image, 1), cv2.COLOR_BGR2RGB)
    results = pose.process(image)
    image = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)

    current_action = None

    if results.pose_landmarks:
        mp_drawing.draw_landmarks(image, results.pose_landmarks, mp_pose.POSE_CONNECTIONS)

        landmarks = results.pose_landmarks.landmark

        # Lấy tọa độ cổ tay và mũi
        left_wrist  = landmarks[mp_pose.PoseLandmark.LEFT_WRIST.value]
        right_wrist = landmarks[mp_pose.PoseLandmark.RIGHT_WRIST.value]
        nose        = landmarks[mp_pose.PoseLandmark.NOSE.value]
        left_shoulder = landmarks[mp_pose.PoseLandmark.LEFT_SHOULDER.value]

        # Ngưỡng nâng tay: cổ tay phải cao hơn MŨI và visibility > 0.5
        # (Ảnh đã flip: right_wrist MediaPipe = tay TRÁI thực tế)
        is_left_raised  = (right_wrist.y < nose.y) and (right_wrist.visibility > 0.5)
        is_right_raised = (left_wrist.y  < nose.y) and (left_wrist.visibility  > 0.5)

        # Xác định hành động dựa trên ngưỡng giơ tay (giới hạn an toàn, tránh nhận spam rung giật)
        if is_left_raised and not is_right_raised:
            current_action = "raise_left"
            label = "RAISE LEFT HAND (PUNCH)"
            color = (0, 255, 0)
        elif is_right_raised and not is_left_raised:
            current_action = "raise_right"
            label = "RAISE RIGHT HAND"
            color = (0, 0, 255)

        if current_action:
            cv2.putText(image, f"ACTION: {label}", (30, 50),
                        cv2.FONT_HERSHEY_SIMPLEX, 1.0, color, 2, cv2.LINE_AA)

    # Trạng thái dừng: gửi lệnh Reset đưa tay xuống an toàn khi người dùng thả tay
    if current_action:
        send_command(current_action)
    else:
        if last_action is not None and last_action != "stop":
            send_command("stop")
            last_action = "stop"

    # Hiển thị thông tin kết nối góc trên phải
    h, w = image.shape[:2]
    conn_text = f"Yanshee: {ROBOT_IP}:9090"
    cv2.putText(image, conn_text, (10, h - 15),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (180, 180, 180), 1, cv2.LINE_AA)

    cv2.imshow("Yanshee Gesture Control  |  ESC = Thoat", image)

    if cv2.waitKey(5) & 0xFF == 27:  # ESC
        break

cap.release()
cv2.destroyAllWindows()
print("\nĐã thoát.")