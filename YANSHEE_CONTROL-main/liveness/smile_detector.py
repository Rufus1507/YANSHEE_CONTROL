"""Smile detection via mouth width / face width ratio."""
import numpy as np


class SmileDetector:
    # Tỉ lệ chiều rộng miệng / chiều rộng khuôn mặt (khoảng cách 2 má)
    # Bình thường ~ 0.35 - 0.40. Khi cười khóe miệng kéo giãn nên tỉ lệ sẽ > 0.45.
    # Tỷ lệ chiều rộng miệng / chiều rộng khuôn mặt (khoảng cách 2 má)
    # Giảm từ 0.44 → 0.42 để nhận tốt hơn khi đứng xa camera
    RATIO_THRESHOLD = 0.42

    def __init__(self):
        self.smiling = False

    def reset(self):
        self.smiling = False

    def update(self, landmarks) -> bool:
        """Return True if the person is smiling."""
        # Khóe miệng trái và phải
        left = np.array(landmarks[61][:2])
        right = np.array(landmarks[291][:2])
        mouth_width = np.linalg.norm(left - right)
        
        # Má trái và má phải (lấy làm chuẩn chiều rộng khuôn mặt)
        face_left = np.array(landmarks[234][:2])
        face_right = np.array(landmarks[454][:2])
        face_width = np.linalg.norm(face_left - face_right) + 1e-6
        
        ratio = mouth_width / face_width
        
        self.smiling = ratio > self.RATIO_THRESHOLD
        return self.smiling
