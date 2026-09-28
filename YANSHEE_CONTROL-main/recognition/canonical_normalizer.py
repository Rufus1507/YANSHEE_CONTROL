"""
canonical_normalizer.py — Canonical Geometric Normalization + Descriptor

Transforms 478 MediaPipe Face Mesh landmarks into a translation-invariant,
scale-invariant, rotation-robust canonical representation, then extracts a
compact geometric descriptor (~40 floats).

Pipeline:
  raw 478 landmarks (normalised x,y,z)
  → translate (origin = eye midpoint)
  → scale     (unit = inter-eye distance)
  → rotate    (align eye-line to horizontal)
  → canonical coords
  → geometric descriptor (global ratios + local geometry + symmetry)

Does NOT modify or replace the existing HOG/LBP embedding.
Used as an ADDITIVE signal during enrollment diversity checking and
optionally blended into the embedding pipeline.
"""
import numpy as np
from typing import List, Tuple, Optional
from logs.logger import get_logger

logger = get_logger(__name__)

# ── MediaPipe Face Mesh landmark indices (verified from face_alignment.py) ──
_LEFT_EYE   = [33, 133, 160, 158, 153, 144]
_RIGHT_EYE  = [362, 263, 387, 385, 380, 373]
_NOSE_TIP   = [4]
_NOSE_BASE  = [94, 19, 1, 4]          # nose bridge & tip region
_MOUTH_L    = [61]
_MOUTH_R    = [291]
_MOUTH_TOP  = [13]
_MOUTH_BOT  = [14]
_CHIN       = [152]
_FOREHEAD   = [10]
_JAW_L      = [234]                    # left jaw landmark
_JAW_R      = [454]                    # right jaw landmark

# Left eye corners
_LEFT_EYE_INNER  = [133]
_LEFT_EYE_OUTER  = [33]
_RIGHT_EYE_INNER = [362]
_RIGHT_EYE_OUTER = [263]

# Upper / lower lip
_UPPER_LIP = [13, 312, 311, 310, 415, 308, 324, 318, 402, 317, 14]
_LOWER_LIP = [17, 84, 181, 91, 146, 61, 185, 40, 39, 37, 0]


def _mean_lm(landmarks: list, indices: list) -> np.ndarray:
    """Average of selected landmark positions (x,y only)."""
    pts = [np.array(landmarks[i][:2]) for i in indices if i < len(landmarks)]
    if not pts:
        return np.zeros(2)
    return np.mean(pts, axis=0)


def canonicalize(
    landmarks: List[Tuple[float, float, float]]
) -> Optional[np.ndarray]:
    """
    Normalize landmarks to canonical coordinate space.

    Args:
        landmarks: list of 478+ (x, y, z) tuples, MediaPipe normalised [0,1].

    Returns:
        canonical: np.ndarray shape (N, 2) — canonical x/y for each landmark,
                   or None if landmarks are insufficient.
    """
    if not landmarks or len(landmarks) < 468:
        return None

    pts = np.array([[lm[0], lm[1]] for lm in landmarks], dtype=np.float32)

    # 1. Reference points
    left_eye  = _mean_lm(landmarks, _LEFT_EYE)
    right_eye = _mean_lm(landmarks, _RIGHT_EYE)
    eye_mid   = (left_eye + right_eye) / 2.0

    # 2. Translation — origin at eye midpoint
    pts = pts - eye_mid

    # 3. Scale — inter-eye distance = 1.0
    eye_dist = np.linalg.norm(right_eye - left_eye)
    if eye_dist < 1e-6:
        return None
    pts = pts / eye_dist

    # 4. Rotation — rotate so right_eye is exactly to the right of left_eye
    dx = right_eye[0] - left_eye[0]
    dy = right_eye[1] - left_eye[1]
    angle = np.arctan2(dy, dx)          # angle of eye line
    cos_a, sin_a = np.cos(-angle), np.sin(-angle)
    rot = np.array([[cos_a, -sin_a],
                    [sin_a,  cos_a]], dtype=np.float32)
    pts = (rot @ pts.T).T               # shape (N, 2)

    return pts


