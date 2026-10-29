"""
Text-to-Speech engine.
Uses Windows SAPI / pyttsx3 safely across threads.
Falls back gracefully if TTS is unavailable.
"""
import sys
import threading
from logs.logger import get_logger

logger = get_logger(__name__)

_speech_lock = threading.Lock()


class SpeechEngine:
    """Thread-safe abstraction for local TTS on Windows / Linux."""

    def say(self, text: str) -> bool:
        """Speak *text* using local TTS. Returns True on success."""
        if not text or not str(text).strip():
            return False

        with _speech_lock:
            # 1. On Windows, try SAPI directly with CoInitialize
            if sys.platform == "win32":
                try:
                    import pythoncom
                    import win32com.client
                    pythoncom.CoInitialize()
                    try:
                        speaker = win32com.client.Dispatch("SAPI.SpVoice")
                        # 0 = SVSFDefault (synchronous)
                        speaker.Speak(str(text), 0)
                        logger.info("SpeechEngine (SAPI) đã nói: %s", text)
                        return True
                    finally:
                        pythoncom.CoUninitialize()
                except Exception as sapi_err:
                    logger.debug("SAPI TTS error: %s, trying pyttsx3 fallback", sapi_err)

            # 2. Secondary fallback: pyttsx3 with fresh instance
            try:
                import pyttsx3
                engine = pyttsx3.init()
                # Try to pick an English voice if available
                try:
                    for voice in engine.getProperty("voices"):
                        if "en" in voice.id.lower() or "english" in voice.name.lower():
                            engine.setProperty("voice", voice.id)
                            break
                    engine.setProperty("rate", 160)
                except Exception:
                    pass
                engine.say(str(text))
                engine.runAndWait()
                engine.stop()
                logger.info("SpeechEngine (pyttsx3) đã nói: %s", text)
                return True
            except Exception as p_err:
                logger.warning("Local TTS error: %s", p_err)
                return False
