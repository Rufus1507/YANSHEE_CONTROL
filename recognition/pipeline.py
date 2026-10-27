"""
RecognitionPipeline — Main realtime recognition loop (Multi-Person, Non-Blocking).

Upgrades in v2:
  - Multi-person tracking with IoU + Center distance fallback.
  - TEMP_LOST state with missed_frames tracking (keeps ID alive if face turns away).
  - 7-frame weighted temporal voting (newer frames have higher weight).
  - Enhanced Quality Gate with INSUFFICIENT_VISUAL_INFORMATION state (prevents false UNKNOWN).
  - Per-track liveness stability.
"""
import time
import asyncio
import concurrent.futures
from typing import List, Dict, Optional, Any
from collections import defaultdict
import numpy as np

from events.event_bus import EventBus
from vision.face_detector import FaceDetector
from vision.face_landmarks import FaceLandmarks
from vision.face_alignment import align_face
from vision.quality_checker import check_quality_detailed
from recognition.embedding_extractor import EmbeddingExtractor
from recognition.face_matcher import FaceMatcher
from liveness.liveness_manager import LivenessManager
from config import (
    GREETING_COOLDOWN_SECONDS,
    LIVENESS_ENABLED,
    UNKNOWN_COOLDOWN_SECONDS,
    LOW_CONFIDENCE_COOLDOWN_SECONDS,
    REQUIRED_CONSISTENT_FRAMES,
    FRAME_TOLERANCE,
    FACE_SIMILARITY_THRESHOLD,
    PIPELINE_PROCESS_MAX_FPS,
    STRANGER_LABEL,
    VOTING_WINDOW_SIZE,
    MIN_VOTES_TO_ACCEPT,
    TRACK_MAX_MISSED_FRAMES,
    TRACK_IOU_THRESHOLD,
    TRACK_MAX_CENTER_DISTANCE,
)
from logs.logger import get_logger
from recognition.face_database import FaceDatabase

logger = get_logger(__name__)


def get_iou(boxA, boxB):
    xA = max(boxA[0], boxB[0])
    yA = max(boxA[1], boxB[1])
    xB = min(boxA[0] + boxA[2], boxB[0] + boxB[2])
    yB = min(boxA[1] + boxA[3], boxB[1] + boxB[3])

    interArea = max(0, xB - xA) * max(0, yB - yA)
    if interArea == 0:
        return 0.0

    boxAArea = boxA[2] * boxA[3]
    boxBArea = boxB[2] * boxB[3]

    return interArea / float(boxAArea + boxBArea - interArea)


def get_center_distance(boxA, boxB):
    cxA = boxA[0] + boxA[2] / 2.0
    cyA = boxA[1] + boxA[3] / 2.0
    cxB = boxB[0] + boxB[2] / 2.0
    cyB = boxB[1] + boxB[3] / 2.0
    return ((cxA - cxB) ** 2 + (cyA - cyB) ** 2) ** 0.5


class FaceTrack:
    def __init__(self, tracking_id: int, initial_bbox, bus: EventBus):
        self.tracking_id = tracking_id
        self.bbox = initial_bbox
        self.last_seen_time = time.time()
        self.missed_frames = 0

        # States: IDLE → RECOGNIZING → LIVENESS_CHECK → VERIFIED / STRANGER / FAILED → COOLDOWN
        # Additional: TEMP_LOST, INSUFFICIENT_VISUAL_INFO
        self.state = "IDLE"
        self.history = []  # rolling window of length VOTING_WINDOW_SIZE
        self.current_user = None
        self.cooldown_until = 0.0

        # Each track has its own distinct LivenessManager state
        self.liveness = LivenessManager(bus, tracking_id=tracking_id)

        self.last_unknown_emit = 0.0
        self.last_low_conf_emit = 0.0

        self._embedding_pending = False

    @property
    def status(self):
        if self.state == "IDLE": return "RECOGNIZING"
        if self.state == "STRANGER": return STRANGER_LABEL
        if self.state == "TEMP_LOST": return "Mất dấu..."
        if self.state == "INSUFFICIENT_VISUAL_INFO": return "Tiến lại gần..."
        return self.state