def build_geometric_descriptor(
    landmarks: List[Tuple[float, float, float]]
) -> Optional[np.ndarray]:
    """
    Build a compact geometric descriptor from canonical landmarks.

    Returns:
        np.ndarray of shape (~40,), float32, L2-normalised.
        None if landmarks insufficient.
    """
    canonical = canonicalize(landmarks)
    if canonical is None:
        return None

    # Re-derive key points from canonical coords
    def _c(indices):
        pts = [canonical[i] for i in indices if i < len(canonical)]
        return np.mean(pts, axis=0) if pts else np.zeros(2)

    left_eye   = _c(_LEFT_EYE)
    right_eye  = _c(_RIGHT_EYE)
    nose_tip   = _c(_NOSE_TIP)
    mouth_l    = _c(_MOUTH_L)
    mouth_r    = _c(_MOUTH_R)
    mouth_top  = _c(_MOUTH_TOP)
    mouth_bot  = _c(_MOUTH_BOT)
    chin       = _c(_CHIN)
    forehead   = _c(_FOREHEAD)
    jaw_l      = _c(_JAW_L)
    jaw_r      = _c(_JAW_R)
    le_inner   = _c(_LEFT_EYE_INNER)
    le_outer   = _c(_LEFT_EYE_OUTER)
    re_inner   = _c(_RIGHT_EYE_INNER)
    re_outer   = _c(_RIGHT_EYE_OUTER)
    eye_mid    = (left_eye + right_eye) / 2.0  # = (0,0) after canonicalise

    # Helper distances
    def d(a, b): return float(np.linalg.norm(a - b)) + 1e-9

    # Inter-eye distance = 1.0 by construction (canonical unit)
    eye_w = 1.0

    # ── GLOBAL RATIOS (8 features) ──────────────────────────────────────────
    face_h     = d(forehead, chin)               # face height
    face_w     = d(jaw_l, jaw_r)                 # face width at jaw
    mouth_w    = d(mouth_l, mouth_r)             # mouth width
    nose_h     = d(eye_mid, nose_tip)            # eye-to-nose distance
    eye_to_m   = d(eye_mid, (mouth_top + mouth_bot) / 2.0)
    mouth_open = d(mouth_top, mouth_bot)

    global_feats = np.array([
        face_w / (face_h + 1e-9),           # face aspect ratio
        eye_w  / (face_w + 1e-9),           # eye width / face width
        nose_h / (face_h + 1e-9),           # nose height ratio
        mouth_w / (face_w + 1e-9),          # mouth width ratio
        eye_to_m / (face_h + 1e-9),         # eye-to-mouth ratio
        mouth_open / (face_h + 1e-9),       # mouth openness ratio
        d(le_outer, le_inner) / eye_w,      # left eye width
        d(re_outer, re_inner) / eye_w,      # right eye width
    ], dtype=np.float32)

    # ── LOCAL GEOMETRY (12 features) ────────────────────────────────────────
    # Eye positions relative to face centre (in canonical space, eye_mid=0)
    le_y = float(left_eye[1])   # should be ~0 after rotation
    re_y = float(right_eye[1])
    chin_y = float(chin[1])
    forehead_y = float(forehead[1])
    nose_x = float(nose_tip[0])
    nose_y = float(nose_tip[1])
    ml_x, ml_y = float(mouth_l[0]), float(mouth_l[1])
    mr_x, mr_y = float(mouth_r[0]), float(mouth_r[1])
    jawl_y, jawr_y = float(jaw_l[1]), float(jaw_r[1])

    local_feats = np.array([
        le_y,                   # left eye canonical y (head tilt indicator)
        re_y,                   # right eye canonical y
        nose_x,                 # nose lateral offset
        nose_y,                 # nose vertical position
        ml_y, mr_y,             # mouth corner heights
        chin_y,                 # chin depth
        forehead_y,             # forehead height
        d(jaw_l, left_eye) / (face_h + 1e-9),   # jaw-to-eye left ratio
        d(jaw_r, right_eye) / (face_h + 1e-9),  # jaw-to-eye right ratio
        jawl_y,                 # left jaw y
        jawr_y,                 # right jaw y
    ], dtype=np.float32)

    # ── ANGULAR FEATURES (8 features) ───────────────────────────────────────
    def angle(a, b):
        v = b - a
        return float(np.arctan2(v[1], v[0]))

    ang_feats = np.array([
        angle(left_eye, right_eye),                       # eye line angle
        angle(nose_tip, mouth_top),                       # nose-to-mouth angle
        angle(mouth_l, mouth_r),                          # mouth angle
        angle(jaw_l, jaw_r),                              # jaw angle
        angle(left_eye, nose_tip),                        # left eye to nose
        angle(right_eye, nose_tip),                       # right eye to nose
        angle(le_inner, re_inner),                        # inner eye corners
        angle(chin, nose_tip),                            # chin to nose
    ], dtype=np.float32)

    # ── SYMMETRY FEATURES (8 features) ──────────────────────────────────────
    # Difference between mirrored left/right landmarks — lower = more symmetric
    sym_feats = np.array([
        abs(float(left_eye[1])  - float(right_eye[1])),       # eye height symmetry
        abs(float(left_eye[0])  + float(right_eye[0])),       # eye x symmetry (should be ~0)
        abs(float(jaw_l[1])     - float(jaw_r[1])),           # jaw symmetry
        abs(float(mouth_l[1])   - float(mouth_r[1])),         # mouth corner symmetry
        abs(float(jaw_l[0])     + float(jaw_r[0])),           # jaw x symmetry
        abs(float(mouth_l[0])   + float(mouth_r[0])),         # mouth x symmetry
        abs(d(left_eye, jaw_l)  - d(right_eye, jaw_r)),       # face half-width symmetry
        abs(d(le_outer, le_inner) - d(re_outer, re_inner)),   # eye width symmetry
    ], dtype=np.float32)

    # ── Concatenate + L2-normalise ───────────────────────────────────────────
    descriptor = np.concatenate([global_feats, local_feats, ang_feats, sym_feats])
    descriptor = descriptor - np.mean(descriptor)   # zero-centre
    norm = np.linalg.norm(descriptor)
    if norm > 1e-6:
        descriptor = descriptor / norm

    return descriptor.astype(np.float32)  # shape (36,)


