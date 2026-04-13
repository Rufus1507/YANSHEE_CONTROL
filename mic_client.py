"""
mic_client.py  (v2 — RNNoise + VAD)
====================================
Pipeline xử lý trước khi gửi lên server Whisper:

  Mic (PyAudio)
    │
    ▼  chunk 10ms (160 samples @ 16kHz)
  [RNNoise]            — Khử ồn thần kinh nhân tạo (pyrnnoise)
    │
    ▼
  [WebRTC VAD]         — Lọc frame không phải giọng nói (webrtcvad-wheels)
    │  gom các frame có VAD=True thành một đoạn câu
    ▼
  [Gửi TCP] → server test_whisper_mic.py (raw PCM int16 16kHz)
    │
    ▼
  [Nhận lệnh text] ← server (text kết quả)

Cài thư viện cần thiết:
    pip install pyaudio pyrnnoise webrtcvad-wheels numpy

Cách dùng:
    python mic_client.py                        # localhost:9999
    python mic_client.py --host 192.168.1.x     # server từ xa
    python mic_client.py --host 127.0.0.1 --port 9998
    python mic_client.py --list-devices         # liệt kê thiết bị mic
"""

import os
import sys
# Fix UnicodeEncodeError khi in tiếng Việt ra Windows console
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import socket
import struct
import argparse
import time
import collections
import numpy as np

# ─────────────────────────── KẾT NỐI SERVER ──────────────────────────────── #
DEFAULT_HOST = "10.17.0.82"
DEFAULT_PORT = 9999

# ─────────────────────────── AUDIO CAPTURE ───────────────────────────────── #
SAMPLE_RATE      = 16000   # Hz — WebRTC VAD & Whisper đều thích 16kHz
CHANNELS         = 1       # Mono
SAMPLE_WIDTH     = 2       # bytes (int16)
# Kích thước frame phải là bội của 10ms cho VAD: 10ms=160, 20ms=320, 30ms=480
VAD_FRAME_MS     = 20      # ms mỗi frame VAD (10 / 20 / 30)
FRAME_SAMPLES    = int(SAMPLE_RATE * VAD_FRAME_MS / 1000)   # = 320
FRAME_BYTES      = FRAME_SAMPLES * SAMPLE_WIDTH              # = 640

# ─────────────────────────── VAD (WebRTC) ────────────────────────────────── #
VAD_AGGRESSIVENESS  = 2      # 0 (ít lọc) – 3 (lọc mạnh nhất). 2 cân bằng tốt
# Tỉ lệ frame "có tiếng" trong cửa sổ trượt để bắt đầu ghi
SPEECH_THRESHOLD    = 0.6    # ≥60% frame trong cửa sổ phải là speech → bắt đầu
# Tỉ lệ frame "im lặng" trong cửa sổ để dừng ghi
SILENCE_THRESHOLD   = 0.25   # <25% speech → kết thúc đoạn
WINDOW_FRAMES       = 15     # cửa sổ trượt (15 frames × 20ms = 300ms nhìn lui)
MAX_SILENCE_FRAMES  = 20     # số frame im lặng liên tiếp được chấp nhận sau câu (20×20ms=400ms)
MAX_PHRASE_FRAMES   = 400    # độ dài tối đa một câu (400×20ms = 8 giây)
PRE_ROLL_FRAMES     = 8      # số frame trước khi phát hiện speech (padding ~160ms)

# ─────────────────────────── RNNoise ─────────────────────────────────────── #
# RNNoise xử lý 48kHz với frame 10ms = 480 mẫu.
# Chúng ta dùng 16kHz nên cần upsample → denoise → downsample.
# pyrnnoise hỗ trợ internal resampling, kiểm tra khi import.
RNNOISE_ENABLED  = True    # Đặt False nếu không cài pyrnnoise

# ─────────────────────────── IMPORT CÁC THƯ VIỆN TÙY CHỌN ───────────────── #
# RNNoise
try:
    import pyrnnoise
    _rnnoise_available = True
    print("[Init] ✅ pyrnnoise đã được tải.")
except ImportError:
    _rnnoise_available = False
    print("[Init] ⚠️  pyrnnoise chưa được cài. Bỏ qua khử ồn RNNoise.")
    print("       Gõ: pip install pyrnnoise")

# WebRTC VAD
try:
    import webrtcvad
    _vad_available = True
    print("[Init] ✅ webrtcvad đã được tải.")
except ImportError:
    _vad_available = False
    print("[Init] ⚠️  webrtcvad chưa được cài. VAD bị tắt (sẽ dùng RMS fallback).")
    print("       Gõ: pip install webrtcvad-wheels")

# PyAudio
try:
    import pyaudio
    _pyaudio_available = True
