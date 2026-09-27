"""
User registration via Yanshee camera (MJPEG stream) hoặc webcam (legacy).

Upgrades in v2 (24-sample Auto-Sampling):
  - No more manual "Phase 1 / Phase 2" splits.
  - Automatically classifies face into 7 buckets (Pose + Distance) using
    Canonical Normalizer (yaw/pitch) and bounding box size.
  - Dedupes dynamically (skips frames with cosine sim > 0.93 to existing).
  - Shows bucket progress on-screen (e.g. FRONT_NEAR: 3/4).
"""
import uuid
import cv2
import numpy as np
import time
from PIL import Image, ImageDraw, ImageFont
import sys
import os
from typing import List, Optional, Tuple
from pathlib import Path

# Ensure project root is on sys.path so all local imports work
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from recognition.face_database import FaceDatabase
from recognition.embedding_extractor import EmbeddingExtractor
from recognition.canonical_normalizer import pose_from_canonical
from vision.face_detector import FaceDetector
from vision.face_landmarks import FaceLandmarks
from vision.face_alignment import align_face
from vision.quality_checker import check_quality_detailed
from config import (
    FACE_MODEL_NAME,
    CAMERA_INDEX,
    ENROLLMENT_TARGET_SAMPLES,
    ENROLLMENT_DUPLICATE_THRESHOLD,
    ENROLLMENT_CAPTURE_COOLDOWN,
)
from logs.logger import get_logger

logger = get_logger(__name__)

# ── Bucket Definitions ────────────────────────────────────────────────────────
TARGET_BUCKETS = {
    "FRONT_NEAR": 4,   # w >= 140
    "FRONT_MID": 4,    # 90 <= w < 140
    "FRONT_FAR": 4,    # w < 90
    "TURN_LEFT": 3,    # yaw > 15
    "TURN_RIGHT": 3,   # yaw < -15
    "LOOK_UP": 3,      # pitch > 15
    "LOOK_DOWN": 3,    # pitch < -15
}


def register_user(
    full_name: str,
    role: str,
    note: str,
    aligned_face_images: List[np.ndarray],
    landmarks_list: List[Optional[List[Tuple]]],
    bucket_labels: List[str],
    model_path: Path | str | None = None,
) -> str:
    """
    Store collected embeddings into the database.
    Deduping was already done dynamically during capture.
    """
    db = FaceDatabase()
    existing = db.find_users_by_name(full_name)
    for old_uid in existing:
        db.hard_delete_user(old_uid)
        logger.info(f"  Đã xóa user cũ cùng tên: {full_name} ({old_uid})")

    user_id = f"U{uuid.uuid4().hex[:8].upper()}"
    db.add_user(user_id, full_name, role, note)
    logger.info(f"Đăng ký người dùng: {full_name} ({user_id}), role={role}")

    extractor = EmbeddingExtractor(model_path)
    saved_count = 0

    for idx, (img, lms, label) in enumerate(zip(aligned_face_images, landmarks_list, bucket_labels)):
        emb = extractor.get_embedding(img, lms)
        db.add_embedding(
            user_id, emb,
            angle_label=label,
            quality=1.0, 
            model_name=FACE_MODEL_NAME,
        )
        saved_count += 1
        logger.info(f"  Lưu embedding [{label}] cho {user_id}")

    logger.info(f"Đăng ký hoàn tất: {user_id} — {saved_count} embeddings đã lưu")
    return user_id


def _detect_faces_mediapipe(detector, frame):
    """Detect ALL faces in a frame using MediaPipe."""
    import mediapipe as mp
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    results = detector.detector.process(rgb)
    if not results.detections:
        return []

    h_img, w_img = frame.shape[:2]
    faces = []
    for det in results.detections:
        bb = det.location_data.relative_bounding_box
        x = max(int(bb.xmin * w_img), 0)
        y = max(int(bb.ymin * h_img), 0)
        bw = min(int(bb.width * w_img), w_img - x)
        bh = min(int(bb.height * h_img), h_img - y)
        if bw > 20 and bh > 20:
            faces.append((x, y, bw, bh))
    return faces


def put_text_vietnamese(img, text, position, font, color_bgr):
    """Draw Vietnamese text with accents on a BGR image using PIL."""
    if not text:
        return img
    img_pil = Image.fromarray(img)
    draw = ImageDraw.Draw(img_pil)
    color_rgb = (color_bgr[2], color_bgr[1], color_bgr[0])
    draw.text(position, text, font=font, fill=color_rgb)
    return np.array(img_pil)


