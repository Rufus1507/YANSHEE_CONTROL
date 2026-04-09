import speech_recognition as sr
import whisper
import torch
import numpy as np
import warnings

# Tắt các cảnh báo không cần thiết của PyTorch/Whisper
warnings.filterwarnings("ignore", category=UserWarning)

def main():
    print("="*60)
    print(" CHƯƠNG TRÌNH NHẬN DIỆN GIỌNG NÓI ĐỘC LẬP (WHISPER AI)")
    print("="*60)

    print("\n[1] Đang tải mô hình AI Whisper... Vui lòng đợi.")
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"    -> Đang chạy trên: {device.upper()}")
    
    # Tải mô hình Whisper bản "base" (phù hợp với máy tính cá nhân nhanh nhạy)
    try:
        model = whisper.load_model("large-v3", device=device)
        print("    -> Tải model thành công!")
    except Exception as e:
        print(f"    -> Lỗi khi tải Whisper: {e}")
        return

    # Cài đặt Micro
    recognizer = sr.Recognizer()
    recognizer.energy_threshold = 400
    recognizer.dynamic_energy_threshold = True

    try:
        microphone = sr.Microphone()
        print("\n[2] Đang kiểm tra Microphone môi trường xung quanh...")
        with microphone as source:
            recognizer.adjust_for_ambient_noise(source, duration=1.0)
        print("    -> Microphone hoàn hảo! Sẵn sàng thu âm.")
    except Exception as e:
        print(f"\n[Lỗi] Không cấu hình được Microphone: {e}")
        return

    print("\n" + "="*60)
    print(" HÃY NÓI VÀO MIC (Bấm Ctrl+C trên bàn phím để tắt)")
    print("="*60)

    while True:
        try:
            with microphone as source:
                print("\n🎤 Đang thu âm (Nói đi bạn)...")
                # timeout=None (nghe mãi mãi tới khi có tiếng), phrase_time=10 (câu nói tối đa 10s)
                audio = recognizer.listen(source, timeout=None, phrase_time_limit=10)

            print("⏳ Đang dịch...")
            
            # Chuyển đổi chuẩn hóa âm thanh sang dạng Float Array cho AI
            wav_bytes = audio.get_raw_data(convert_rate=16000, convert_width=2)
            audio_np = np.frombuffer(wav_bytes, np.int16).flatten().astype(np.float32) / 32768.0

            # Lọc năng lượng, triệt tiêu tạp âm quạt gió (ngăn ảo giác chép sai của Whisper)
            rms = np.sqrt(np.mean(audio_np**2))
            if rms < 0.005:
                continue

            # ==============================================================
            # YÊU CẦU: CHỈ NHẬN TIẾNG VIỆT HOẶC TIẾNG ANH
            # Nếu muốn dùng tiếng Anh, bạn thay đổi thành `language="en"`
            # ==============================================================
            result = model.transcribe(
                audio_np, 
                language="vi",    # Khóa chặt chỉ nghe Tiếng Việt
                fp16=torch.cuda.is_available(),
                condition_on_previous_text=False, # Không cho phép máy tự lặp lại từ cũ sai
                initial_prompt="Đây là câu nói bằng tiếng Việt rõ ràng." 
            )
            
            text = result["text"].strip()
            if text and len(text) > 2:
                print(f"=> [AI nghe được]: {text}")

        except KeyboardInterrupt:
            print("\n[Hệ thống] Đã nhận lệnh thoát chương trình. Tạm biệt!")
            break
        except Exception as e:
            print(f"⚠️ Lỗi hệ thống ngoài ý muốn: {e}")

if __name__ == "__main__":
    main()
