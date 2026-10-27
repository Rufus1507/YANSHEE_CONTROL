"""
Công cụ chẩn đoán nhanh — kiểm tra kết nối tới robot Yanshee,
mở stream MJPEG, đếm frame, tính FPS và latency.

Chạy:
    python -m tools.test_yanshee_camera --ip 192.168.0.100

Hoặc:
    python tools/test_yanshee_camera.py --ip 192.168.0.100

File này hoạt động ĐỘC LẬP với Face Recognition pipeline.
"""

import argparse
import sys
import os
import time

# Thêm project root vào sys.path
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

import requests
import cv2
import numpy as np

from config import YANSHEE_IP, YANSHEE_STREAM_PORT, YANSHEE_STREAM_TIMEOUT, ROBOT_IP, ROBOT_PORT


def ping_robot(ip: str, port: int) -> bool:
    """Kiểm tra robot có reachable không bằng API battery."""
    try:
        r = requests.get(f"http://{ip}:{port}/v1/devices/battery", timeout=3)
        return r.ok
    except Exception:
        return False


def open_stream(ip: str, stream_port: int, timeout: float):
    """Mở HTTP MJPEG stream từ robot."""
    url = f"http://{ip}:{stream_port}/stream.mjpg"
    print(f"[INFO] Opening stream: {url}")
    resp = requests.get(url, stream=True, timeout=timeout)
    if resp.status_code != 200:
        raise RuntimeError(f"Bad HTTP status {resp.status_code}")
    return resp


def main():
    parser = argparse.ArgumentParser(
        description="Test Yanshee camera MJPEG stream"
    )
    parser.add_argument("--ip", default=YANSHEE_IP,
                        help=f"Yanshee robot IP (default: {YANSHEE_IP})")
    parser.add_argument("--stream-port", type=int, default=YANSHEE_STREAM_PORT,
                        help=f"Stream port (default: {YANSHEE_STREAM_PORT})")
    parser.add_argument("--robot-port", type=int, default=ROBOT_PORT,
                        help=f"Robot API port (default: {ROBOT_PORT})")
    parser.add_argument("--frames", type=int, default=60,
                        help="Number of frames to capture (default: 60)")
    parser.add_argument("--show", action="store_true",
                        help="Show preview window (requires display)")
    args = parser.parse_args()

    ip = args.ip
    stream_port = args.stream_port
    robot_port = args.robot_port
    max_frames = args.frames

    print("=" * 60)
    print("  YANSHEE CAMERA STREAM DIAGNOSTIC TOOL")
    print("=" * 60)
    print(f"  Robot IP      : {ip}")
    print(f"  Robot API Port: {robot_port}")
    print(f"  Stream Port   : {stream_port}")
    print(f"  Max Frames    : {max_frames}")
    print()

    # 1. Ping robot
    print("[STEP 1] Ping robot...")
    if ping_robot(ip, robot_port):
        print(f"  [OK] Robot reachable at {ip}:{robot_port}")
    else:
        print(f"  [FAILED] Robot NOT reachable at {ip}:{robot_port}")
        print("  → Kiểm tra lại IP, port, và kết nối mạng.")
        return

    # 2. Mở stream
    print(f"\n[STEP 2] Opening MJPEG stream...")
    try:
        resp = open_stream(ip, stream_port, YANSHEE_STREAM_TIMEOUT)
        print(f"  [OK] Stream opened successfully")
    except Exception as e:
        print(f"  [FAILED] Cannot open stream: {e}")
        print("  → Stream MJPEG có thể chưa được bật trên robot.")
        print("  → Thử gọi open_vision_stream() nếu có SDK/API hỗ trợ.")
        return

    # 3. Đọc và decode frame
    print(f"\n[STEP 3] Receiving frames...")
    buf = b""
    frame_count = 0
    start_time = time.time()
    decode_errors = 0
    resolutions = set()
    frame_times = []

    try:
        for chunk in resp.iter_content(chunk_size=4096):
            buf += chunk
            # Tìm JPEG markers
            soi = buf.find(b"\xff\xd8")  # Start of Image
            eoi = buf.find(b"\xff\xd9")  # End of Image
            if soi != -1 and eoi != -1 and eoi > soi:
                jpeg = buf[soi:eoi + 2]
                buf = buf[eoi + 2:]
                frame_count += 1
                frame_ts = time.time()
                frame_times.append(frame_ts)

                # Decode
                img = cv2.imdecode(
                    np.frombuffer(jpeg, np.uint8), cv2.IMREAD_COLOR
                )
                if img is None:
                    decode_errors += 1
                    print(f"  [#{frame_count}] [FAILED] Decode failed ({len(jpeg)} bytes)")
                else:
                    h, w = img.shape[:2]
                    resolutions.add(f"{w}x{h}")
                    # Tính FPS tức thì
                    if len(frame_times) >= 2:
                        instant_fps = 1.0 / max(
                            frame_times[-1] - frame_times[-2], 0.001
                        )
                    else:
                        instant_fps = 0.0
                    print(f"  [#{frame_count}] [OK] {w}x{h}  "
                          f"JPEG={len(jpeg):,} bytes  "
                          f"FPS={instant_fps:.1f}")

                    # Preview
                    if args.show:
                        cv2.imshow("Yanshee Camera Test", img)
                        if cv2.waitKey(1) & 0xFF == 27:  # ESC to quit
                            print("\n  → Preview closed by user (ESC)")
                            break

                if frame_count >= max_frames:
                    break
    except KeyboardInterrupt:
        print("\n  → Stopped by user (Ctrl+C)")
    except Exception as e:
        print(f"\n  [FAILED] Stream error: {e}")
    finally:
        if args.show:
            cv2.destroyAllWindows()

    # 4. Báo cáo
    elapsed = time.time() - start_time
    avg_fps = frame_count / elapsed if elapsed > 0 else 0

    print("\n" + "=" * 60)
    print("  KẾT QUẢ")
    print("=" * 60)
    print(f"  Frames received   : {frame_count}")
    print(f"  Decode errors     : {decode_errors}")
    print(f"  Elapsed time      : {elapsed:.2f} s")
    print(f"  Average FPS       : {avg_fps:.1f}")
    print(f"  Resolutions seen  : {', '.join(resolutions) if resolutions else 'N/A'}")

    if frame_count > 0 and decode_errors == 0:
        print(f"\n  [OK] Stream hoạt động tốt!")
    elif frame_count > 0:
        print(f"\n  [WARN] Stream hoạt động nhưng có {decode_errors} lỗi decode.")
    else:
        print(f"\n  [FAILED] Không nhận được frame nào.")

    # 5. Test reconnect (optional)
    print(f"\n[STEP 4] Test reconnect...")
    try:
        resp2 = open_stream(ip, stream_port, YANSHEE_STREAM_TIMEOUT)
        # Đọc 1 frame để xác nhận
        buf2 = b""
        for chunk in resp2.iter_content(chunk_size=4096):
            buf2 += chunk
            s = buf2.find(b"\xff\xd8")
            e = buf2.find(b"\xff\xd9")
            if s != -1 and e != -1 and e > s:
                print(f"  [OK] Reconnect thành công – nhận được frame")
                break
        else:
            print(f"  [FAILED] Reconnect: không nhận được frame")
    except Exception as ex:
        print(f"  [FAILED] Reconnect thất bại: {ex}")

    print()


if __name__ == "__main__":
    main()
