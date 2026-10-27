"""
Text-to-Speech engine.
Uses pyttsx3 (offline, works on Windows).
Falls back gracefully if TTS is unavailable.
"""
from logs.logger import get_logger

logger = get_logger(__name__)

_engine = None


def _get_engine():
    global _engine
    if _engine is not None:
        return _engine
    try:
        import pyttsx3
        _engine = pyttsx3.init()
        # Try to pick an English voice if available
        for voice in _engine.getProperty("voices"):
            if "en" in voice.id.lower() or "english" in voice.name.lower():
                _engine.setProperty("voice", voice.id)
                break
        _engine.setProperty("rate", 160)
        return _engine
    except Exception:
        logger.exception("Không thể khởi tạo pyttsx3")
        return None


class SpeechEngine:
    """Abstraction for TTS. Can be swapped for Yanshee TTS or file-based audio."""

    def say(self, text: str) -> bool:
        """Speak *text* using the local TTS engine. Returns True on success."""
        engine = _get_engine()
        if engine is None:
            logger.warning("TTS không khả dụng – bỏ qua: %s", text)
            return False
        try:
            engine.say(text)
            engine.runAndWait()
            logger.info("Đã nói: {}", text)
            return True
        except Exception:
            logger.exception("TTS lỗi khi nói: {}", text)
            return False
