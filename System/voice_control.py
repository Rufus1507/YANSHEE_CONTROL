"""
voice_control.py  —  System/
==============================
Nhiệm vụ DUY NHẤT:
  1. Mở mic (PyAudio + RNNoise + WebRTC VAD)
  2. Gom câu → gửi audio PCM lên test_whisper_mic.py (server)
  3. Nhận JSON commands từ server
  4. Put từng command vào command_queue của main_control

Toàn bộ xử lý Whisper + NLP nằm ở test_whisper_mic.py.
"""

import os
import sys
import json
import socket
import struct
import time
import itertools
import collections

import numpy as np

# Fix encoding Windows console
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
try:
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

_qc = itertools.count()

# ─── CẤU HÌNH SERVER WHISPER ────────────────────────────────────────────────
WHISPER_HOST = "labai.tail8d0a72.ts.net"   # ← IP máy chạy test_whisper_mic.py
WHISPER_PORT = 9999

# ─── AUDIO ───────────────────────────────────────────────────────────────────
SAMPLE_RATE    = 16000
CHANNELS       = 1
SAMPLE_WIDTH   = 2                                              # int16
VAD_FRAME_MS   = 20
FRAME_SAMPLES  = int(SAMPLE_RATE * VAD_FRAME_MS / 1000)       # 320
FRAME_BYTES    = FRAME_SAMPLES * SAMPLE_WIDTH                  # 640

# ─── VAD ─────────────────────────────────────────────────────────────────────
VAD_AGGRESSIVENESS = 2
SPEECH_THRESHOLD   = 0.60
WINDOW_FRAMES      = 15
MAX_SILENCE_FRAMES = 20
MAX_PHRASE_FRAMES  = 400
PRE_ROLL_FRAMES    = 8

# ─── IMPORT TÙY CHỌN ────────────────────────────────────────────────────────
try:
    import pyrnnoise as _pyrnnoise; _rnnoise_ok = True
except ImportError:
    _rnnoise_ok = False

try:
    import webrtcvad as _webrtcvad; _vad_ok = True
except ImportError:
    _vad_ok = False

try:
    import pyaudio as _pyaudio; _pyaudio_ok = True
except ImportError:
    _pyaudio_ok = False
    print("[VoiceCtrl] ❌ Thiếu pyaudio. Gõ: pip install pyaudio")


# ═════════════════════════════════════════════════════════════════════════════
# SOCKET HELPERS
# ═════════════════════════════════════════════════════════════════════════════

def _recv_exact(sock, n):
    buf = b""
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            return None
        buf += chunk
    return buf

def _send_audio(sock, pcm: bytes):
    sock.sendall(struct.pack(">I", len(pcm)) + pcm)

def _recv_json(sock) -> list:
    raw_len = _recv_exact(sock, 4)
    if raw_len is None:
        return []
    n = struct.unpack(">I", raw_len)[0]
    if n == 0:
        return []
    raw = _recv_exact(sock, n)
    if not raw:
        return []
    try:
        return json.loads(raw.decode("utf-8", errors="replace"))
    except Exception:
        return []

def _connect(host, port):
    while True:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.connect((host, port))
            print(f"[VoiceCtrl] ✅ Kết nối Whisper server {host}:{port}")
            return s
        except ConnectionRefusedError:
            print(f"[VoiceCtrl] Server chưa sẵn sàng, thử lại sau 3s...")
            time.sleep(3)


# ═════════════════════════════════════════════════════════════════════════════
# RNNoise
# ═════════════════════════════════════════════════════════════════════════════