except ImportError:
    _pyaudio_available = False
    print("[Init] ❌ pyaudio chưa cài. Gõ: pip install pyaudio")
    print("       Không thể chạy mic_client mà không có pyaudio!")


# ═════════════════════════════════════════════════════════════════════════════
# CÁC HÀM TIỆN ÍCH SOCKET
# ═════════════════════════════════════════════════════════════════════════════

def _recv_exact(sock: socket.socket, n: int) -> bytes | None:
    """Đọc đúng n bytes từ socket. Trả None nếu kết nối đứt."""
    buf = b""
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            return None
        buf += chunk
    return buf


def send_audio(sock: socket.socket, pcm_bytes: bytes):
    """Gửi gói audio: [4 bytes big-endian uint32 length] + [PCM payload]."""
    header = struct.pack(">I", len(pcm_bytes))
    sock.sendall(header + pcm_bytes)


def recv_response(sock: socket.socket) -> str:
    """Nhận phản hồi text từ server."""
    raw_len = _recv_exact(sock, 4)
    if raw_len is None:
        return ""
    msg_len = struct.unpack(">I", raw_len)[0]
    if msg_len == 0:
        return ""
    raw_msg = _recv_exact(sock, msg_len)
    if raw_msg is None:
        return ""
    return raw_msg.decode("utf-8", errors="replace")


def connect_to_server(host: str, port: int) -> socket.socket:
    """Kết nối TCP tới server, tự thử lại mỗi 2 giây."""
    while True:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect((host, port))
            print(f"[Mic Client] ✅ Đã kết nối tới {host}:{port}")
            return sock
        except ConnectionRefusedError:
            print(f"[Mic Client] Server chưa sẵn sàng. Thử lại sau 2 giây...")
            time.sleep(2)


# ═════════════════════════════════════════════════════════════════════════════
# RNNOISE — KHỬ ỒN
# ═════════════════════════════════════════════════════════════════════════════

class RNNoiseProcessor:
    """
    Wrapper khử ồn dùng pyrnnoise.
    pyrnnoise xử lý 48kHz / 480 sample per frame.
    Chúng ta sẽ upsample 16kHz→48kHz, denoise, rồi downsample về 16kHz.
    """
    def __init__(self):
        self._denoiser = None
        if _rnnoise_available and RNNOISE_ENABLED:
            try:
                self._denoiser = pyrnnoise.NoiseReducer()
                self._enabled = True
                print("[RNNoise] Khởi tạo thành công.")
            except Exception as e:
                print(f"[RNNoise] Lỗi khởi tạo: {e}. Bỏ qua.")
                self._enabled = False
        else:
            self._enabled = False

    @property
    def enabled(self):
        return self._enabled

    def process_frame(self, pcm_int16_16k: bytes) -> bytes:
        """
        Nhận frame PCM int16 16kHz → trả về PCM int16 16kHz đã khử ồn.
        Frame phải đúng FRAME_BYTES bytes (= FRAME_SAMPLES × 2).
        """
        if not self._enabled:
            return pcm_int16_16k

        try:
            # Chuyển sang float32
            arr_16k = np.frombuffer(pcm_int16_16k, dtype=np.int16).astype(np.float32)

            # Upsample 16kHz → 48kHz (hệ số 3) bằng repeat (đơn giản, đủ dùng)
            arr_48k = np.repeat(arr_16k, 3)

            # RNNoise cần frame 480 mẫu @ 48kHz (= 10ms)
            # Chúng ta có FRAME_SAMPLES*3 mẫu, chia đều thành nhiều frame 480
            denoised_48k = np.zeros_like(arr_48k)
            n_frames = len(arr_48k) // 480
            for i in range(n_frames):
                segment = arr_48k[i*480:(i+1)*480]
                denoised_segment = self._denoiser.process_frame(segment)
                denoised_48k[i*480:(i+1)*480] = denoised_segment

            # Downsample 48kHz → 16kHz (lấy mẫu thứ 3)
            arr_out_16k = denoised_48k[::3]

            # Clip & chuyển về int16
            arr_out_16k = np.clip(arr_out_16k, -32768, 32767).astype(np.int16)
            return arr_out_16k.tobytes()

        except Exception:
            # Nếu lỗi bất kỳ → trả nguyên gốc
            return pcm_int16_16k


# ═════════════════════════════════════════════════════════════════════════════
# VAD — PHÁT HIỆN GIỌNG NÓI
# ═════════════════════════════════════════════════════════════════════════════

