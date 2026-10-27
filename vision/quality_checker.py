"""
Face quality heuristics — Enhanced Quality Gate v2.

Checks:
  1. Face size (TOO_SMALL vs INSUFFICIENT_VISUAL_INFORMATION)
  2. Face near frame edge
  3. Blur (Laplacian variance)
  4. Brightness / overexposure
  5. Head rotation (yaw/pitch via canonical normalizer)
  6. Multiple faces (enrollment only)

Returns:
  - check_quality(frame, bbox, landmarks) → (bool, str)  [backward-compat API]
  - check_quality_detailed(frame, bbox, landmarks) → FaceQualityResult

IMPORTANT:
  FACE_TOO_SMALL  (w < MIN_FACE_SIZE)
      ≠ INSUFFICIENT_VISUAL_INFORMATION  (w < TOO_SMALL_FACE_THRESHOLD)
  The latter means "face detected but too far to recognize" — do NOT emit UNKNOWN.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional
import cv2
import numpy as np

from config import (
    MIN_FACE_SIZE,
    MIN_FACE_QUALITY,
    MIN_BLUR_THRESHOLD,
    MIN_BRIGHTNESS,
    MAX_BRIGHTNESS,
    TOO_SMALL_FACE_THRESHOLD,
    MAX_HEAD_ROTATION_YAW,
    MAX_HEAD_ROTATION_PITCH,
)


@dataclass
class FaceQualityResult:
    is_valid: bool
    reason: str                              # machine-readable key
    message: str                             # human-readable UI message
    quality_score: float = 0.0
    face_size: int = 0
    blur_score: float = 0.0
    brightness_score: float = 0.0
    yaw_deg: Optional[float] = None
    pitch_deg: Optional[float] = None
    insufficient_visual: bool = False        # True → face too small/far, not UNKNOWN


# Reason constants
REASON_OK                      = "OK"
REASON_INVALID_FRAME           = "INVALID_FRAME"
REASON_INSUFFICIENT_VISUAL     = "INSUFFICIENT_VISUAL_INFORMATION"
REASON_FACE_TOO_SMALL          = "FACE_TOO_SMALL"
REASON_FACE_OUTSIDE_FRAME      = "FACE_OUTSIDE_FRAME"
REASON_TOO_DARK                = "TOO_DARK"
REASON_TOO_BRIGHT              = "TOO_BRIGHT"
REASON_TOO_BLURRY              = "TOO_BLURRY"
REASON_HEAD_TOO_ROTATED        = "HEAD_TOO_ROTATED"
REASON_MULTIPLE_FACES          = "MULTIPLE_FACES"
REASON_CROP_ERROR              = "CROP_ERROR"


def check_quality_detailed(
    frame: np.ndarray,
    bbox: tuple,
    landmarks=None,
    num_faces: int = 1,
) -> FaceQualityResult:
    """
    Detailed quality check returning a FaceQualityResult.
    Use this for enrollment and for the pipeline's quality gate.
    """
    if frame is None or frame.size == 0:
        return FaceQualityResult(False, REASON_INVALID_FRAME, "Invalid frame")

    x, y, w, h = bbox
    frame_h, frame_w = frame.shape[:2]

    # ── 0. Multiple faces check (enrollment) ─────────────────────────────
    if num_faces > 1:
        return FaceQualityResult(
            False, REASON_MULTIPLE_FACES,
            f"Multiple faces detected ({num_faces}). Only 1 person allowed.",
            face_size=w,
        )

    # ── 1. Face too small / insufficient visual info ──────────────────────
    face_px = min(w, h)

    if face_px < TOO_SMALL_FACE_THRESHOLD:
        return FaceQualityResult(
            False, REASON_INSUFFICIENT_VISUAL,
            "Move closer — face too small to process.",
            face_size=face_px,
            insufficient_visual=True,   # <-- distinct flag: NOT an UNKNOWN person
        )

    if face_px < MIN_FACE_SIZE:
        return FaceQualityResult(
            False, REASON_FACE_TOO_SMALL,
            "Move a bit closer for better recognition.",
            face_size=face_px,
        )

    # ── 2. Face near frame edge ───────────────────────────────────────────
    cx, cy = x + w // 2, y + h // 2
    margin_x = frame_w * 0.12
    margin_y = frame_h * 0.12
    if cx < margin_x or cx > frame_w - margin_x or cy < margin_y or cy > frame_h - margin_y:
        return FaceQualityResult(
            False, REASON_FACE_OUTSIDE_FRAME,
            "Please stand in the center of the frame.",
            face_size=face_px,
        )

    # ── 3. Crop face region ───────────────────────────────────────────────
    x1 = max(0, int(y))
    y1 = max(0, int(x))
    x2 = min(frame_h, int(y + h))
    y2 = min(frame_w, int(x + w))
    face_crop = frame[x1:x2, y1:y2]
    if face_crop.size == 0:
        return FaceQualityResult(False, REASON_CROP_ERROR, "Face crop error.", face_size=face_px)

    gray = cv2.cvtColor(face_crop, cv2.COLOR_BGR2GRAY)

    # ── 4. Brightness ─────────────────────────────────────────────────────
    mean_brightness = float(np.mean(gray))
    if mean_brightness < MIN_BRIGHTNESS:
        return FaceQualityResult(
            False, REASON_TOO_DARK,
            "Too dark — improve lighting.",
            face_size=face_px,
            brightness_score=mean_brightness,
        )
    if mean_brightness > MAX_BRIGHTNESS:
        return FaceQualityResult(
            False, REASON_TOO_BRIGHT,
            "Too bright — reduce exposure.",
            face_size=face_px,
            brightness_score=mean_brightness,
        )

    # ── 5. Blur ───────────────────────────────────────────────────────────
    lap_var = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    if lap_var < MIN_BLUR_THRESHOLD:
        return FaceQualityResult(
            False, REASON_TOO_BLURRY,
            "Image blurry — hold still.",
            face_size=face_px,
            blur_score=lap_var,
            brightness_score=mean_brightness,
        )

    # ── 6. Head rotation via landmarks (optional) ─────────────────────────
    yaw_deg, pitch_deg = None, None
    if landmarks and len(landmarks) >= 468:
        try:
            from recognition.canonical_normalizer import pose_from_canonical
            pose = pose_from_canonical(landmarks)
            if pose is not None:
                yaw_deg, pitch_deg = pose
                if abs(yaw_deg) > MAX_HEAD_ROTATION_YAW or abs(pitch_deg) > MAX_HEAD_ROTATION_PITCH:
                    return FaceQualityResult(
                        False, REASON_HEAD_TOO_ROTATED,
                        "Please look directly at the camera.",
                        face_size=face_px,
                        blur_score=lap_var,
                        brightness_score=mean_brightness,
                        yaw_deg=yaw_deg,
                        pitch_deg=pitch_deg,
                    )
        except Exception:
            pass  # pose check is best-effort; never block recognition for this

    # ── Compute aggregate quality score ───────────────────────────────────
    size_score       = min(1.0, (face_px - MIN_FACE_SIZE) / (200.0 - MIN_FACE_SIZE))
    blur_score_norm  = min(1.0, lap_var / 300.0)
    bri_score_norm   = 1.0 - abs(mean_brightness - 128.0) / 128.0
    quality_score    = float((size_score * 0.4 + blur_score_norm * 0.4 + bri_score_norm * 0.2))

    return FaceQualityResult(
        True, REASON_OK,
        "OK",
        quality_score=quality_score,
        face_size=face_px,
        blur_score=lap_var,
        brightness_score=mean_brightness,
        yaw_deg=yaw_deg,
        pitch_deg=pitch_deg,
    )


def check_quality(
    frame: np.ndarray,
    bbox: tuple,
    landmarks=None,
    num_faces: int = 1,
) -> tuple[bool, str]:
    """
    Backward-compatible API — returns (ok: bool, reason: str).

    'reason' is now machine-readable (REASON_* constant) so callers that
    previously compared the Vietnamese string need to be updated if they do
    exact string matching.  Pipeline uses it only to emit events, so no
    breaking change.
    """
    result = check_quality_detailed(frame, bbox, landmarks, num_faces)
    return result.is_valid, result.message