class _RNNoise:
    def __init__(self):
        self.enabled = False
        if _rnnoise_ok:
            try:
                self._dn = _pyrnnoise.NoiseReducer()
                self.enabled = True
            except Exception as e:
                print(f"[RNNoise] Lỗi: {e}. Bỏ qua.")

    def process(self, pcm16k: bytes) -> bytes:
        if not self.enabled:
            return pcm16k
        try:
            arr = np.frombuffer(pcm16k, np.int16).astype(np.float32)
            arr48 = np.repeat(arr, 3)
            out48 = np.zeros_like(arr48)
            for i in range(len(arr48) // 480):
                seg = arr48[i*480:(i+1)*480]
                out48[i*480:(i+1)*480] = self._dn.process_frame(seg)
            return np.clip(out48[::3], -32768, 32767).astype(np.int16).tobytes()
        except Exception:
            return pcm16k


# ═════════════════════════════════════════════════════════════════════════════
# VAD
# ═════════════════════════════════════════════════════════════════════════════

class _VAD:
    def __init__(self):
        self.enabled = False
        if _vad_ok:
            try:
                self._vad = _webrtcvad.Vad(VAD_AGGRESSIVENESS)
                self.enabled = True
            except Exception as e:
                print(f"[VAD] Lỗi: {e}. Dùng RMS fallback.")

    def is_speech(self, pcm: bytes) -> bool:
        if self.enabled:
            try:
                return self._vad.is_speech(pcm, SAMPLE_RATE)
            except Exception:
                pass
        arr = np.frombuffer(pcm, np.int16).astype(np.float32) / 32768.0
        return float(np.sqrt(np.mean(arr**2))) > 0.012


# ═════════════════════════════════════════════════════════════════════════════
# VÒNG LẶP CHÍNH — được gọi từ main_control.py
# ═════════════════════════════════════════════════════════════════════════════

def start_voice_control(cmd_queue=None,
                        host: str = WHISPER_HOST,
                        port: int = WHISPER_PORT):
    """
    Hàm được main_control.py gọi trong thread riêng.
      - Mở mic → RNNoise → VAD → gom câu
      - Gửi PCM lên test_whisper_mic.py
      - Nhận JSON commands về
      - Put lệnh vào cmd_queue
    """
    if not _pyaudio_ok:
        print("[VoiceCtrl] Không có PyAudio. Thoát luồng voice.")
        return

    rnn = _RNNoise()
    vad = _VAD()

    # Mở mic
    pa = _pyaudio.PyAudio()
    try:
        dev_info = pa.get_default_input_device_info()
        dev_idx  = dev_info["index"]
        print(f"[VoiceCtrl] Mic: [{dev_idx}] {dev_info['name']}")
    except OSError:
        print("[VoiceCtrl] Không tìm thấy mic. Thoát luồng voice.")
        pa.terminate()
        return

    try:
        stream = pa.open(
            format=_pyaudio.paInt16,
            channels=CHANNELS,
            rate=SAMPLE_RATE,
            input=True,
            input_device_index=dev_idx,
            frames_per_buffer=FRAME_SAMPLES,
        )
    except OSError as e:
        print(f"[VoiceCtrl] Không mở được mic: {e}")
        pa.terminate()
        return

    print("[VoiceCtrl] Mic đã mở.")

    # Kết nối server Whisper
    sock = _connect(host, port)

    print("\n" + "═"*50)
    print("  🎤  VOICE CONTROL  (RNNoise + VAD + Whisper)")
    print("═"*50)
    print(f"  RNNoise : {'BẬT' if rnn.enabled else 'TẮT'}")
    print(f"  VAD     : {'BẬT (WebRTC)' if vad.enabled else 'TẮT (RMS fallback)'}")
    print(f"  Server  : {host}:{port}")
    print("─"*50)

    ring      = collections.deque(maxlen=WINDOW_FRAMES)
    pre_roll  = collections.deque(maxlen=PRE_ROLL_FRAMES)
    recording = False
    sil_count = 0
    frames: list[bytes] = []

    try:
        while True:
            try:
                raw   = stream.read(FRAME_SAMPLES, exception_on_overflow=False)
                clean = rnn.process(raw)
                is_v  = vad.is_speech(clean)

                ring.append(1 if is_v else 0)
                ratio = sum(ring) / len(ring) if ring else 0.0
                pre_roll.append(clean)

                if not recording:
                    if ratio >= SPEECH_THRESHOLD:
                        recording = True
                        sil_count = 0
                        frames    = list(pre_roll)
                        print("\n🎙️  Đang nghe lệnh...")
                else:
                    frames.append(clean)
                    sil_count = 0 if is_v else sil_count + 1

                    if sil_count >= MAX_SILENCE_FRAMES or len(frames) >= MAX_PHRASE_FRAMES:
                        recording = False

                        trim = MAX_SILENCE_FRAMES // 2
                        if len(frames) > trim:
                            frames = frames[:-trim]

                        pcm = b"".join(frames)
                        frames = []
                        ring.clear()
                        pre_roll.clear()

                        # Bỏ qua câu quá ngắn (<300ms)
                        if len(pcm) < SAMPLE_RATE * SAMPLE_WIDTH * 0.3:
                            print("  (Quá ngắn, bỏ qua)")
                            continue

                        dur = len(pcm) / (SAMPLE_RATE * SAMPLE_WIDTH)
                        rms = float(np.sqrt(np.mean(
                            np.frombuffer(pcm, np.int16).astype(np.float32)**2
                        ))) / 32768.0
                        print(f"⏫ Gửi {len(pcm):,}B ({dur:.1f}s, RMS={rms:.4f})...")

                        # ── Gửi audio → nhận JSON commands ── #
                        try:
                            _send_audio(sock, pcm)
                            cmds = _recv_json(sock)
                        except (BrokenPipeError, ConnectionResetError, OSError) as e:
                            print(f"[VoiceCtrl] Mất kết nối: {e}. Kết nối lại...")
                            try: sock.close()
                            except: pass
                            sock = _connect(host, port)
                            continue

                        # ── Put commands vào queue ── #
                        if cmds and cmd_queue:
                            for cmd in cmds:
                                cmd_queue.put((
                                    cmd["priority"],
                                    next(_qc),
                                    cmd["source"],
                                    cmd["action"],
                                    cmd["data"]
                                ))
                            print(f"✅ Đã gửi {len(cmds)} lệnh vào queue.")
                        elif not cmds:
                            print("  (Server không nhận ra lệnh)")

            except Exception as e:
                if isinstance(e, KeyboardInterrupt):
                    raise
                print(f"[VoiceCtrl] Lỗi: {e}")
                time.sleep(0.1)

    except KeyboardInterrupt:
        print("\n[VoiceCtrl] Nhận tín hiệu dừng.")
    finally:
        try: stream.stop_stream(); stream.close()
        except: pass
        try: pa.terminate()
        except: pass
        try: sock.close()
        except: pass
        print("[VoiceCtrl] Đã dọn dẹp tài nguyên.")
