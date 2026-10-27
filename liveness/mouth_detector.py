"""Mouth open detection via vertical/horizontal lip distance ratio.

Scale-invariant: sử dụng tỷ lệ chiều cao miệng / chiều rộng miệng (MAR)
thêm debounce: phải há hẳn rồi đóng lại mới thoả mãn → tránh mồm hé sẵn.
"""
import numpy as np


# MediaPipe Face Mesh — điểm miệng
_MOUTH_TOP    = 13   # đỉnh trên môi
_MOUTH_BOT    = 14   # đỉnh dưới môi
_MOUTH_LEFT   = 61   # khóe trái
_MOUTH_RIGHT  = 291  # khóe phải


class MouthOpenDetector:
    """
    Má định (MAR = Mouth Aspect Ratio) = dọc / ngang.
    Giá trị bình thường ~ 0.05-0.15. Há rã ~ 0.35+.
    Scale-invariant: không bị ảnh hưởng khi đứng xa/gần camera.
    """
    # Há to: MAR > OPEN_THRESH trong CONSEC_FRAMES liên tiếp
    OPEN_THRESH   = 0.35  # ~ há rõ ràng
    CLOSE_THRESH  = 0.15  # đóng lại
    CONSEC_FRAMES = 3     # số frame liên tiếp phải đạt

    def __init__(self):
        self.reset()

    def reset(self):
        self._open_count  = 0   # frame liên tiếp đang há
        self._was_open    = False
        self.opened       = False  # đã phát hiện há thành công

    @staticmethod
    def _mar(landmarks) -> float:
        top    = np.array(landmarks[_MOUTH_TOP][:2])
        bot    = np.array(landmarks[_MOUTH_BOT][:2])
        left   = np.array(landmarks[_MOUTH_LEFT][:2])
        right  = np.array(landmarks[_MOUTH_RIGHT][:2])
        h = np.linalg.norm(top - bot)
        w = np.linalg.norm(left - right) + 1e-6
        return h / w

    def update(self, landmarks) -> bool:
        """Return True khi phát hiện há miệng hẳn (mời 1 lần / lần có debounce)."""
        if self.opened:
            return True  # đã pass rồi — giữ nguyên

        mar = self._mar(landmarks)

        if mar > self.OPEN_THRESH:
            self._open_count += 1
            if self._open_count >= self.CONSEC_FRAMES:
                self._was_open = True
        else:
            self._open_count = 0

        # Chỉ thoả mãn khi đã há to (đủ CONSEC frames)
        if self._was_open:
            self.opened = True

        return self.opened
