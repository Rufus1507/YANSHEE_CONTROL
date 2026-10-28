"""
voice/gemini_ai_controller.py — Bộ não Gemini AI Trò chuyện & Điều khiển Ngữ nghĩa Tự nhiên
=============================================================================================
Tính năng Chế độ 3 (Gemini AI Speech-to-Speech & Natural Intent Recognition):
1. Thu âm tiếng Việt từ Micro laptop qua speech_recognition.
2. Đưa câu nói tự nhiên lên Google Gemini AI để:
   - Phân tích ý định tự nhiên (Intent Recognition) -> tìm hành động tương ứng trong ROBOT_MOTIONS
   - Trò chuyện / đố vui / trả lời câu hỏi đóng vai Robot Yanshee
3. Phản hồi giọng nói tiếng Việt qua VietnameseTTS (loa Robot Yanshee hoặc loa máy tính local).
4. Đẩy lệnh motion vào ActionQueue với độ ưu tiên VOICE.
"""

import json
import os
import re
import threading
import time
from typing import Optional, Dict, Any

from logs.logger import get_logger
from config import (
    GEMINI_API_KEY,
    VOICE_LISTEN_TIMEOUT,
    VOICE_PHRASE_TIME_LIMIT,
    VOICE_LANGUAGE,
)
from voice.tts_engine import VietnameseTTS

logger = get_logger(__name__)

# Danh sách hành động chuẩn mà phần cứng Robot Yanshee hỗ trợ
ROBOT_MOTIONS = [
    # Nhóm hành động hệ thống
    "Base_TurnR", "ActionAging1", "Stop", "MerryChristmas", "TurnRight1", 
    "SweetAndSour", "Base_Backward", "GoalKeeper2", "calibration", "Football_RShoot", 
    "Base_GetupF", "ShootLeft", "knee right", "OneStepMoveLeft", "TurnLeft", 
    "knee left", "Football_LKeep", "TurnRight", "Fight_LSideHit", "Forward1", 
    "Base_Leftward", "LeftTackle", "ActionAging", "RaiseRightHand", "Base_Forward", 
    "LeftSidePunch", "WakaWaka", "Football_LKick", "OneStepMoveRight", "GetUp", 
    "RightHitForward", "rightmovestep", "Base_GetupB", "OneStepForward", "Base_TurnL", 
    "Victory", "Left slide tackle", "Football_LShoot", "ExitEnergySavingReset", "Reset", 
    "OneStepTurnRight", "OneStepTurnLeft", "Football_RKick", "Shutdown", "TurnLeftSlowly", 
    "Fight_LHit", "Football_RKeep", "Football_LSideK", "PushUp", "TurnL_tiny", 
    "GoalKeeper1", "Fight_RHit", "GetupFront", "TurnR_tiny", "Base_Rightward", 
    "Rightward", "HappyBirthday", "Hug", "ResetSwitch", "LeftHitForward", 
    "TurnLeft1", "Backward1", "ShootRight", "TurnRightSlowly", "WeAreTakingOff", 
    "Leftward", "Fight_RSideHit", "OneStepBackward", "Football_RSideK", "RightSidePunch", 
    "Forward", "leftmovestep", "GetupRear", "RightTackle", "calibration_new", 
    "reset_without_head", "Backward", "EnterEnergySavingSquat", "Move_fast",
    
    # Nhóm hành động điều khiển bộ phận
    "F_MoveF_E", "H_WaveRH", "H_Rise_R", "F_MoveF_R", "H_Rise_B", 
    "Hd_Wacth_R", "F_Reset_S", "Hd_Reset_S", "F_MoveB_A", "F_TurnR_T", 
    "F_TurnL_T", "F_MoveR", "Track_TurnR", "Hd_Wacth_F", "F_MoveF_A", 
    "CarryBox", "H_HWave_C", "H_Wave_R", "H_Rise_L", "H_Bec_L", 
    "F_MoveF_B", "H_HWave_L", "H_Bec_R", "H_Str_L", "H_Bec_B", 
    "Hd_Wacth_L", "Reset_S", "Track_TurnL", "H_Str_B", "F_MoveB_E", 
    "F_MoveL", "H_Str_R", "H_RBox", "H_Reset_S"
]


