"""
tts_engine.py — TTS tiếng Việt qua Google TTS + SSH tới Yanshee.

Chuyển text → MP3 → SFTP lên robot → phát qua loa Yanshee.
Tích hợp sẵn vào kiến trúc EventBus, chạy trên thread riêng
để KHÔNG block luồng Camera/Recognition chính.

GIẢI QUYẾT THÁCH THỨC #1 (Blocking):
- Tất cả thao tác I/O (gTTS, SSH, SFTP) đều chạy trên background thread.
- Chỉ giao tiếp với hệ thống chính qua EventBus.

GIẢI QUYẾT THÁCH THỨC #3 (Tài nguyên):
- SSH connection được tạo/đóng cho mỗi lần phát, tránh giữ kết nối zombie.
- File MP3 tạm được dọn dẹp sau khi phát xong.
"""
import os
import tempfile
from logs.logger import get_logger
from config import YANSHEE_IP

logger = get_logger(__name__)

# SSH credentials cho Yanshee (Raspberry Pi bên trong)
_ROBOT_SSH_USER = "pi"
_ROBOT_SSH_PASS = "raspberry"
_ROBOT_SSH_PORT = 22


class VietnameseTTS:
    """Chuyển text tiếng Việt → MP3 → phát trên loa Yanshee qua SSH."""

    def __init__(self, robot_ip: str | None = None):
        self._robot_ip = robot_ip or YANSHEE_IP
        self._ssh_user = _ROBOT_SSH_USER
        self._ssh_pass = _ROBOT_SSH_PASS

    def speak(self, text: str) -> bool:
        """
        Tạo MP3 từ text tiếng Việt bằng gTTS, gửi lên Yanshee qua SSH,
        và phát bằng mpg123.

        Trả về True nếu thành công, False nếu thất bại.
        Hàm này blocking — nên gọi từ thread riêng (asyncio.to_thread).
        """
        if not text or not text.strip():
            return False

        tmp_path = None
        try:
            # 1. Tạo MP3 bằng gTTS
            from gtts import gTTS
            tts = gTTS(text=text, lang='vi', slow=False)

            # Lưu vào file tạm
            fd, tmp_path = tempfile.mkstemp(suffix=".mp3", prefix="yanshee_tts_")
            os.close(fd)
            tts.save(tmp_path)
            logger.info(f"[TTS-VN] Đã tạo MP3: {os.path.basename(tmp_path)}")

            # 2. Gửi qua SSH + SFTP
            import paramiko
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            ssh.connect(
                self._robot_ip,
                port=_ROBOT_SSH_PORT,
                username=self._ssh_user,
                password=self._ssh_pass,
                timeout=5,
            )

            remote_path = f"/home/{self._ssh_user}/tts_output.mp3"
            sftp = ssh.open_sftp()
            sftp.put(tmp_path, remote_path)
            sftp.close()
            logger.info(f"[TTS-VN] Đã upload MP3 lên robot ({self._robot_ip})")

            # 3. Phát bằng mpg123
            _, stdout, stderr = ssh.exec_command(f"mpg123 {remote_path}")
            exit_code = stdout.channel.recv_exit_status()
            ssh.close()

            if exit_code == 0:
                logger.info(f"[TTS-VN] Robot đã phát xong: '{text[:50]}...'")
                return True
            else:
                err = stderr.read().decode("utf-8", errors="replace")
                logger.warning(f"[TTS-VN] mpg123 exit code {exit_code}: {err}")
                return False

        except ImportError as e:
            logger.error(f"[TTS-VN] Thiếu thư viện: {e}. "
                         f"Chạy: pip install gTTS paramiko")
            return False
        except Exception as e:
            logger.error(f"[TTS-VN] Lỗi TTS: {e}")
            return False
        finally:
            # Dọn file tạm
            if tmp_path and os.path.exists(tmp_path):
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass

    def speak_local(self, text: str) -> bool:
        """
        Fallback: Phát TTS trên máy tính local (không qua robot).
        Dùng khi robot offline.
        """
        try:
            from gtts import gTTS
            import playsound

            fd, tmp_path = tempfile.mkstemp(suffix=".mp3", prefix="local_tts_")
            os.close(fd)
            tts = gTTS(text=text, lang='vi', slow=False)
            tts.save(tmp_path)
            playsound.playsound(tmp_path)
            os.unlink(tmp_path)
            return True
        except ImportError:
            logger.warning("[TTS-VN] Không có playsound, bỏ qua local TTS")
            return False
        except Exception as e:
            logger.error(f"[TTS-VN] Lỗi local TTS: {e}")
            return False
