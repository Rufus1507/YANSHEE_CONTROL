import cv2
import numpy as np
from config import FRAME_WIDTH, FRAME_HEIGHT

# 3-D reference model points (generic face)
_MODEL_POINTS = np.array([
    (0.0, 0.0, 0.0),           # Nose tip        (landmark 1)
    (0.0, -330.0, -65.0),      # Chin             (landmark 152)
    (-225.0, 170.0, -135.0),   # Left eye corner  (landmark 33)
    (225.0, 170.0, -135.0),    # Right eye corner (landmark 263)
    (-150.0, -150.0, -125.0),  # Left mouth corner(landmark 61)
    (150.0, -150.0, -125.0),   # Right mouth corner(landmark 291)
], dtype=np.float64)

# Corresponding MediaPipe indices
_LANDMARK_IDS = [1, 152, 33, 263, 61, 291]

class HeadPoseEstimator:
    def __init__(self, frame_width: int = FRAME_WIDTH, frame_height: int = FRAME_HEIGHT):
        focal = frame_width
        self.camera_matrix = np.array([
            [focal, 0, frame_width / 2],
            [0, focal, frame_height / 2],
            [0, 0, 1],
        ], dtype=np.float64)
        self.dist_coeffs = np.zeros((4, 1), dtype=np.float64)
        self.size = (frame_width, frame_height)

    def estimate(self, landmarks) -> tuple | None:
        """
        Given full normalised landmarks, return (yaw, pitch, roll) in degrees,
        or None on failure.
        """
        image_points = np.array([
            (landmarks[i][0] * self.size[0], landmarks[i][1] * self.size[1])
            for i in _LANDMARK_IDS
        ], dtype=np.float64)

        ok, rvec, tvec = cv2.solvePnP(
            _MODEL_POINTS, image_points,
            self.camera_matrix, self.dist_coeffs,
            flags=cv2.SOLVEPNP_ITERATIVE,
        )
        if not ok:
            return None

        rmat, _ = cv2.Rodrigues(rvec)
        angles, _, _, _, _, _ = cv2.RQDecomp3x3(rmat)
        yaw, pitch, roll = angles[1], angles[0], angles[2]
        return float(yaw), float(pitch), float(roll)