if __name__ == "__main__":
    import argparse
    import platform

    parser = argparse.ArgumentParser(description="Auto-Sampling Enrollment")
    parser.add_argument("--name", type=str, required=True, help="Họ và tên")
    parser.add_argument("--role", type=str, default="Student", help="Vai trò (Admin/Teacher/Student/Guest)")
    parser.add_argument("--note", type=str, default="", help="Ghi chú")
    
    args = parser.parse_args()
    num_images = sum(TARGET_BUCKETS.values())  # Defaults to 24

    # Mở camera local (Webcam laptop)
    cap = cv2.VideoCapture(CAMERA_INDEX, cv2.CAP_DSHOW) if platform.system() == "Windows" else cv2.VideoCapture(CAMERA_INDEX)
    if not cap.isOpened():
        print("Lỗi: Không thể mở webcam (laptop camera).")
        sys.exit(1)

    print(f"\n{'='*60}")
    print(f"  AUTO-SAMPLING ENROLLMENT: {args.name}")
    print(f"  Target Samples: {num_images}")
    print(f"{'='*60}")
    print("\nHướng dẫn:")
    print("  Hệ thống sẽ tự động chụp đủ 24 ảnh đa dạng nhất.")
    print("  Bạn chỉ cần di chuyển từ gần ra xa, quay đầu trái/phải/lên/xuống.")
    print("  ESC = hủy\n")

    detector = FaceDetector()
    landmarks_extractor = FaceLandmarks()
    extractor = EmbeddingExtractor()
    
    aligned_images = []
    captured_landmarks = []
    captured_embeddings = []
    captured_labels = []
    bucket_counts = {k: 0 for k in TARGET_BUCKETS.keys()}
    
    last_capture_time = 0

    try:
        font_title = ImageFont.truetype("arial.ttf", 26)
        font_action = ImageFont.truetype("arialbd.ttf", 32)
        font_instruction = ImageFont.truetype("arial.ttf", 22)
        font_progress = ImageFont.truetype("arial.ttf", 20)
        font_category = ImageFont.truetype("arial.ttf", 18)
        font_debug = ImageFont.truetype("arial.ttf", 14)
    except IOError:
        font_title = font_action = font_instruction = font_progress = font_category = font_debug = ImageFont.load_default()

    cv2.namedWindow("Auto-Sampling Enrollment", cv2.WINDOW_NORMAL)
    cv2.resizeWindow("Auto-Sampling Enrollment", 1280, 720)

    INSTRUCTION_MAP = {
        "FRONT_NEAR": "Nhìn thẳng vào camera",
        "FRONT_MID": "Giữ nguyên khuôn mặt, lùi ra xa một chút",
        "FRONT_FAR": "Lùi xa hơn nữa",
        "TURN_LEFT": "Quay mặt sang trái",
        "TURN_RIGHT": "Quay mặt sang phải",
        "LOOK_UP": "Nhìn lên",
        "LOOK_DOWN": "Nhìn xuống",
    }

    QUALITY_MSG_MAP = {
        "FACE_TOO_SMALL": "Lại gần camera hơn",
        "INSUFFICIENT_VISUAL_INFORMATION": "Lại gần camera hơn",
        "TOO_BLURRY": "Giữ đầu yên",
        "TOO_DARK": "Tăng ánh sáng",
        "TOO_BRIGHT": "Tránh ánh sáng quá mạnh",
        "HEAD_TOO_ROTATED": "Quay mặt theo hướng được yêu cầu",
        "MULTIPLE_FACES": "Chỉ để một người trước camera",
        "FACE_OUTSIDE_FRAME": "Đứng vào giữa khung hình",
    }

    ORDERED_BUCKETS = ["FRONT_NEAR", "FRONT_MID", "FRONT_FAR", "TURN_LEFT", "TURN_RIGHT", "LOOK_UP", "LOOK_DOWN"]

    debug_mode = False
    success_mode = False
    success_start_time = 0
    last_captured_bucket = ""

    while True:
        if success_mode:
            if time.time() - success_start_time > 2.0:
                break
            
            # Draw Success Screen
            canvas_pil = Image.new("RGB", (1280, 720), (30, 30, 30))
            draw = ImageDraw.Draw(canvas_pil)
            draw.text((500, 300), "✓ ĐĂNG KÝ THÀNH CÔNG", font=font_action, fill=(76, 175, 80))
            draw.text((530, 350), f"{num_images} / {num_images} mẫu hợp lệ", font=font_instruction, fill=(255, 255, 255))
            draw.text((490, 390), "Hồ sơ khuôn mặt đã được lưu.", font=font_instruction, fill=(170, 170, 170))
            
            cv2.imshow("Auto-Sampling Enrollment", cv2.cvtColor(np.array(canvas_pil), cv2.COLOR_RGB2BGR))
            cv2.waitKey(1)
            continue

        ret, frame = cap.read()
        if not ret:
            continue

        # Process frame
        faces = _detect_faces_mediapipe(detector, frame)
        num_faces = len(faces)

        can_capture = False
        aligned = None
        landmarks = None
        face_w = 0
        q_res = None
        is_duplicate = False

        if num_faces > 0:
            q_res = check_quality_detailed(frame, faces[0], num_faces=num_faces)
            x, y, w, h = faces[0]
            face_w = w
            
            if q_res.is_valid and num_faces == 1:
                landmarks = landmarks_extractor.extract(frame)
                aligned = align_face(frame, faces[0], landmarks)
                if aligned is not None:
                    can_capture = True

        # Find current target bucket
        current_target = None
        for b_name in ORDERED_BUCKETS:
            if bucket_counts[b_name] < TARGET_BUCKETS[b_name]:
                current_target = b_name
                break

        if current_target is None and len(aligned_images) >= num_images:
            success_mode = True
            success_start_time = time.time()
            continue

        # ── Auto capture logic ─────────────────
        if can_capture and aligned is not None and current_target is not None:
            current_time = time.time()
            if current_time - last_capture_time > ENROLLMENT_CAPTURE_COOLDOWN:
                yaw_deg, pitch_deg = (0.0, 0.0)
                pose = pose_from_canonical(landmarks) if landmarks else None
                if pose:
                    yaw_deg, pitch_deg = pose
                
                bucket = "FRONT_MID"
                if yaw_deg < -15: bucket = "TURN_RIGHT"
                elif yaw_deg > 15: bucket = "TURN_LEFT"
                elif pitch_deg < -15: bucket = "LOOK_DOWN"
                elif pitch_deg > 15: bucket = "LOOK_UP"
                else:
                    if face_w >= 140: bucket = "FRONT_NEAR"
                    elif face_w >= 90: bucket = "FRONT_MID"
                    else: bucket = "FRONT_FAR"

                if bucket_counts[bucket] < TARGET_BUCKETS[bucket]:
                    emb = extractor.get_embedding(aligned, landmarks)
                    
                    if captured_embeddings:
                        max_sim = max(np.dot(emb, s) for s in captured_embeddings)
                        if max_sim > ENROLLMENT_DUPLICATE_THRESHOLD:
                            is_duplicate = True

                    if not is_duplicate:
                        aligned_images.append(aligned)
                        captured_landmarks.append(landmarks)
                        captured_embeddings.append(emb)
                        captured_labels.append(bucket)
                        bucket_counts[bucket] += 1
                        
                        last_captured_bucket = bucket
                        last_capture_time = current_time

        # ── UI Rendering (PIL Canvas) ───────────────────────────────────────────────────
        canvas_pil = Image.new("RGB", (1280, 720), (30, 30, 30))
        draw = ImageDraw.Draw(canvas_pil)

        draw.text((40, 25), "Auto Face Enrollment", font=font_title, fill=(255, 255, 255))
        draw.text((40, 55), f"Mẫu: {len(aligned_images)} / {num_images}", font=font_progress, fill=(170, 170, 170))

        cam_w, cam_h = 800, 600
        cam_x, cam_y = 40, 90
        
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        
        # Draw robust bounding box directly on frame
        if num_faces > 0:
            x, y, w, h = faces[0]
            box_color = (255, 193, 7) # Yellow (Waiting)
            if not q_res.is_valid:
                box_color = (244, 67, 54) # Red (Invalid)
            elif can_capture:
                box_color = (76, 175, 80) # Green (Valid)
            
            cv2.rectangle(frame_rgb, (x, y), (x+w, y+h), box_color, 2)
            
        cam_pil = Image.fromarray(frame_rgb).resize((cam_w, cam_h))
        canvas_pil.paste(cam_pil, (cam_x, cam_y))

        # Panel Right
        panel_x, panel_y = 880, 90
        draw.rectangle([panel_x, panel_y, panel_x + 360, panel_y + 600], fill=(37, 37, 38))

        draw.text((panel_x + 20, panel_y + 20), "BƯỚC HIỆN TẠI", font=font_progress, fill=(170, 170, 170))
        action_text = current_target if current_target else "HOÀN THÀNH"
        draw.text((panel_x + 20, panel_y + 50), action_text, font=font_action, fill=(255, 255, 255))

        # Human-friendly Instructions
        instruction_text = INSTRUCTION_MAP.get(current_target, "")
        inst_color = (255, 255, 255)
        
        if num_faces == 0:
            instruction_text = "Vui lòng đứng trước camera"
            inst_color = (255, 193, 7)
        elif q_res and not q_res.is_valid:
            instruction_text = QUALITY_MSG_MAP.get(q_res.reason, "Điều chỉnh khuôn mặt")
            inst_color = (244, 67, 54)
        elif is_duplicate:
            instruction_text = "Quá giống ảnh cũ, hãy thay đổi góc"
            inst_color = (255, 193, 7)

        draw.text((panel_x + 20, panel_y + 100), instruction_text, font=font_instruction, fill=inst_color)

        # Progress Bar
        draw.text((panel_x + 20, panel_y + 180), f"Tiến độ: {len(aligned_images)} / {num_images}", font=font_progress, fill=(255, 255, 255))
        bar_x, bar_y, bar_w, bar_h = panel_x + 20, panel_y + 215, 320, 20
        progress_ratio = min(1.0, len(aligned_images) / num_images)
        draw.rectangle([bar_x, bar_y, bar_x + bar_w, bar_y + bar_h], fill=(70, 70, 70))
        if progress_ratio > 0:
            draw.rectangle([bar_x, bar_y, bar_x + int(bar_w * progress_ratio), bar_y + bar_h], fill=(76, 175, 80))

        # Categories List
        cat_y = panel_y + 270
        for b_name in ORDERED_BUCKETS:
            count = bucket_counts[b_name]
            target = TARGET_BUCKETS[b_name]
            if count >= target:
                prefix = "✓"
                c_fill = (76, 175, 80)
            elif b_name == current_target:
                prefix = "○"
                c_fill = (255, 193, 7)
            else:
                prefix = "○"
                c_fill = (150, 150, 150)
                
            draw.text((panel_x + 20, cat_y), f"{prefix}   {b_name:<15} {count}/{target}", font=font_category, fill=c_fill)
            cat_y += 35

        # Capture Feedback Animation (Fades out after 800ms)
        dt = time.time() - last_capture_time
        if dt < 0.8 and last_captured_bucket:
            # Draw a nice green pill over the bottom of the camera view
            pill_w, pill_h = 240, 50
            pill_x = cam_x + (cam_w - pill_w) // 2
            pill_y = cam_y + cam_h - pill_h - 30
            draw.rectangle([pill_x, pill_y, pill_x + pill_w, pill_y + pill_h], fill=(76, 175, 80))
            draw.text((pill_x + 20, pill_y + 12), f"✓ Đã thu mẫu {last_captured_bucket}", font=font_progress, fill=(255, 255, 255))

        # Debug Overlay
        if debug_mode and q_res:
            debug_text = f"DEBUG: Q={getattr(q_res, 'quality_score', 0):.2f} | B={getattr(q_res, 'blur_score', 0):.0f} | Y={getattr(q_res, 'yaw_deg', 0) or 0:.1f} | P={getattr(q_res, 'pitch_deg', 0) or 0:.1f} | S={face_w}px"
            draw.text((cam_x + 10, cam_y + 10), debug_text, font=font_debug, fill=(0, 255, 255))
            draw.text((cam_x + 10, cam_y + 30), f"Multiple: {num_faces > 1} | Valid: {q_res.is_valid}", font=font_debug, fill=(0, 255, 255))

        draw.text((10, 700), "Nhấn 'ESC' để thoát, 'D' để bật/tắt Debug Mode", font=font_debug, fill=(100, 100, 100))

        # Convert back and show
        final_bgr = cv2.cvtColor(np.array(canvas_pil), cv2.COLOR_RGB2BGR)
        cv2.imshow("Auto-Sampling Enrollment", final_bgr)

        key = cv2.waitKey(1)
        if key == 27:  # ESC
            print("\nĐã hủy đăng ký.")
            cap.release()
            cv2.destroyAllWindows()
            sys.exit(0)
        elif key == ord('d') or key == ord('D'):
            debug_mode = not debug_mode

    cap.release()
    cv2.destroyAllWindows()

    if len(aligned_images) == num_images:
        print(f"\nĐang lưu {len(aligned_images)} mẫu vào database...")
        user_id = register_user(args.name, args.role, args.note, aligned_images, captured_landmarks, captured_labels)

        print(f"\n{'='*60}")
        print(f"  ĐĂNG KÝ THÀNH CÔNG!")
        print(f"  User ID   : {user_id}")
        print(f"  Tên        : {args.name}")
        print(f"{'='*60}")
    else:
        print("ĐĂNG KÝ THẤT BẠI — không đủ ảnh.")

