"""
Face detector using MediaPipe Face Detection.
Optimized: reuse RGB buffer, skip detection every N frames if no face.
"""
import numpy as np
import cv2
import mediapipe as mp
from events.event_bus import EventBus
from logs.logger import get_logger
from config import FACE_DETECTION_CONFIDENCE

logger = get_logger(__name__)

# Phát hiện khuôn mặt mỗi N frame khi không có khuôn mặt (tiết kiệm CPU)
# Giảm từ 2 xuống 1 để không bỏ lỡ mặt xuất hiện đột ngột
_SKIP_FRAMES_NO_FACE = 1


class FaceDetector:
    def __init__(self):
        self.detector = mp.solutions.face_detection.FaceDetection(
            model_selection=1,  # 0=short range (<=2m), 1=full range — phát hiện xa hơn
            min_detection_confidence=FACE_DETECTION_CONFIDENCE,
        )
        self._had_face_last = False
        self._skip_counter = 0

    def process(self, frame: np.ndarray):
        """
        Phát hiện tất cả khuôn mặt trong frame.
        Trả về list bounding boxes [(x, y, w, h), ...]
        """
        # Bỏ qua một số frame khi không có khuôn mặt để giảm tải CPU
        if not self._had_face_last:
            self._skip_counter += 1
            if self._skip_counter < _SKIP_FRAMES_NO_FACE:
                return []
            self._skip_counter = 0

        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = self.detector.process(rgb)

        if not results.detections:
            self._had_face_last = False
            return []

        self._had_face_last = True

        bboxes = []
        h, w = frame.shape[:2]
        for d in results.detections:
            bb = d.location_data.relative_bounding_box
            x = max(int(bb.xmin * w), 0)
            y = max(int(bb.ymin * h), 0)
            bw = min(int(bb.width * w), w - x)
            bh = min(int(bb.height * h), h - y)
            
            # Lọc các bounding box quá nhỏ hoặc không hợp lệ
            if bw > 20 and bh > 20:  # Giảm từ 30→20 để bắt mặt nhỏ hơn
                bboxes.append((x, y, bw, bh))

        return bboxes
