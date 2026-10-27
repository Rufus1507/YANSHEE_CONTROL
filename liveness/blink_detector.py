"""Blink detection via Eye Aspect Ratio (EAR)."""
import numpy as np


# MediaPipe Face Mesh eye landmark indices
_LEFT_EYE = [33, 160, 158, 133, 153, 144]
_RIGHT_EYE = [362, 385, 387, 263, 373, 380]


def _ear(landmarks, indices):
    """Compute Eye Aspect Ratio for a set of 6 eye landmark indices."""
    pts = [np.array(landmarks[i][:2]) for i in indices]
    # vertical distances
    v1 = np.linalg.norm(pts[1] - pts[5])
    v2 = np.linalg.norm(pts[2] - pts[4])
    # horizontal distance
    h = np.linalg.norm(pts[0] - pts[3])
    return (v1 + v2) / (2.0 * h + 1e-6)


class BlinkDetector:
    # Nâng EAR_THRESHOLD lên 0.22 và giảm CONSEC_FRAMES xuống 2
    # → Nhạy hơn với mắt nhỏ khi đứng xa, tránh cần chớp mạnh
    EAR_THRESHOLD = 0.22
    CONSEC_FRAMES = 2

    def __init__(self):
        self.counter = 0
        self.blinks = 0

    def reset(self):
        self.counter = 0
        self.blinks = 0

    def update(self, landmarks) -> int:
        """Feed one frame of landmarks. Returns total blink count so far."""
        left_ear = _ear(landmarks, _LEFT_EYE)
        right_ear = _ear(landmarks, _RIGHT_EYE)
        avg = (left_ear + right_ear) / 2.0

        if avg < self.EAR_THRESHOLD:
            self.counter += 1
        else:
            if self.counter >= self.CONSEC_FRAMES:
                self.blinks += 1
            self.counter = 0
        return self.blinks