class VoiceActivityDetector:
    """
    WebRTC VAD wrapper với cửa sổ trượt để quyết định
    bắt đầu / kết thúc một đoạn giọng nói.
    """
    def __init__(self):
        self._vad = None
        if _vad_available:
            try:
                self._vad = webrtcvad.Vad(VAD_AGGRESSIVENESS)
                print(f"[VAD] WebRTC VAD khởi tạo (aggressiveness={VAD_AGGRESSIVENESS}).")
                self._enabled = True
            except Exception as e:
                print(f"[VAD] Lỗi: {e}. Dùng RMS fallback.")
                self._enabled = False
        else:
            self._enabled = False

    def is_speech(self, pcm_bytes: bytes) -> bool:
        """Kiểm tra frame PCM int16 16kHz có phải giọng nói không."""
        if self._enabled:
            try:
                return self._vad.is_speech(pcm_bytes, SAMPLE_RATE)
            except Exception:
                pass
        # Fallback: dùng RMS
        arr = np.frombuffer(pcm_bytes, dtype=np.int16).astype(np.float32) / 32768.0
        rms = float(np.sqrt(np.mean(arr ** 2)))
        return rms > 0.012   # ngưỡng RMS fallback


# ═════════════════════════════════════════════════════════════════════════════
# VÒng LẶP CHÍNH
# ═════════════════════════════════════════════════════════════════════════════

def list_devices():
    """In danh sách thiết bị microphone."""
    if not _pyaudio_available:
        print("Cần cài pyaudio.")
        return
    pa = pyaudio.PyAudio()
    print("\n=== Danh sách thiết bị âm thanh ===")
    for i in range(pa.get_device_count()):
        info = pa.get_device_info_by_index(i)
        if info["maxInputChannels"] > 0:
            print(f"  [{i}] {info['name']} — {int(info['defaultSampleRate'])} Hz")
    pa.terminate()
    print()


