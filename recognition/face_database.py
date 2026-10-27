"""
FaceDatabase — SQLite persistence layer for users, face embeddings,
and recognition logs.

All embeddings are stored as BLOB (numpy .tobytes()) for efficiency.
"""
import sqlite3
import numpy as np
from typing import List, Tuple, Optional, Dict, Any
from config import DATABASE_PATH, FACE_EMBEDDING_DIM
from logs.logger import get_logger

logger = get_logger(__name__)


class FaceDatabase:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(FaceDatabase, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, db_path: str = DATABASE_PATH):
        if self._initialized:
            return
        self._initialized = True
        import os
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.conn = sqlite3.connect(db_path, check_same_thread=False, timeout=10.0)
        self.conn.execute("PRAGMA journal_mode=WAL")
        self._ensure_tables()
        self.fix_is_active_null()

    # ── Schema ──────────────────────────────────────────────────
    def _ensure_tables(self):
        cur = self.conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT UNIQUE NOT NULL,
                full_name TEXT NOT NULL,
                role TEXT NOT NULL,
                note TEXT,
                created_at TEXT,
                updated_at TEXT,
                is_active INTEGER DEFAULT 1 NOT NULL
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS face_embeddings(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                embedding BLOB NOT NULL,
                angle_label TEXT,
                quality_score REAL,
                model_name TEXT,
                created_at TEXT
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS recognition_logs(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT,
                full_name TEXT,
                role TEXT,
                result TEXT,
                best_score REAL,
                second_score REAL,
                threshold REAL,
                confidence REAL,
                liveness_passed INTEGER,
                processing_time_ms REAL,
                frame_id INTEGER,
                robot_action TEXT,
                robot_status TEXT,
                created_at TEXT
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS system_logs(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                level TEXT,
                module TEXT,
                message TEXT,
                created_at TEXT
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS robot_actions(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                role TEXT,
                speech_text TEXT,
                motion_name TEXT,
                enabled INTEGER DEFAULT 1
            )
        """)
        # Add model_name column to face_embeddings if missing (migration)
        try:
            cur.execute("SELECT model_name FROM face_embeddings LIMIT 1")
        except sqlite3.OperationalError:
            cur.execute("ALTER TABLE face_embeddings ADD COLUMN model_name TEXT")
            logger.info("Migrated face_embeddings: added model_name column")

        # Add best_score, second_score, threshold, processing_time_ms, frame_id columns to recognition_logs if missing
        for col, col_type in [("best_score", "REAL"), ("second_score", "REAL"), ("threshold", "REAL"), ("processing_time_ms", "REAL"), ("frame_id", "INTEGER")]:
            try:
                cur.execute(f"SELECT {col} FROM recognition_logs LIMIT 1")
            except sqlite3.OperationalError:
                cur.execute(f"ALTER TABLE recognition_logs ADD COLUMN {col} {col_type}")
                logger.info(f"Migrated recognition_logs: added {col} column")

        self.conn.commit()

    # ── Fix NULL is_active ──────────────────────────────────────
    def fix_is_active_null(self) -> int:
        """Set is_active=1 for any user rows where it is NULL."""
        cur = self.conn.cursor()
        cur.execute("UPDATE users SET is_active = 1 WHERE is_active IS NULL")
        fixed = cur.rowcount
        if fixed > 0:
            self.conn.commit()
            logger.info(f"Fixed {fixed} users with NULL is_active → 1")
        return fixed

    # ── User CRUD ───────────────────────────────────────────────
    def add_user(self, user_id: str, full_name: str, role: str, note: str = "") -> None:
        cur = self.conn.cursor()
        cur.execute(
            """INSERT OR IGNORE INTO users(user_id, full_name, role, note, is_active, created_at, updated_at)
               VALUES(?, ?, ?, ?, 1, datetime('now'), datetime('now'))""",
            (user_id, full_name, role, note),
        )
        self.conn.commit()

    def get_user_info(self, user_id: str) -> Optional[dict]:
        cur = self.conn.cursor()
        cur.execute(
            "SELECT full_name, role FROM users WHERE user_id=? AND is_active=1",
            (user_id,),
        )
        row = cur.fetchone()
        return {"full_name": row[0], "role": row[1]} if row else None

    def get_all_users(self) -> list:
        cur = self.conn.cursor()
        cur.execute(
            "SELECT user_id, full_name, role, note, created_at FROM users WHERE is_active=1"
        )
        return [
            {"user_id": r[0], "full_name": r[1], "role": r[2], "note": r[3], "created_at": r[4]}
            for r in cur.fetchall()
        ]

    def deactivate_user(self, user_id: str) -> bool:
        """Soft-delete: set is_active = 0."""
        cur = self.conn.cursor()
        cur.execute(
            "UPDATE users SET is_active = 0, updated_at = datetime('now') WHERE user_id = ?",
            (user_id,),
        )
        self.conn.commit()
        return cur.rowcount > 0

    def find_users_by_name(self, full_name: str) -> List[str]:
        """Tìm tất cả user_id có cùng full_name (is_active=1)."""
        cur = self.conn.cursor()
        cur.execute(
            "SELECT user_id FROM users WHERE LOWER(full_name)=LOWER(?) AND is_active=1",
            (full_name,),
        )
        return [row[0] for row in cur.fetchall()]

    def hard_delete_user(self, user_id: str) -> None:
        """Xóa cứng (hard delete) hoàn toàn user và tất cả embeddings. Dùng khi đăng ký lại."""
        cur = self.conn.cursor()
        cur.execute("DELETE FROM face_embeddings WHERE user_id=?", (user_id,))
        cur.execute("DELETE FROM users WHERE user_id=?", (user_id,))
        self.conn.commit()
        logger.info(f"Hard-deleted user {user_id} and all their embeddings.")

    # ── Embedding CRUD ──────────────────────────────────────────
    def add_embedding(
        self,
        user_id: str,
        embedding: np.ndarray,
        angle_label: str = "",
        quality: float = 1.0,
        model_name: str = "",
    ) -> None:
        """Store embedding as raw float32 bytes (NOT pickle)."""
        emb = embedding.astype(np.float32)
        blob = emb.tobytes()
        cur = self.conn.cursor()
        cur.execute(
            """INSERT INTO face_embeddings(user_id, embedding, angle_label, quality_score, model_name, created_at)
               VALUES(?, ?, ?, ?, ?, datetime('now'))""",
            (user_id, blob, angle_label, quality, model_name),
        )
        self.conn.commit()

    def get_all_embeddings(self) -> List[Tuple[str, np.ndarray]]:
        """
        Load all embeddings for active users.
        Returns list of (user_id, np.ndarray(512,)) tuples.
        Handles both new raw-bytes format and legacy pickle format.
        """
        cur = self.conn.cursor()
        cur.execute(
            """SELECT fe.user_id, fe.embedding
               FROM face_embeddings fe
               INNER JOIN users u ON fe.user_id = u.user_id
               WHERE u.is_active = 1"""
        )
        results = []
        for uid, blob in cur.fetchall():
            emb = self._deserialize_embedding(blob)
            if emb is not None:
                results.append((uid, emb))
        return results

    def _deserialize_embedding(self, blob: bytes) -> Optional[np.ndarray]:
        """
        Deserialize embedding BLOB.
        Tries raw float32 bytes first (512 * 4 = 2048 bytes),
        then falls back to pickle for legacy data.
        """
        expected_bytes = FACE_EMBEDDING_DIM * 4  # float32 = 4 bytes

        if len(blob) == expected_bytes:
            # New format: raw float32 bytes
            return np.frombuffer(blob, dtype=np.float32).copy()

        # Legacy format: try pickle
        try:
            import pickle
            emb = pickle.loads(blob)
            if isinstance(emb, np.ndarray):
                if emb.shape[0] == FACE_EMBEDDING_DIM:
                    return emb.astype(np.float32)
                else:
                    logger.warning(
                        f"Legacy embedding has wrong dim={emb.shape[0]}, expected {FACE_EMBEDDING_DIM}. Skipping."
                    )
                    return None
            return None
        except Exception:
            logger.warning(f"Cannot deserialize embedding blob ({len(blob)} bytes). Skipping.")
            return None

    def get_embeddings_by_user(self, user_id: str) -> List[np.ndarray]:
        """Get all embeddings for a specific user."""
        cur = self.conn.cursor()
        cur.execute("SELECT embedding FROM face_embeddings WHERE user_id = ?", (user_id,))
        results = []
        for (blob,) in cur.fetchall():
            emb = self._deserialize_embedding(blob)
            if emb is not None:
                results.append(emb)
        return results

    def count_embeddings_for_user(self, user_id: str) -> int:
        cur = self.conn.cursor()
        cur.execute("SELECT COUNT(*) FROM face_embeddings WHERE user_id = ?", (user_id,))
        return cur.fetchone()[0]

    def delete_embeddings_for_user(self, user_id: str) -> int:
        """Delete all embeddings for a user. Used when re-registering or model change."""
        cur = self.conn.cursor()
        cur.execute("DELETE FROM face_embeddings WHERE user_id = ?", (user_id,))
        self.conn.commit()
        return cur.rowcount

    def delete_all_embeddings(self) -> int:
        """Delete ALL embeddings. Used after model change."""
        cur = self.conn.cursor()
        cur.execute("DELETE FROM face_embeddings")
        self.conn.commit()
        count = cur.rowcount
        logger.warning(f"Deleted ALL {count} embeddings from database")
        return count

    # ── Recognition log ─────────────────────────────────────────
    def add_recognition_log(self, **kwargs) -> None:
        cur = self.conn.cursor()
        fields = [
            "user_id", "full_name", "role", "result",
            "best_score", "second_score", "threshold",
            "confidence", "liveness_passed",
            "processing_time_ms", "frame_id",
            "robot_action", "robot_status",
        ]
        for f in fields:
            if f not in kwargs:
                kwargs[f] = None

        cur.execute(
            """INSERT INTO recognition_logs
               (user_id, full_name, role, result, best_score, second_score, threshold,
                confidence, liveness_passed, processing_time_ms, frame_id, robot_action, robot_status, created_at)
               VALUES(:user_id, :full_name, :role, :result, :best_score, :second_score, :threshold,
                      :confidence, :liveness_passed, :processing_time_ms, :frame_id, :robot_action, :robot_status, datetime('now'))""",
            kwargs,
        )
        self.conn.commit()

    def get_recent_logs(self, limit: int = 50) -> list:
        cur = self.conn.cursor()
        cur.execute(
            """SELECT user_id, full_name, role, confidence, result,
                      best_score, second_score, robot_action, created_at
               FROM recognition_logs ORDER BY id DESC LIMIT ?""",
            (limit,),
        )
        return [
            {
                "user_id": r[0], "full_name": r[1], "role": r[2],
                "confidence": r[3], "result": r[4],
                "best_score": r[5], "second_score": r[6],
                "robot_action": r[7], "created_at": r[8],
            }
            for r in cur.fetchall()
        ]

    # ── Helper Methods ──────────────────────────────────────────
    def count_users(self) -> int:
        cur = self.conn.cursor()
        cur.execute("SELECT COUNT(*) FROM users WHERE is_active = 1")
        return cur.fetchone()[0]

    def count_embeddings(self) -> int:
        cur = self.conn.cursor()
        cur.execute("SELECT COUNT(*) FROM face_embeddings")
        return cur.fetchone()[0]

    def has_registered_faces(self) -> bool:
        return self.count_users() > 0 and self.count_embeddings() > 0

    def count_stats(self) -> dict:
        return {
            "users": self.count_users(),
            "embeddings": self.count_embeddings(),
        }