def descriptor_distance(desc_a: np.ndarray, desc_b: np.ndarray) -> float:
    """
    Cosine distance between two geometric descriptors.
    Returns float in [-1, 1]; lower = more similar.
    """
    sim = float(np.dot(desc_a, desc_b))
    return 1.0 - sim   # 0 = identical, 2 = opposite


def pose_from_canonical(
    landmarks: List[Tuple[float, float, float]]
) -> Optional[Tuple[float, float]]:
    """
    Estimate approximate yaw and pitch from landmark geometry.
    Returns (yaw_deg, pitch_deg) or None.

    Uses asymmetry between left/right eye-to-nose distances as yaw proxy,
    and nose-to-eye vs nose-to-chin ratio as pitch proxy.

    These are HEURISTIC estimates — not camera-calibrated.
    Sufficient for quality gate bucketing (FRONT / TURN_LEFT / LOOK_UP etc.)
    """
    if not landmarks or len(landmarks) < 468:
        return None

    try:
        left_eye  = np.array(_mean_lm(landmarks, _LEFT_EYE))
        right_eye = np.array(_mean_lm(landmarks, _RIGHT_EYE))
        nose_tip  = np.array(_mean_lm(landmarks, _NOSE_TIP))
        chin      = np.array(_mean_lm(landmarks, _CHIN))
        eye_mid   = (left_eye + right_eye) / 2.0

        eye_dist = float(np.linalg.norm(right_eye - left_eye)) + 1e-9

        # YAW: difference in distance from nose to left vs right eye
        d_left  = np.linalg.norm(nose_tip - left_eye)
        d_right = np.linalg.norm(nose_tip - right_eye)
        yaw_raw = (d_right - d_left) / eye_dist   # +ve = turned right
        yaw_deg = float(np.degrees(np.arctan(yaw_raw * 1.5)))

        # PITCH: nose vertical position relative to eye-chin axis
        face_h = float(np.linalg.norm(chin - eye_mid)) + 1e-9
        nose_rel_y = float(nose_tip[1] - eye_mid[1]) / face_h  # normalised
        pitch_deg = float(np.degrees(np.arctan((nose_rel_y - 0.35) * 2.5)))

        return (yaw_deg, pitch_deg)

    except Exception as e:
        logger.warning(f"pose_from_canonical error: {e}")
        return None