class GeminiAIController:
    """
    Quản lý chế độ Gemini AI: Lắng nghe giọng nói, gọi Gemini AI phân tích ý định
    hoặc trả lời câu hỏi, và kích hoạt hành động + phát âm thanh TTS.
    """

    def __init__(self, event_bus, robot_memory=None, mic_index=None, api_key: str = ""):
        self._bus = event_bus
        self._memory = robot_memory
        self._mic_index = mic_index
        self.api_key = api_key or GEMINI_API_KEY or os.getenv("GEMINI_API_KEY", "")
        
        self._tts = VietnameseTTS()
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._running = False

    # ── Lifecycle ────────────────────────────────────────────────────
    def start(self):
        """Khởi động luồng Gemini AI Voice Controller."""
        if self._running:
            logger.warning("[GEMINI-AI] Đã đang chạy, bỏ qua start().")
            return
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._listen_loop,
            name="GeminiAIController",
            daemon=True,
        )
        self._thread.start()
        self._running = True
        logger.info("[GEMINI-AI] ✅ Luồng Gemini AI đã khởi động.")
        self._bus.emit("GEMINI_AI_STATUS", {"status": "started"})

    def stop(self):
        """Dừng luồng Gemini AI (graceful shutdown)."""
        self._stop_event.set()
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3)
        logger.info("[GEMINI-AI] ⏹️ Luồng Gemini AI đã dừng.")
        self._bus.emit("GEMINI_AI_STATUS", {"status": "stopped"})

    @property
    def is_running(self) -> bool:
        return self._running and self._thread is not None and self._thread.is_alive()

    # ── Vòng lặp thu âm ──────────────────────────────────────────────
    def _listen_loop(self):
        try:
            import speech_recognition as sr
        except ImportError:
            logger.error("[GEMINI-AI] ❌ Thiếu SpeechRecognition. Cài đặt: pip install SpeechRecognition")
            self._running = False
            return

        recognizer = sr.Recognizer()

        try:
            mic = sr.Microphone(device_index=self._mic_index)
        except Exception as e:
            logger.error(f"[GEMINI-AI] ❌ Không mở được Micro: {e}")
            self._running = False
            return

        with mic as source:
            print("\n[GEMINI-AI] 🎤 Đang khử ồn môi trường xung quanh (2 giây)...")
            recognizer.adjust_for_ambient_noise(source, duration=2)
            print("[GEMINI-AI] 🤖 SẴN SÀNG! Hãy nói vào Micro (Trò chuyện hoặc ra lệnh)...")
            self._bus.emit("GEMINI_AI_STATUS", {"status": "ready"})

            while not self._stop_event.is_set():
                try:
                    self._bus.emit("GEMINI_AI_STATUS", {"status": "listening"})
                    audio = recognizer.listen(
                        source,
                        timeout=VOICE_LISTEN_TIMEOUT,
                        phrase_time_limit=VOICE_PHRASE_TIME_LIMIT,
                    )

                    user_speech = recognizer.recognize_google(audio, language=VOICE_LANGUAGE)
                    user_speech = user_speech.strip()
                    if not user_speech:
                        continue

                    print(f"\n[BẠN NÓI]: {user_speech}")
                    self._bus.emit("VOICE_RECOGNIZED", {"text": user_speech, "source": "gemini_ai"})

                    # Xử lý lệnh thoát nhanh
                    if any(w in user_speech.lower() for w in ["tạm biệt", "thoát chế độ", "nghỉ ngơi đi"]):
                        bye_msg = "Tạm biệt bạn nhé! Em sẵn sàng nghỉ ngơi."
                        print(f"[YANSHEE]: {bye_msg}")
                        self._tts.speak(bye_msg)
                        continue

                    # Gọi bộ não Gemini AI xử lý
                    self._handle_user_speech(user_speech)

                except sr.WaitTimeoutError:
                    pass
                except sr.UnknownValueError:
                    pass
                except Exception as e:
                    err_name = type(e).__name__
                    if err_name not in ("WaitTimeoutError", "UnknownValueError"):
                        logger.warning(f"[GEMINI-AI] ⚠️ {err_name}: {e}")

                time.sleep(0.3)

        logger.info("[GEMINI-AI] Vòng lặp Gemini AI đã kết thúc.")

    # ── Xử lý câu nói qua Gemini AI ──────────────────────────────────
    def _handle_user_speech(self, user_speech: str):
        """Phân tích câu nói bằng Gemini AI và thực thi hành động / phản hồi."""
        print("[YANSHEE ĐANG SUY NGHĨ]...")
        self._bus.emit("GEMINI_AI_STATUS", {"status": "thinking", "text": user_speech})

        result = self._query_gemini_brain(user_speech)
        res_type = result.get("type", "chat")
        motion = result.get("motion")
        reply = result.get("reply", "")

        # 1. Nếu là lệnh hành động
        if res_type == "action" and motion and motion in ROBOT_MOTIONS:
            print(f"[GEMINI INTENT] 🎯 Nhận diện hành động: {motion}")
            if reply:
                print(f"[YANSHEE]: {reply}")
                # Phát giọng nói xác nhận
                self._tts.speak(reply)

            # Phát sự kiện lệnh VOICE để ActionQueue thực thi hành động
            self._bus.emit("VOICE_COMMAND", {
                "motion": motion,
                "raw_text": user_speech,
                "source": "gemini_ai",
                "reply": reply,
            })
        else:
            # 2. Nếu là trò chuyện / hỏi đáp
            if reply:
                print(f"[YANSHEE TRẢ LỜI]: {reply}")
                self._bus.emit("GEMINI_AI_REPLY", {"text": reply, "raw_text": user_speech})
                self._tts.speak(reply)
            else:
                fallback_msg = "Em nghe rõ rồi nhưng chưa hiểu lắm, bạn nói lại nhé!"
                print(f"[YANSHEE]: {fallback_msg}")
                self._tts.speak(fallback_msg)

    # ── Gửi yêu cầu lên Gemini AI ────────────────────────────────────
    def _query_gemini_brain(self, user_speech: str) -> Dict[str, Any]:
        """Gửi prompt phân tích ngữ nghĩa lên Gemini AI."""
        if not self.api_key:
            # Fallback nếu chưa điền API Key: Dùng bộ nhớ từ khóa local
            logger.info("[GEMINI-AI] Chưa có GEMINI_API_KEY, chuyển sang phân tích bộ nhớ từ khóa cục bộ.")
            if self._memory:
                found_motion = self._memory.find_motion(user_speech)
                if found_motion:
                    return {
                        "type": "action",
                        "motion": found_motion,
                        "reply": f"Dạ, em thực hiện hành động {user_speech} ngay đây ạ!"
                    }
            return {
                "type": "chat",
                "motion": None,
                "reply": "Chào bạn! Để bật trí tuệ nhân tạo Gemini đầy đủ, bạn hãy điền GEMINI_API_KEY vào file config.py nhé!"
            }

        prompt = f"""
Bạn là bộ não AI cho robot thông minh Yanshee.
Dưới đây là danh sách tên các hành động chuẩn mà phần cứng Yanshee hỗ trợ:
{ROBOT_MOTIONS}

Người dùng vừa nói câu sau bằng tiếng Việt: "{user_speech}"

Hãy phân tích ngữ nghĩa và trả lời DUY NHẤT theo định dạng JSON chuẩn (không dùng code block markdown, chỉ JSON):
{{
    "type": "action" HOẶC "chat",
    "motion": "Tên_Hành_Động_Trong_Danh_Sách_Hoặc_null",
    "reply": "Câu nói tiếng Việt ngắn gọn, thân thiện (dưới 25 từ) để robot phát âm qua loa"
}}

Quy tắc:
1. Nếu câu nói yêu cầu robot cử động (tiến, lùi, chào, vui mừng, đá bóng, đấm, ôm, đứng thẳng, nhảy,...), đặt type="action", chọn motion khớp nhất, và reply là câu xác nhận dễ thương.
2. Nếu câu nói là câu hỏi, tâm sự, đố vui, giao tiếp, đặt type="chat", motion=null, và reply là câu trả lời ngắn gọn, hóm hỉnh đóng vai robot Yanshee.
"""

        # Cách 1: Thử gọi qua google.genai SDK
        try:
            from google import genai
            client = genai.Client(api_key=self.api_key)
            # Thử qua interactions API
            try:
                interaction = client.interactions.create(
                    model='gemini-2.5-flash',
                    input=prompt
                )
                if interaction.output_text:
                    return self._parse_json_reply(interaction.output_text)
            except Exception:
                # Thử qua model 3.5 hoặc 3.8
                interaction = client.interactions.create(
                    model='gemini-3.5-flash',
                    input=prompt
                )
                if interaction.output_text:
                    return self._parse_json_reply(interaction.output_text)
        except Exception as e:
            logger.debug(f"[GEMINI-AI] SDK call not available or failed: {e}")

        # Cách 2: Fallback trực tiếp qua REST API (Google AI Studio Endpoint)
        try:
            import requests
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={self.api_key}"
            payload = {
                "contents": [{"parts": [{"text": prompt}]}]
            }
            resp = requests.post(url, json=payload, timeout=8)
            if resp.status_code == 200:
                data = resp.json()
                text_out = data["candidates"][0]["content"]["parts"][0]["text"]
                return self._parse_json_reply(text_out)
            else:
                logger.warning(f"[GEMINI-AI] REST API error status {resp.status_code}: {resp.text[:100]}")
        except Exception as rest_err:
            logger.warning(f"[GEMINI-AI] REST API call failed: {rest_err}")

        # Fallback khi cả 2 cách kết nối API bị lỗi mạng/quota
        if self._memory:
            found_motion = self._memory.find_motion(user_speech)
            if found_motion:
                return {
                    "type": "action",
                    "motion": found_motion,
                    "reply": f"Dạ, em thực hiện {user_speech} ạ!"
                }

        return {
            "type": "chat",
            "motion": None,
            "reply": "Xin lỗi bạn, hiện tại mạng đang bận, em chưa nghe rõ câu vừa rồi!"
        }

    @staticmethod
    def _parse_json_reply(text: str) -> Dict[str, Any]:
        """Trích xuất JSON từ phản hồi của Gemini."""
        try:
            # Xóa các markdown code blocks ```json ... ``` nếu có
            clean = re.sub(r'```(?:json)?', '', text, flags=re.IGNORECASE).strip()
            # Tìm block {...} đầu tiên
            match = re.search(r'\{.*\}', clean, re.DOTALL)
            if match:
                data = json.loads(match.group(0))
                return data
        except Exception:
            pass

        # Nếu không parse được JSON, coi toàn bộ text là câu chat trả lời
        return {
            "type": "chat",
            "motion": None,
            "reply": text.strip()
        }
