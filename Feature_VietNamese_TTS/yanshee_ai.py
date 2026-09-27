#speech to speech with API key, để chạy: 
# .\.venv\Scripts\python.exe yanshee_ai.py
import os
import sys
import paramiko
import speech_recognition as sr
from gtts import gTTS
from google import genai

# 1. CAU HINH BO NAO AI (DIEN MA VAO)
GEMINI_API_KEY = "DUNG_API_KEY"
client = genai.Client(api_key=GEMINI_API_KEY)

# 2. CAU HINH ROBOT YANSHEE
ROBOT_IP = "192.168.137.6"
ROBOT_USER = "pi"
ROBOT_PASS = "raspberry"

def suy_nghi_va_tra_loi(cau_hoi):
    try:
        print("[YANSHEE ĐANG NGHĨ]...")
        # Ép AI đóng vai Yanshee để trả lời nhập tâm hơn
        prompt = f"Bạn là một robot tên là Yanshee. Hãy trả lời câu hỏi sau một cách ngắn gọn, thân thiện bằng tiếng Việt: {cau_hoi}"
        
        interaction = client.interactions.create(
            model='gemini-3.5-flash', 
            input=prompt
        )
        
        # ĐÃ SỬA LỖI: Rút thẳng câu trả lời từ output_text
        if interaction.output_text:
            ai_text = interaction.output_text.strip()
        else:
            ai_text = "Hãy hỏi lại câu khác."
            
        print(f"[YANSHEE TRẢ LỜI]: {ai_text}")
        return ai_text
        
    except Exception as e:
        print(f"[LỖI NÃO AI]: {e}")
        return "Xin lỗi, tôi đang bị lỗi kết nối mạng."

def ep_yanshee_noi(text_input):
    try:
        audio_file = "phan_hoi.mp3"
        tts = gTTS(text=text_input, lang='vi', slow=False)
        tts.save(audio_file)

        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(ROBOT_IP, username=ROBOT_USER, password=ROBOT_PASS, timeout=5)
        
        ftp = ssh.open_sftp()
        ftp.put(audio_file, f"/home/{ROBOT_USER}/{audio_file}")
        ftp.close()

        stdin, stdout, stderr = ssh.exec_command(f"mpg123 /home/{ROBOT_USER}/{audio_file}")
        stdout.channel.recv_exit_status() 

        ssh.close()
    except Exception as e:
        print(f"[LỖI KẾT NỐI ROBOT]: {e}")

# FIX LỖI HIỂN THỊ TERMINAL
sys.stdin.reconfigure(encoding='utf-8')
sys.stdout.reconfigure(encoding='utf-8')

if __name__ == "__main__":
    recognizer = sr.Recognizer()
    print("=== HỆ THỐNG YANSHEE AI ĐÃ KHỞI ĐỘNG ===")
    
    with sr.Microphone() as source:
        print("Đang khử ồn môi trường, vui lòng đợi 2 giây...")
        recognizer.adjust_for_ambient_noise(source, duration=2)
        print("Sẵn sàng!hãy nói vào Micro của Laptop đi...")
        
        while True:
            try:
                print("\n[BÀ]: (Đang nghe...)")
                audio = recognizer.listen(source, timeout=5, phrase_time_limit=10)
                
                # Dịch giọng nói thành chữ
                cau_hoi = recognizer.recognize_google(audio, language="vi-VN")
                print(f"[BẠN NÓI]: {cau_hoi}")
                
                if "tạm biệt" in cau_hoi.lower() or "thoát" in cau_hoi.lower():
                    ep_yanshee_noi("Tạm biệt bạn nha!")
                    break
                
                # Đưa câu hỏi cho AI xử lý
                cau_tra_loi = suy_nghi_va_tra_loi(cau_hoi)
                
                # Ép Yanshee phát âm
                ep_yanshee_noi(cau_tra_loi)
                
            except sr.WaitTimeoutError:
                pass # Bỏ qua nếu không nghe thấy ai nói gì
            except sr.UnknownValueError:
                print("[HỆ THỐNG] Nghe không rõ, bạn nói lại đi!")
            except sr.RequestError:
                print("[HỆ THỐNG] Mất kết nối Internet khi nhận diện giọng nói.")