class RecognitionPipeline:
    def __init__(
        self,
        bus: EventBus,
        face_detector: FaceDetector,
        matcher: FaceMatcher,
        liveness_factory_dummy,  # unused, kept for API compatibility
    ):
        self.bus = bus
        self.face_detector = face_detector
        self.matcher = matcher
        self.db = FaceDatabase()

        try:
            self.embedding_extractor = EmbeddingExtractor()
            self._extractor_ready = True
        except Exception as e:
            logger.error(f"Embedding extractor init failed: {e}")
            self._extractor_ready = False

        self.face_landmarks = FaceLandmarks()

        self.tracks: List[FaceTrack] = []
        self.next_tracking_id = 1
        self.frame_id = 0
        self.last_greeted: Dict[str, float] = {}

        self._min_process_interval = 1.0 / max(1, PIPELINE_PROCESS_MAX_FPS)
        self._last_process_time = 0.0

        self._executor = concurrent.futures.ThreadPoolExecutor(
            max_workers=2, thread_name_prefix="embed_worker"
        )

        self.bus.subscribe("FRAME_READY", self.on_frame)

    # ── Frame handler ────────────────────────────────────────────
    def on_frame(self, payload):
        if not getattr(self.bus, "dashboard_connected", False):
            if self.tracks:
                for track in self.tracks:
                    self.bus.emit("FACE_LOST", {"tracking_id": track.tracking_id})
                self.tracks.clear()
            return

        frame = payload.get("frame")
        if frame is None:
            return

        self.frame_id += 1
        now = time.time()
        do_recognition = (now - self._last_process_time) >= self._min_process_interval
        t_start = time.perf_counter()

        # 1. Phát hiện tất cả khuôn mặt
        bboxes = self.face_detector.process(frame)

        # 2. Tracking (Pass 1: IoU, Pass 2: Center Distance)
        matched_track_indices = set()
        matched_bbox_indices = set()

        # Pass 1: IoU Matching
        for t_idx, track in enumerate(self.tracks):
            best_iou = 0
            best_b_idx = -1
            for b_idx, bbox in enumerate(bboxes):
                if b_idx in matched_bbox_indices:
                    continue
                iou = get_iou(track.bbox, bbox)
                if iou > best_iou:
                    best_iou = iou
                    best_b_idx = b_idx

            if best_iou > TRACK_IOU_THRESHOLD:
                matched_track_indices.add(t_idx)
                matched_bbox_indices.add(best_b_idx)
                track.bbox = bboxes[best_b_idx]
                track.last_seen_time = now
                track.missed_frames = 0
                if track.state == "TEMP_LOST":
                    track.state = "RECOGNIZING"

        # Pass 2: Center distance fallback (handles fast head turns where IoU drops to 0)
        for t_idx, track in enumerate(self.tracks):
            if t_idx in matched_track_indices:
                continue
            best_dist = float('inf')
            best_b_idx = -1
            for b_idx, bbox in enumerate(bboxes):
                if b_idx in matched_bbox_indices:
                    continue
                dist = get_center_distance(track.bbox, bbox)
                if dist < best_dist:
                    best_dist = dist
                    best_b_idx = b_idx
            
            if best_dist < TRACK_MAX_CENTER_DISTANCE:
                matched_track_indices.add(t_idx)
                matched_bbox_indices.add(best_b_idx)
                track.bbox = bboxes[best_b_idx]
                track.last_seen_time = now
                track.missed_frames = 0
                if track.state == "TEMP_LOST":
                    track.state = "RECOGNIZING"

        # Handle Lost & Active Tracks
        active_tracks = []
        for t_idx, track in enumerate(self.tracks):
            if t_idx in matched_track_indices:
                active_tracks.append(track)
            else:
                track.missed_frames += 1
                if track.missed_frames > TRACK_MAX_MISSED_FRAMES:
                    self.bus.emit("FACE_LOST", {"tracking_id": track.tracking_id})
                else:
                    if track.state not in ["VERIFIED", "STRANGER", "FAILED", "COOLDOWN"]:
                        track.state = "TEMP_LOST"
                    active_tracks.append(track)

        # Create New Tracks
        for b_idx, bbox in enumerate(bboxes):
            if b_idx not in matched_bbox_indices:
                new_track = FaceTrack(self.next_tracking_id, bbox, self.bus)
                self.next_tracking_id += 1
                active_tracks.append(new_track)

        self.tracks = active_tracks

        # 3. Process Each Track
        for track in self.tracks:
            # Emit FACE_DETECTED label
            if track.state != "TEMP_LOST":
                self.bus.emit("FACE_DETECTED", {
                    "bbox": list(track.bbox),
                    "tracking_id": track.tracking_id,
                    "status": track.status,
                    "label": self._get_display_label(track),
                })

            if track.state == "TEMP_LOST":
                continue

            if track.state == "COOLDOWN":
                if now > track.cooldown_until:
                    track.state = "IDLE"
                    track.history.clear()
                continue

            if track.state in ["VERIFIED", "STRANGER", "FAILED"]:
                continue

            if not self._extractor_ready:
                continue

            if track.state in ["IDLE", "RECOGNIZING", "INSUFFICIENT_VISUAL_INFO"]:
                if track._embedding_pending or not do_recognition:
                    continue

                # Quality gate: detailed check
                q_res = check_quality_detailed(frame, track.bbox, num_faces=1)
                
                if not q_res.is_valid:
                    if getattr(q_res, 'insufficient_visual', False):
                        track.state = "INSUFFICIENT_VISUAL_INFO"
                        self.bus.emit("INSUFFICIENT_VISUAL_INFORMATION", {
                            "reason": q_res.reason,
                            "message": q_res.message,
                            "tracking_id": track.tracking_id
                        })
                    else:
                        self.bus.emit("FACE_QUALITY_POOR", {
                            "reason": q_res.reason,
                            "message": q_res.message,
                            "tracking_id": track.tracking_id
                        })
                    continue

                track.state = "RECOGNIZING"

                # Landmarks + align (sync, fast)
                landmarks = self.face_landmarks.extract(frame, track.bbox)
                aligned_face = align_face(frame, track.bbox, landmarks)
                if aligned_face is None:
                    continue

                track._embedding_pending = True
                self._submit_embedding_task(track, aligned_face, landmarks, now)

            elif track.state == "LIVENESS_CHECK":
                landmarks = self.face_landmarks.extract(frame, track.bbox)
                liveness_result = track.liveness.update(frame, landmarks)

                if liveness_result is True:
                    self.handle_verification(track, now)
                elif liveness_result is False:
                    track.state = "FAILED"

        if do_recognition:
            self._last_process_time = now

        t_end = time.perf_counter()
        if any(t.state not in ["IDLE", "TEMP_LOST"] for t in self.tracks):
            self.bus.emit("PIPELINE_METRICS", {
                "recognition_time": (t_end - t_start) * 1000
            })

    # ── ThreadPool task ──────────────────────────────────────────
    def _submit_embedding_task(self, track: FaceTrack, aligned_face: np.ndarray,
                                landmarks, now: float):
        loop = getattr(self.bus, "_loop", None)
        lm_snapshot = list(landmarks) if landmarks else None

        def _run():
            embedding = self.embedding_extractor.get_embedding(aligned_face, lm_snapshot)
            return self.matcher.match(embedding)

        future = self._executor.submit(_run)

        def _done_callback(fut):
            try:
                match_result = fut.result()
            except Exception as e:
                logger.error(f"Embedding task error: {e}")
                track._embedding_pending = False
                return

            if loop and loop.is_running():
                loop.call_soon_threadsafe(self._on_match_result, track, match_result, now)
            else:
                self._on_match_result(track, match_result, now)

        future.add_done_callback(_done_callback)

    def _on_match_result(self, track: FaceTrack, match_result: dict, now: float):
        track._embedding_pending = False

        if track not in self.tracks or track.state not in ["RECOGNIZING", "IDLE"]:
            return

        status = match_result.get("status")

        if status == "RECOGNIZED":
            candidate_id = match_result["user_id"]
        elif status == "UNKNOWN":
            candidate_id = "UNKNOWN"
        elif status == "LOW_CONFIDENCE":
            candidate_id = "LOW_CONFIDENCE"
        else:
            candidate_id = "ERROR"

        # 7-Frame rolling window
        track.history.append(candidate_id)
        if len(track.history) > VOTING_WINDOW_SIZE:
            track.history.pop(0)

        counts = {uid: track.history.count(uid) for uid in set(track.history)}
        if not counts:
            return

        # Weighted voting: newer frames have higher weight (index + 1)
        score_dict = {uid: 0.0 for uid in counts.keys()}
        for i, cid in enumerate(track.history):
            score_dict[cid] += (i + 1)

        best_candidate = max(score_dict.keys(), key=lambda k: score_dict[k])

        # Minimum absolute votes required
        if counts[best_candidate] < MIN_VOTES_TO_ACCEPT:
            return

        # ── Quyết định kết quả ────────────────────────────────────
        if best_candidate == "UNKNOWN":
            track.current_user = None
            track.state = "STRANGER"
            if now - track.last_unknown_emit > UNKNOWN_COOLDOWN_SECONDS:
                self.bus.emit("UNKNOWN_USER", {
                    "reason": "not_registered",
                    "label": STRANGER_LABEL,
                    "best_score": match_result.get("best_score", 0.0),
                    "threshold": FACE_SIMILARITY_THRESHOLD,
                    "tracking_id": track.tracking_id,
                })
                track.last_unknown_emit = now
                self.db.add_recognition_log(
                    result="unknown",
                    best_score=match_result.get("best_score", 0.0),
                    threshold=FACE_SIMILARITY_THRESHOLD,
                    processing_time_ms=match_result.get("processing_time_ms"),
                    frame_id=self.frame_id
                )

        elif best_candidate == "LOW_CONFIDENCE":
            track.current_user = None
            if now - track.last_low_conf_emit > LOW_CONFIDENCE_COOLDOWN_SECONDS:
                self.bus.emit("LOW_CONFIDENCE", {
                    "reason": "margin_too_small",
                    "best_score": match_result.get("best_score", 0.0),
                    "second_score": match_result.get("second_score", 0.0),
                    "tracking_id": track.tracking_id,
                })
                track.last_low_conf_emit = now
            track.history.clear()

        elif best_candidate == "ERROR":
            pass

        else:
            track.current_user = match_result
            self.bus.emit("USER_RECOGNIZED", track.current_user)

            if LIVENESS_ENABLED:
                track.state = "LIVENESS_CHECK"
                track.liveness.start_session()
            else:
                self.handle_verification(track, now)

    # ── Helper: display label ────────────────────────────────────
    def _get_display_label(self, track: FaceTrack) -> str:
        if track.state == "STRANGER": return STRANGER_LABEL
        if track.state == "VERIFIED" and track.current_user:
            return track.current_user.get("full_name", "Đã xác minh")
        if track.state == "LIVENESS_CHECK": return "Xác minh liveness..."
        if track.state == "FAILED": return "Liveness thất bại"
        if track.state == "COOLDOWN": return "Cooldown..."
        if track.state == "TEMP_LOST": return "Mất dấu..."
        if track.state == "INSUFFICIENT_VISUAL_INFO": return "Tiến lại gần..."
        return "Đang nhận diện..."

    # ── Verification ─────────────────────────────────────────────
    def handle_verification(self, track: FaceTrack, now: float):
        track.state = "VERIFIED"
        user_id = track.current_user["user_id"]

        payload = track.current_user.copy()
        payload["liveness_passed"] = LIVENESS_ENABLED
        payload["tracking_id"] = track.tracking_id

        self.bus.emit("USER_VERIFIED", payload)
        self.last_greeted[user_id] = now

        self.db.add_recognition_log(
            user_id=user_id,
            full_name=track.current_user.get("full_name"),
            role=track.current_user.get("role"),
            result="recognized",
            best_score=track.current_user.get("best_score"),
            second_score=track.current_user.get("second_score"),
            threshold=FACE_SIMILARITY_THRESHOLD,
            confidence=track.current_user.get("confidence"),
            liveness_passed=LIVENESS_ENABLED,
            processing_time_ms=track.current_user.get("processing_time_ms"),
            frame_id=self.frame_id
        )
