import cv2
import numpy as np
from typing import List, Tuple, Optional
from logs.logger import get_logger

logger = get_logger(__name__)

def align_face(
    frame: np.ndarray,
    bbox: Tuple[int, int, int, int],
    landmarks: Optional[List[Tuple[float, float, float]]] = None
) -> Optional[np.ndarray]:
    """
    Căn chỉnh khuôn mặt về 112x112 dùng cho model nhúng.
    Nếu có landmarks, dùng thuật toán xoay theo mắt.
    Nếu không, fallback cắt theo bbox và resize.
    """
    if frame is None or frame.size == 0:
        return None

    h_img, w_img = frame.shape[:2]
    x, y, w, h = bbox

    # Fallback crop bbox
    def fallback_crop():
        # Mở rộng bbox 20%
        cx, cy = x + w//2, y + h//2
        size = int(max(w, h) * 1.2)
        nx = max(0, cx - size//2)
        ny = max(0, cy - size//2)
        nw = min(w_img - nx, size)
        nh = min(h_img - ny, size)
        
        crop = frame[ny:ny+nh, nx:nx+nw]
        if crop.size == 0:
            return None
        return cv2.resize(crop, (112, 112))

    if not landmarks or len(landmarks) < 468:
        return fallback_crop()

    try:
        # Approximate eye centres from MediaPipe landmark indices
        left_eye_indices = [33, 133, 160, 158, 153, 144]
        right_eye_indices = [362, 263, 387, 385, 380, 373]
        
        left_eye = np.mean([np.array(landmarks[i][:2]) for i in left_eye_indices], axis=0)
        right_eye = np.mean([np.array(landmarks[i][:2]) for i in right_eye_indices], axis=0)

        # Convert normalised → pixel coords
        left = np.array([left_eye[0] * w_img, left_eye[1] * h_img])
        right = np.array([right_eye[0] * w_img, right_eye[1] * h_img])

        eye_center = ((left + right) / 2).astype(int)
        angle = float(np.degrees(np.arctan2(right[1] - left[1], right[0] - left[0])))
        eye_dist = np.linalg.norm(right - left)

        if eye_dist < 10:  # Quá nhỏ để xoay chính xác
            return fallback_crop()

        scale = 60.0 / eye_dist  # map eye distance to ~60 px in 112×112

        M = cv2.getRotationMatrix2D(tuple(eye_center.astype(float)), angle, scale)
        # Shift so centre of eyes lands at (56, 44) in the output
        M[0, 2] += 56 - eye_center[0]
        M[1, 2] += 44 - eye_center[1]

        aligned = cv2.warpAffine(frame, M, (112, 112), flags=cv2.INTER_LINEAR)
        return aligned
        
    except Exception as e:
        logger.warning(f"Lỗi align_face, dùng fallback crop: {e}")
        return fallback_crop()
