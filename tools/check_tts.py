import sys
import os

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _PROJECT_ROOT)

from robot.speech_engine import SpeechEngine

print("Kiểm tra Local TTS (pyttsx3)...")
tts = SpeechEngine()

print("Đang phát âm thanh: 'Kiểm tra hệ thống giọng nói thành công.'")
tts.say("Kiểm tra hệ thống giọng nói thành công.")
print("Hoàn tất!")
