"""
FaceMatcher — Cosine-similarity matching with centroid + individual embeddings.

Returns matching results synchronously as a dictionary. 
Does NOT emit events or log to DB — the Pipeline handles those.
"""
import time
from collections import defaultdict
from typing import Optional, Dict, Any

import numpy as np

from logs.logger import get_logger
from config import (
    FACE_SIMILARITY_THRESHOLD,
    FACE_SIMILARITY_MARGIN,
)
from recognition.face_database import FaceDatabase

logger = get_logger(__name__)


class FaceMatcher:
    def __init__(self):
        self.db = FaceDatabase()

        # Internal cache
        self._user_embeddings: Dict[str, list] = {}   # user_id → [emb, ...]
        self._centroids: Dict[str, np.ndarray] = {}   # user_id → mean embedding
        self._all_embs: list = []                       # flat [(uid, emb), ...]
        self._user_ids: list = []                       # ordered unique user_ids

        self.refresh_cache()

    # ── Cache Management ────────────────────────────────────────
    def refresh_cache(self) -> None:
        """Reload embedding cache from DB, compute centroids."""
        try:
            raw = self.db.get_all_embeddings()  # [(user_id, emb), ...]

            # Group by user_id
            grouped = defaultdict(list)
            for uid, emb in raw:
                grouped[uid].append(emb)

            self._user_embeddings = dict(grouped)
            self._all_embs = raw

            # Compute L2-normalised centroids
            self._centroids = {}
            for uid, embs in self._user_embeddings.items():
                centroid = np.mean(embs, axis=0).astype(np.float32)
                norm = np.linalg.norm(centroid)
                if norm > 1e-6:
                    centroid = centroid / norm
                self._centroids[uid] = centroid

            self._user_ids = list(self._centroids.keys())

            n_users = len(self._user_ids)
            n_embs = len(self._all_embs)
            logger.info(
                f"Embedding cache reloaded — {n_users} users, {n_embs} vectors, "
                f"{n_users} centroids computed"
            )
        except Exception as e:
            logger.error(f"Error loading embedding cache: {e}")
            self._user_embeddings = {}
            self._centroids = {}
            self._all_embs = []
            self._user_ids = []

    # ── Matching ────────────────────────────────────────────────
    def match(self, embedding: np.ndarray) -> Dict[str, Any]:
        """
        Match a query embedding against the cache using cosine similarity.

        Returns a dictionary indicating the result. Status can be:
        - "RECOGNIZED": Passed threshold and margin.
        - "LOW_CONFIDENCE": Passed threshold but failed margin.
        - "UNKNOWN": Below threshold.
        - "ERROR": DB empty or invalid embedding.
        """
        start_t = time.perf_counter()

        if not self._centroids:
            return self._build_unknown(0.0, start_t, detail="database_empty")

        try:
            # Ensure query is normalised
            query = embedding.astype(np.float32)
            qnorm = np.linalg.norm(query)
            if qnorm > 1e-6:
                query = query / qnorm

            # ── Step 1: Centroid-level cosine similarity ────────
            centroid_scores = {}
            for uid in self._user_ids:
                # dot product of L2-normalised vectors = cosine similarity
                score = float(np.dot(query, self._centroids[uid]))
                centroid_scores[uid] = score

            # Sort by score descending
            ranked = sorted(centroid_scores.items(), key=lambda x: x[1], reverse=True)

            # ── Step 2: Fine-grained matching on top candidates ─
            # Check top candidates (all centroids above a loose pre-filter)
            pre_filter_threshold = max(0.0, FACE_SIMILARITY_THRESHOLD - 0.15)
            candidates = [
                (uid, cscore) for uid, cscore in ranked
                if cscore >= pre_filter_threshold
            ]

            if not candidates:
                return self._build_unknown(ranked[0][1] if ranked else 0.0, start_t)

            # For each candidate, compute a robust similarity score
            user_best_scores = {}
            for uid, cscore in candidates:
                embs = self._user_embeddings.get(uid, [])
                if not embs:
                    continue
                emb_matrix = np.stack(embs)
                sims = emb_matrix @ query  # dot products (all normalised)
                
                # Chống nhận nhầm (Outlier Rejection):
                # Thay vì lấy np.max (dễ bị 1 ảnh nhiễu đánh lừa), ta lấy trung bình của Top 3 ảnh giống nhất
                top_k = min(3, len(sims))
                top_sims_mean = float(np.mean(np.sort(sims)[-top_k:]))
                
                # Kết hợp với điểm Centroid để đảm bảo tính ổn định tuyệt đối
                final_robust_score = 0.7 * top_sims_mean + 0.3 * cscore
                user_best_scores[uid] = final_robust_score

            if not user_best_scores:
                return self._build_unknown(0.0, start_t)

            # ── Step 3: Rank by best individual score ───────────
            final_ranked = sorted(
                user_best_scores.items(), key=lambda x: x[1], reverse=True
            )

            best_uid, best_score = final_ranked[0]
            second_uid = final_ranked[1][0] if len(final_ranked) > 1 else None
            second_score = final_ranked[1][1] if len(final_ranked) > 1 else 0.0

            # ── Step 4: Threshold checks ────────────────────────
            if best_score < FACE_SIMILARITY_THRESHOLD:
                return self._build_unknown(best_score, start_t, detail=f"best={best_score:.3f} < {FACE_SIMILARITY_THRESHOLD}")

            margin = best_score - second_score
            if len(final_ranked) > 1 and margin < FACE_SIMILARITY_MARGIN:
                # Ambiguous — two users too close
                return {
                    "status": "LOW_CONFIDENCE",
                    "reason": "margin_too_small",
                    "best_score": round(best_score, 4),
                    "second_score": round(second_score, 4),
                    "best_user_id": best_uid,
                    "second_user_id": second_uid,
                    "margin": round(margin, 4),
                    "required_margin": FACE_SIMILARITY_MARGIN,
                    "processing_time_ms": (time.perf_counter() - start_t) * 1000.0
                }

            # ── Step 5: Accepted — fetch user info ──────────────
            info = self.db.get_user_info(best_uid)
            if info is None:
                return {
                    "status": "ERROR",
                    "reason": "user_not_found_in_db",
                    "user_id": best_uid,
                    "processing_time_ms": (time.perf_counter() - start_t) * 1000.0
                }

            # Confidence: map similarity to percentage
            confidence = min(100.0, max(0.0, (best_score - 0.2) / 0.8 * 100.0))

            return {
                "status": "RECOGNIZED",
                "user_id": best_uid,
                "full_name": info["full_name"],
                "role": info["role"],
                "best_score": round(best_score, 4),
                "second_score": round(second_score, 4),
                "second_user_id": second_uid,
                "confidence": round(confidence, 1),
                "processing_time_ms": (time.perf_counter() - start_t) * 1000.0
            }

        except Exception as e:
            logger.error(f"Lỗi trong quá trình so khớp: {e}", exc_info=True)
            return {
                "status": "ERROR",
                "reason": str(e),
                "processing_time_ms": (time.perf_counter() - start_t) * 1000.0
            }

    def _build_unknown(self, score: float, start_t: float, detail: str = "") -> Dict[str, Any]:
        """Constructs an UNKNOWN response."""
        return {
            "status": "UNKNOWN",
            "reason": "below_threshold",
            "detail": detail,
            "best_score": round(score, 4),
            "threshold": FACE_SIMILARITY_THRESHOLD,
            "processing_time_ms": (time.perf_counter() - start_t) * 1000.0
        }
