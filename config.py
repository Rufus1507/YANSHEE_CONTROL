import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

# Camera settings
CAMERA_INDEX: int = 0
FRAME_WIDTH: int = 640        # Giảm từ 1280 → 640 để giảm lag
FRAME_HEIGHT: int = 480       # Giảm từ 720 → 480 để giảm lag
JPEG_QUALITY: int = 70        # Giảm nhẹ chất lượng JPEG để stream nhanh hơn
CAMERA_RECONNECT_DELAY: int = 3
MAX_FAIL_FRAMES: int = 15

# Pipeline throttle — giới hạn số lần xử lý recognition/giây để tránh CPU quá tải
PIPELINE_PROCESS_MAX_FPS: int = 15   # Chỉ xử lý tối đa 15 frame/giây

# Dashboard settings
DASHBOARD_HOST: str = "127.0.0.1"
DASHBOARD_PORT: int = 8000

# Database settings
DATABASE_PATH: str = os.path.join(BASE_DIR, "data", "yanshee_faceid.db")

# ── Face Recognition Settings ─────────────────────────────────
FACE_EMBEDDING_DIM: int = 512
FACE_MODEL_NAME: str = "code_chay_512"

# Cosine similarity (Pearson Correlation) — Code Chay v2 + Robust Matcher + Zero Centering
# Nhờ kỹ thuật Zero-Centering, điểm người lạ sẽ rớt xuống cực thấp (< 0.70)
# Đặt ngưỡng 0.82 là siêu khắt khe, hoàn toàn miễn nhiễm với người lạ.
FACE_SIMILARITY_THRESHOLD: float = 0.88

# Khoảng cách tối thiểu giữa người giống nhất và người giống thứ 2
FACE_SIMILARITY_MARGIN: float = 0.020
FACE_MIN_DET_SCORE: float = 0.7           # Tăng độ tin cậy tối thiểu khi phát hiện mặt (từ 0.5 -> 0.7)

# Legacy Euclidean threshold (kept for reference, NOT used in new matcher)
FACE_THRESHOLD: float = 0.42

FACE_DETECTION_CONFIDENCE: float = 0.7  # Tăng lên 0.7 để chắc chắn bắt đúng khuôn mặt
UNKNOWN_COOLDOWN_SECONDS: int = 2        # Giảm cooldown để phản hồi khách lạ nhanh hơn
RECOGNITION_COOLDOWN_SECONDS: int = 2

# Registration
MAX_REGISTER_IMAGES_PER_USER: int = 20

# Smoothing & Consistency
REQUIRED_CONSISTENT_FRAMES: int = 5    # Tăng từ 2 lên 5 để kiểm tra kỹ lưỡng liên tục trước khi quyết định
FRAME_TOLERANCE: int = 1
LOW_CONFIDENCE_COOLDOWN_SECONDS: int = 2

# Stranger (Unknown face detected)
STRANGER_LABEL: str = "Khách Lạ"      # Hiển thị khi phát hiện mặt chưa đăng ký

# Face Quality — Khắt khe hơn để đảm bảo thấy rõ mặt mới cho qua
MIN_FACE_SIZE: int = 70              # Tăng từ 40 -> 70 để yêu cầu đứng gần và rõ mặt
MIN_FACE_QUALITY: float = 0.75       # Tăng từ 0.60 -> 0.75 để loại ảnh nhiễu/kém chất lượng
MIN_BLUR_THRESHOLD: float = 80.0     # Tăng từ 40 -> 80: mặt phải thật rõ, không bị mờ nhòe
MIN_BRIGHTNESS: float = 40.0         # Tăng từ 30 -> 40: yêu cầu ánh sáng tốt hơn
MAX_BRIGHTNESS: float = 240.0        # Tăng từ 230→240

# Registration-first workflow
REQUIRE_REGISTERED_USER_BEFORE_MAIN: bool = False
EXIT_IF_NO_REGISTERED_USERS: bool = False
SHUTDOWN_ON_UNKNOWN_USER: bool = False
UNKNOWN_CONFIRM_FRAMES: int = 10
UNKNOWN_SHUTDOWN_DELAY_SECONDS: int = 3

# Liveness settings
LIVENESS_ENABLED: bool = True
LIVENESS_TIMEOUT: int = 10  # seconds
LIVENESS_RANDOM_CHALLENGE_COUNT: int = 2
BLINK_REQUIRED_COUNT: int = 1