def run_client(host: str, port: int, device_index: int | None = None):
    """Vòng lặp chính: mở mic → RNNoise → VAD → gom câu → gửi server → nhận lệnh."""

    if not _pyaudio_available:
        print("[Lỗi] Cần cài pyaudio: pip install pyaudio")
        sys.exit(1)

    # ── Khởi tạo các bộ xử lý ───────────────────────────────────────────── #
    denoiser = RNNoiseProcessor()
    vad      = VoiceActivityDetector()

    # ── Mở microphone với PyAudio ────────────────────────────────────────── #
    pa = pyaudio.PyAudio()

    # Tìm thiết bị mặc định nếu không chỉ định
    if device_index is None:
        try:
            default_info = pa.get_default_input_device_info()
            device_index = default_info["index"]
            print(f"[PyAudio] Dùng mic mặc định: [{device_index}] {default_info['name']}")
        except OSError:
            print("[Lỗi] Không tìm thấy microphone mặc định.")
            pa.terminate()
            sys.exit(1)

    try:
        stream = pa.open(
            format=pyaudio.paInt16,
            channels=CHANNELS,
            rate=SAMPLE_RATE,
            input=True,
            input_device_index=device_index,
            frames_per_buffer=FRAME_SAMPLES,
        )
    except OSError as e:
        print(f"[Lỗi] Không mở được stream mic: {e}")
        pa.terminate()
        sys.exit(1)

    print("[PyAudio] Stream mic đã mở thành công.")

    # ── Kết nối server ───────────────────────────────────────────────────── #
    sock = connect_to_server(host, port)

    print()
    print("═" * 58)
    print("  🎤  MIC CLIENT v2  —  RNNoise + VAD  —  Whisper Server")
    print("═" * 58)
    if denoiser.enabled:
        print("  🔇 RNNoise:  BẬT  (khử ồn nền)")
    else:
        print("  🔇 RNNoise:  TẮT  (chưa cài pyrnnoise)")
    if vad._enabled:
        print(f"  🗣️  VAD:      BẬT  (WebRTC, aggressiveness={VAD_AGGRESSIVENESS})")
    else:
        print("  🗣️  VAD:      TẮT  (dùng RMS fallback)")
    print(f"  📻  Frame:    {VAD_FRAME_MS}ms × {FRAME_SAMPLES} samples @ {SAMPLE_RATE}Hz")
    print("  Nói lệnh rõ ràng. Nhấn  Ctrl+C  để thoát.")
    print("─" * 58)

    # ── Cửa sổ trượt VAD ────────────────────────────────────────────────── #
    ring = collections.deque(maxlen=WINDOW_FRAMES)   # vòng lặp nhỏ để nhìn lui
    pre_roll = collections.deque(maxlen=PRE_ROLL_FRAMES)  # padding trước câu

    recording = False       # Đang trong giữa một câu không?
    silence_count = 0       # Số frame im lặng liên tiếp sau khi bắt đầu
    phrase_frames: list[bytes] = []   # Danh sách frame (đã clean) của câu hiện tại

    try:
        while True:
            try:
                # ── Đọc một frame từ mic ─────────────────────────────── #
                raw_frame = stream.read(FRAME_SAMPLES, exception_on_overflow=False)

                # ── RNNoise — khử ồn ─────────────────────────────────── #
                clean_frame = denoiser.process_frame(raw_frame)

                # ── WebRTC VAD ────────────────────────────────────────── #
                is_voice = vad.is_speech(clean_frame)
                ring.append(1 if is_voice else 0)

                speech_ratio = sum(ring) / len(ring) if ring else 0.0

                # Padding trước câu (luôn giữ vài frame gần nhất)
                pre_roll.append(clean_frame)

                if not recording:
                    # ── Chờ bắt đầu câu ─────────────────────────────── #
                    if speech_ratio >= SPEECH_THRESHOLD:
                        recording = True
                        silence_count = 0
                        # Thêm pre-roll (audio ngay trước khi phát hiện)
                        phrase_frames = list(pre_roll)
                        print("\n🎙️  Bắt đầu ghi... (đang nghe lệnh)")
                else:
                    # ── Đang ghi câu ─────────────────────────────────── #
                    phrase_frames.append(clean_frame)

                    if not is_voice:
                        silence_count += 1
                    else:
                        silence_count = 0

                    # Điều kiện kết thúc câu:
                    # (a) Quá nhiều im lặng sau câu nói, HOẶC
                    # (b) Câu quá dài (safety limit)
                    end_of_phrase = (
                        silence_count >= MAX_SILENCE_FRAMES
                        or len(phrase_frames) >= MAX_PHRASE_FRAMES
                    )

                    if end_of_phrase:
                        recording = False
                        silence_count = 0

                        # Bỏ bớt frame im lặng cuối (padding out = MAX_SILENCE_FRAMES/2)
                        trim_tail = MAX_SILENCE_FRAMES // 2
                        if len(phrase_frames) > trim_tail:
                            phrase_frames = phrase_frames[:-trim_tail]

                        pcm_bytes = b"".join(phrase_frames)
                        phrase_frames = []
                        ring.clear()
                        pre_roll.clear()

                        # Kiểm tra độ dài tối thiểu (~300ms)
                        min_bytes = SAMPLE_RATE * SAMPLE_WIDTH * 0.3  # 0.3 giây
                        if len(pcm_bytes) < min_bytes:
                            print("  (Câu quá ngắn, bỏ qua)")
                            continue

                        # ── Gửi lên server ───────────────────────────── #
                        rms = float(np.sqrt(np.mean(
                            np.frombuffer(pcm_bytes, np.int16).astype(np.float32) ** 2
                        ))) / 32768.0

                        duration_s = len(pcm_bytes) / (SAMPLE_RATE * SAMPLE_WIDTH)
                        print(f"⏫ Gửi {len(pcm_bytes):,} bytes ({duration_s:.1f}s, RMS={rms:.4f})...")

                        try:
                            send_audio(sock, pcm_bytes)
                            print("⏳ Đang chờ kết quả từ server...")
                            response = recv_response(sock)
                            if response:
                                print(f"✅ [Lệnh nhận được]: {response}")
                            else:
                                print("  (Server không nhận ra lệnh)")
                        except (BrokenPipeError, ConnectionResetError, OSError) as e:
                            print(f"\n[Mic Client] Mất kết nối: {e}. Đang kết nối lại...")
                            sock.close()
                            sock = connect_to_server(host, port)

            except KeyboardInterrupt:
                raise
            except Exception as e:
                print(f"[Lỗi vòng lặp] {e}")
                time.sleep(0.1)

    except KeyboardInterrupt:
        print("\n\n[Mic Client] Đã nhận Ctrl+C. Đang tắt...")
    finally:
        stream.stop_stream()
        stream.close()
        pa.terminate()
        sock.close()
        print("[Mic Client] Đã giải phóng mic và đóng kết nối.")


# ═════════════════════════════════════════════════════════════════════════════
# ENTRY POINT
# ═════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Mic Client v2 — RNNoise + VAD + Whisper Server"
    )
    parser.add_argument(
        "--host",
        default=DEFAULT_HOST,
        help=f"Địa chỉ IP server Whisper (mặc định: {DEFAULT_HOST})",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=DEFAULT_PORT,
        help=f"Cổng TCP server (mặc định: {DEFAULT_PORT})",
    )
    parser.add_argument(
        "--device",
        type=int,
        default=None,
        help="Index thiết bị microphone (dùng --list-devices để xem danh sách)",
    )
    parser.add_argument(
        "--list-devices",
        action="store_true",
        help="Liệt kê tất cả thiết bị microphone và thoát",
    )
    args = parser.parse_args()

    if args.list_devices:
        list_devices()
        sys.exit(0)

    run_client(args.host, args.port, args.device)
