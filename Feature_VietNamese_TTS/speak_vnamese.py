#text to speech
import os
import sys
import paramiko
from gtts import gTTS

# CẤU HÌNH YANSHEE
ROBOT_IP = "192.168.137.6"
ROBOT_USER = "pi"
ROBOT_PASS = "raspberry"

def ep_yanshee_noi(text_input):
    print(f"\n[ĐANG XỬ LÝ]: Tạo giọng nói tiếng Việt cho câu: '{text_input}'...")
    
    try:
        # BƯỚC 1: Dùng gTTS tạo file MP3 giọng chuẩn Việt (Miễn phí, KHÔNG CẦN KEY)
        audio_file = "giong_chuan.mp3"
        tts = gTTS(text=text_input, lang='vi', slow=False)
        tts.save(audio_file)
        print("[HỆ THỐNG] Đã tạo xong file MP3 giọng chị Google.")

        # BƯỚC 2: Kết nối thẳng vào Yanshee
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(ROBOT_IP, username=ROBOT_USER, password=ROBOT_PASS, timeout=5)
        
        # BƯỚC 3: Quăng file MP3 sang robot
        ftp = ssh.open_sftp()
        ftp.put(audio_file, f"/home/{ROBOT_USER}/{audio_file}")
        ftp.close()

        # BƯỚC 4: Ép loa Yanshee mở file MP3 lên
        print("[HỆ THỐNG] Đang truyền lệnh cho Yanshee phát loa...")
        stdin, stdout, stderr = ssh.exec_command(f"mpg123 /home/{ROBOT_USER}/{audio_file}")
        stdout.channel.recv_exit_status() # Đợi đọc xong

        ssh.close()
        print("[THÀNH CÔNG] Yanshee đã đọc xong câu của bà!")
        
    except Exception as e:
        print(f"[LỖI MẠNG HOẶC KẾT NỐI ROBOT]: {e}")
        print("💡 Nếu lỗi, hãy chắc chắn laptop và Yanshee đang cùng kết nối chung một mạng Wi-Fi.")

# FIX LỖI FONT CHỮ WINDOWS TERMINAL
sys.stdin.reconfigure(encoding='utf-8')
sys.stdout.reconfigure(encoding='utf-8')

if __name__ == "__main__":
    print("=== HỆ THỐNG ÉP YANSHEE NÓI TIẾNG VIỆT CHUẨN (KHÔNG API) ===")
    while True:
        cau_noi = input("\nNhập bất kỳ câu gì bà muốn Yanshee nói (hoặc gõ 'thoát'): ")
        if cau_noi.lower() == 'thoát':
            break
        
        # Yêu cầu phải có chữ mới chạy
        if cau_noi.strip() != "":
            ep_yanshee_noi(cau_noi)