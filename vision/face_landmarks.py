"""
MediaPipe Face Mesh landmark extractor.
Returns 478 normalised (x, y, z) landmarks when `refine_landmarks=True`.
"""
import cv2
import numpy as np
import mediapipe as mp
from logs.logger import get_logger

logger = get_logger(__name__)


class FaceLandmarks:
    def __init__(self):
        self.mesh = mp.solutions.face_mesh.FaceMesh(
            static_image_mode=False,
            max_num_faces=1,
            refine_landmarks=True,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5,
        )

    def extract(self, image: np.ndarray, bbox=None):
        """Return list of (x, y, z) normalised landmarks for the full frame, or None."""
        if bbox is None:
            rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            results = self.mesh.process(rgb)
            if not results.multi_face_landmarks:
                return None
            return [
                (lm.x, lm.y, lm.z)
                for lm in results.multi_face_landmarks[0].landmark
            ]
        
        # Multi-person safe: crop and map back
        x, y, w, h = bbox
        h_img, w_img = image.shape[:2]
        
        size = int(max(w, h) * 1.5)
        cx, cy = x + w//2, y + h//2
        nx = max(0, cx - size//2)
        ny = max(0, cy - size//2)
        nw = min(w_img - nx, size)
        nh = min(h_img - ny, size)
        
        crop = image[ny:ny+nh, nx:nx+nw]
        if crop.size == 0:
            return None
            
        rgb = cv2.cvtColor(crop, cv2.COLOR_BGR2RGB)
        results = self.mesh.process(rgb)
        if not results.multi_face_landmarks:
            return None
            
        lms = []
        for lm in results.multi_face_landmarks[0].landmark:
            px = nx + lm.x * nw
            py = ny + lm.y * nh
            lms.append((px / w_img, py / h_img, lm.z))
        return lms
