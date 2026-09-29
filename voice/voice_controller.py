"""
voice_controller.py — Điều khiển giọng nói tiếng Việt tích hợp.

Thu âm qua micro → nhận diện giọng nói (Google Speech Recognition) →
tìm lệnh trong bộ nhớ → phát sự kiện qua EventBus.

GIẢI QUYẾT THÁCH THỨC #1 (Blocking - Thu âm):
- Toàn bộ vòng lặp thu âm chạy trên thread riêng (threading.Thread).
- Giao tiếp với hệ thống chính 100% qua EventBus (không dùng biến toàn cục).
- Camera/Recognition hoàn toàn không bị ảnh hưởng.

GIẢI QUYẾT THÁCH THỨC #2 (Xung đột điều khiển):
- Phát sự kiện VOICE_COMMAND thay vì gọi trực tiếp robot API.
- ActionQueue (trong robot_action_engine) sẽ quyết định ưu tiên.

GIẢI QUYẾT THÁCH THỨC #3 (Tài nguyên):
- Graceful stop qua _stop_event (threading.Event).
- Micro được giải phóng khi dừng.
"""
import threading
import time
from logs.logger import get_logger
from config import VOICE_LISTEN_TIMEOUT, VOICE_PHRASE_TIME_LIMIT, VOICE_LANGUAGE

logger = get_logger(__name__)


class VoiceController:
    """
    Luồng thu âm + nhận diện giọng nói tiếng Việt chạy độc lập.

    Khi nhận diện được lệnh hợp lệ, phát sự kiện:
      VOICE_COMMAND { "motion": "Forward", "raw_text": "đi thẳng", "source": "voice" }

    Khi gặp từ lạ (không khớp bộ nhớ):
      VOICE_UNKNOWN_WORD { "raw_text": "...", "source": "voice" }
    """

    def __init__(self, event_bus, robot_memory, mic_index=None):
        self._bus = event_bus
        self._memory = robot_memory
        self._mic_index = mic_index
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._running = False

    # ── Lifecycle ────────────────────────────────────────────────────
    def start(self):
        """Khởi động luồng thu âm ở background."""
        if self._running:
            logger.warning("[VOICE] Đã đang chạy, bỏ qua start().")
            return
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._listen_loop,
            name="VoiceController",
            daemon=True,
        )
        self._thread.start()
        self._running = True
        logger.info("[VOICE] ✅ Luồng thu âm đã khởi động.")
        self._bus.emit("VOICE_STATUS", {"status": "started"})

    def stop(self):
        """Dừng luồng thu âm (graceful shutdown)."""
        self._stop_event.set()
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3)
        logger.info("[VOICE] ⏹️ Luồng thu âm đã dừng.")
        self._bus.emit("VOICE_STATUS", {"status": "stopped"})

    @property
    def is_running(self) -> bool:
        return self._running and self._thread is not None and self._thread.is_alive()

    # ── Core listen loop (chạy trên thread riêng) ────────────────────
    def _listen_loop(self):
        """
        Vòng lặp chính: thu âm → nhận diện → tìm lệnh → emit event.
        Chạy hoàn toàn trên thread riêng, KHÔNG block main async loop.
        """
        try:
            import speech_recognition as sr
        except ImportError:
            logger.error("[VOICE] ❌ Thiếu SpeechRecognition. "
                         "Chạy: pip install SpeechRecognition")
            self._bus.emit("VOICE_STATUS", {"status": "error",
                           "message": "Thiếu thư viện SpeechRecognition"})
            self._running = False
            return

        recognizer = sr.Recognizer()

        try:
            mic = sr.Microphone(device_index=self._mic_index)
        except (OSError, AttributeError) as e:
            logger.error(f"[VOICE] ❌ Không mở được micro: {e}")
            self._bus.emit("VOICE_STATUS", {"status": "error",
                           "message": f"Không mở được micro: {e}"})
            self._running = False
            return

        with mic as source:
            logger.info(f"[VOICE] 🎤 Đang khử ồn môi trường (2 giây)...")
            recognizer.adjust_for_ambient_noise(source, duration=2)
            logger.info("[VOICE] 🎤 Sẵn sàng nhận lệnh giọng nói!")
            self._bus.emit("VOICE_STATUS", {"status": "ready"})

            while not self._stop_event.is_set():
                try:
                    self._bus.emit("VOICE_STATUS", {"status": "listening"})
                    audio_data = recognizer.listen(
                        source,
                        timeout=VOICE_LISTEN_TIMEOUT,
                        phrase_time_limit=VOICE_PHRASE_TIME_LIMIT,
                    )

                    # Nhận diện giọng nói bằng Google Speech Recognition
                    text_result = recognizer.recognize_google(
                        audio_data, language=VOICE_LANGUAGE
                    )
                    text_result = text_result.lower().strip()
                    logger.info(f"[VOICE] 🗣️ Nghe: '{text_result}'")

                    self._bus.emit("VOICE_RECOGNIZED", {
                        "text": text_result,
                        "source": "voice",
                    })

                    # Tìm lệnh trong bộ nhớ
                    motion = self._memory.find_motion(text_result)

                    if motion:
                        logger.info(f"[VOICE] ✅ Khớp lệnh: '{text_result}' → {motion}")
                        self._bus.emit("VOICE_COMMAND", {
                            "motion": motion,
                            "raw_text": text_result,
                            "source": "voice",
                        })
                    else:
                        logger.info(f"[VOICE] ❓ Từ lạ: '{text_result}'")
                        self._bus.emit("VOICE_UNKNOWN_WORD", {
                            "raw_text": text_result,
                            "source": "voice",
                        })

                except Exception as timeout_err:
                    # sr.WaitTimeoutError hoặc sr.UnknownValueError — bình thường
                    err_name = type(timeout_err).__name__
                    if err_name not in ("WaitTimeoutError", "UnknownValueError"):
                        logger.warning(f"[VOICE] ⚠️ {err_name}: {timeout_err}")

                # Nghỉ ngắn để tránh spin-loop
                time.sleep(0.3)

        logger.info("[VOICE] Vòng lặp thu âm đã kết thúc.")
