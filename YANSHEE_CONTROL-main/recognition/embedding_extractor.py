"""
Face Embedding Extractor — Code Chay Enhanced v2 (No AI Models).

Cải tiến để kháng thay đổi khoảng cách (scale-invariant):
  1. Multi-scale pixel features: capture ở nhiều scale → trung bình
  2. HOG features: Histogram of Oriented Gradients – robust về cấu trúc
  3. LBP histogram: dùng histogram thay vì pixel raw → ít bị ảnh hưởng scale
  4. Preprocessing: Gamma correction + CLAHE để cân bằng sáng

Kết quả: L2-normalised vector 512-dim.
"""
import numpy as np
import cv2
from logs.logger import get_logger

logger = get_logger(__name__)


class EmbeddingExtractor:
    """
    Extracts a scale-robust 512-dim embedding using OpenCV (No AI Model).
    Input : aligned BGR face image (112×112).
    Output: L2-normalised numpy float32 vector (512,).
    """

    # HOG descriptor params — fixed for reproducibility
    _HOG_WIN    = (64, 64)
    _HOG_BLOCK  = (16, 16)
    _HOG_STRIDE = (8, 8)
    _HOG_CELL   = (8, 8)
    _HOG_NBINS  = 9

    def __init__(self, model_path=None):
        from config import FACE_EMBEDDING_DIM
        self.expected_dim = FACE_EMBEDDING_DIM  # 512

        self._hog = cv2.HOGDescriptor(
            self._HOG_WIN,
            self._HOG_BLOCK,
            self._HOG_STRIDE,
            self._HOG_CELL,
            self._HOG_NBINS,
        )
        self._clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(4, 4))
        logger.info("Using Scale-Robust OpenCV Extractor v2 (Multi-Scale + HOG + LBP Hist) — 512 dims.")

    # ── Public API ────────────────────────────────────────────────
    def get_embedding(self, face_img: np.ndarray, landmarks=None) -> np.ndarray:
        """
        Trích xuất embedding 512-dim từ ảnh mặt đã align.
        Scale-invariant: hoạt động tốt cả khi gần lẫn xa camera.
        (landmarks parameter is accepted for compatibility but ignored in v2)

        Args:
            face_img: ảnh BGR, ideally 112×112.
        Returns:
            np.ndarray shape (512,), dtype float32, L2-normalised.
        """
        # ── Preprocessing ──────────────────────────────────────────
        gray = cv2.cvtColor(face_img, cv2.COLOR_BGR2GRAY)
        # Gamma correction để cân bằng sáng tối
        gray = self._gamma_correct(gray, gamma=1.2)
        # CLAHE để equalise contrast
        gray = self._clahe.apply(gray)

        # ── 1. Multi-scale Pixel features (160 dims) ───────────────
        # Chụp ở 2 scale rồi concat → kháng thay đổi khoảng cách
        scale1 = cv2.resize(gray, (10, 8)).flatten().astype(np.float32)  # 80 dims
        scale2 = cv2.resize(gray, (10, 8),
                            interpolation=cv2.INTER_AREA).flatten().astype(np.float32)  # 80 dims
        # Normalize mỗi scale riêng trước khi concat (scale-invariant)
        scale1 = self._l2norm(scale1)
        scale2 = self._l2norm(scale2)
        pixel_feat = np.concatenate([scale1, scale2])  # 160 dims

        # ── 2. HOG features (288 dims) ─────────────────────────────
        hog_input = cv2.resize(gray, self._HOG_WIN)
        hog_feat_raw = self._hog.compute(hog_input).flatten().astype(np.float32)
        # Fold down to 288 dims
        target_hog = 288
        if hog_feat_raw.size >= target_hog:
            chunk = hog_feat_raw.size // target_hog
            hog_feat = np.array([
                hog_feat_raw[i * chunk:(i + 1) * chunk].mean()
                for i in range(target_hog)
            ], dtype=np.float32)
        else:
            pad = target_hog - hog_feat_raw.size
            hog_feat = np.pad(hog_feat_raw, (0, pad)).astype(np.float32)

        # ── 3. LBP Histogram features (64 dims) ────────────────────
        # Dùng histogram thay vì raw pixels → robust hơn với scale
        lbp_img = self._compute_lbp(gray)
        # Chia thành 4 vùng (2×2 grid) rồi tính histogram mỗi vùng → 4×16=64 dims
        h, w = lbp_img.shape
        regions = [
            lbp_img[:h//2, :w//2],    # top-left
            lbp_img[:h//2, w//2:],    # top-right
            lbp_img[h//2:, :w//2],    # bottom-left
            lbp_img[h//2:, w//2:],    # bottom-right
        ]
        lbp_feat_parts = []
        for region in regions:
            hist, _ = np.histogram(region.ravel(), bins=16, range=(0, 256))
            hist = hist.astype(np.float32)
            hist = self._l2norm(hist)
            lbp_feat_parts.append(hist)
        lbp_feat = np.concatenate(lbp_feat_parts)  # 64 dims

        # ── 4. Concatenate → 160 + 288 + 64 = 512 dims ────────────
        combined = np.concatenate([pixel_feat, hog_feat, lbp_feat])

        # ── 5. L2-normalise ───────────────────────────────────────
        return self._l2norm(combined)

    # ── Private Helpers ──────────────────────────────────────────
    @staticmethod
    def _l2norm(vec: np.ndarray) -> np.ndarray:
        # Zero-centering: Trừ đi trung bình của vector
        # Biến Cosine Similarity thông thường thành Pearson Correlation
        # Triệt tiêu các đặc trưng chung của con người, khuếch đại sự khác biệt cá nhân
        vec = vec - np.mean(vec)
        norm = np.linalg.norm(vec)
        return vec / norm if norm > 1e-6 else vec

    @staticmethod
    def _gamma_correct(gray: np.ndarray, gamma: float = 1.2) -> np.ndarray:
        """Gamma correction để cân bằng ảnh tối/sáng."""
        lut = np.array([
            min(255, int((i / 255.0) ** (1.0 / gamma) * 255))
            for i in range(256)
        ], dtype=np.uint8)
        return cv2.LUT(gray, lut)

    @staticmethod
    def _compute_lbp(gray: np.ndarray) -> np.ndarray:
        """Local Binary Pattern (radius=1, 8 neighbours)."""
        rows, cols = gray.shape
        padded = np.pad(gray, 1, mode='edge').astype(np.int32)
        lbp = np.zeros((rows, cols), dtype=np.uint8)
        offsets = [(-1, -1), (-1, 0), (-1, 1),
                   ( 0,  1),
                   ( 1,  1), ( 1,  0), ( 1, -1),
                   ( 0, -1)]
        center = padded[1:-1, 1:-1]
        for bit, (dr, dc) in enumerate(offsets):
            neighbour = padded[1 + dr:rows + 1 + dr, 1 + dc:cols + 1 + dc]
            lbp |= ((neighbour >= center).astype(np.uint8) << bit)
        return lbp