# Robot settings
ROBOT_ENABLED: bool = True
ROBOT_IP: str = "10.165.178.75"
ROBOT_PORT: int = 9090
ROBOT_TIMEOUT: int = 3  # seconds
AUTO_RECONNECT: bool = True
GREETING_COOLDOWN_SECONDS: int = 10

# Role actions
# Motion names must match actual robot motions (from GET /v1/motions/list):
#   RaiseRightHand, Hug, Victory, Forward, PushUp, Reset, etc.
ROLE_ACTIONS = {
    "Admin": {
        "speech": "Hello admin {name}.",
        "motion": "RaiseRightHand"
    },
    "Teacher": {
        "speech": "Hello teacher {name}.",
        "motion": "Hug"
    },
    "Student": {
        "speech": "Hello student {name}.",
        "motion": "RaiseRightHand"
    },
    "Guest": {
        "speech": "Hello guest {name}.",
        "motion": "RaiseRightHand"
    },
    "Unknown": {
        "speech": "Sorry, I haven't recognized you yet",
        "motion": None
    },
    "Stranger": {
        "speech": "Hello stranger, you are not registered in the system, please register and try again..",
        "motion": None
    },
}

# Configs for Robot Reset
ROBOT_HOME_MOTION: str = "Reset"  # Verified from /v1/motions/list API
ROBOT_RESET_DELAY: float = 2.5    # Wait time (seconds) after greeting finishes before resetting


LOG_PATH: str = os.path.join(BASE_DIR, "logs", "system.log")

# ---------------------------------------------------
# Cấu hình camera Yanshee (được bật khi YANSHEE_CAMERA_ENABLED=True)
YANSHEE_CAMERA_ENABLED: bool = True          # bật/tắt camera Yanshee
YANSHEE_IP: str = "10.165.178.75"            # IP robot (cùng với ROBOT_IP)
YANSHEE_STREAM_PORT: int = 8000              # cổng stream MJPEG
YANSHEE_STREAM_TIMEOUT: float = 5.0          # timeout kết nối HTTP (s)
YANSHEE_STREAM_RESOLUTION: str = "1280x720"   # chỉ dành cho diagnostic
CAMERA_RECONNECT_DELAY: int = 2               # delay khi reconnect
CAMERA_HEALTH_TIMEOUT: float = 0.5           # nếu không có frame trong thời gian này → error
MAX_FRAME_QUEUE: int = 2                      # giữ tối đa 2 frame (newest + backup)

# ── Enrollment auto-sampling (24 diverse samples) ─────────────────────────
# [CALIBRATION] Adjust based on how diverse the enrollment environment is.
ENROLLMENT_TARGET_SAMPLES: int = 24    # target number of diverse samples
ENROLLMENT_MAX_SAMPLES: int = 30       # hard cap to avoid bloat
ENROLLMENT_DUPLICATE_THRESHOLD: float = 0.93  # cosine-sim above = duplicate, skip
ENROLLMENT_CAPTURE_COOLDOWN: float = 0.4       # seconds between auto-captures

# ── Temporal voting ────────────────────────────────────────────────────────
# [CALIBRATION] Larger window = more stable but slower to confirm.
VOTING_WINDOW_SIZE: int = 7           # rolling history window per track
MIN_VOTES_TO_ACCEPT: int = 5          # min votes needed to confirm identity

# ── Multi-person tracking ──────────────────────────────────────────────────
# [CALIBRATION] Increase TRACK_MAX_MISSED_FRAMES if camera drops frames often.
TRACK_MAX_MISSED_FRAMES: int = 8      # frames without match before dropping track
TRACK_IOU_THRESHOLD: float = 0.25     # IoU threshold to re-associate existing track
TRACK_MAX_CENTER_DISTANCE: int = 120  # px — fallback when IoU is 0 (e.g. head turn)

# ── Quality gate ───────────────────────────────────────────────────────────
# [CALIBRATION] TOO_SMALL_FACE_THRESHOLD < MIN_FACE_SIZE must always hold.
TOO_SMALL_FACE_THRESHOLD: int = 50    # below = INSUFFICIENT_VISUAL_INFORMATION (not UNKNOWN)
MAX_HEAD_ROTATION_YAW: float = 40.0   # degrees — beyond = quality fail for recognition
MAX_HEAD_ROTATION_PITCH: float = 35.0 # degrees

# ── Liveness per track ─────────────────────────────────────────────────────
LIVENESS_PER_TRACK: bool = True        # each track has its own liveness state (always true)
