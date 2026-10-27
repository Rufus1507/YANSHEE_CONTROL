"""
YANSHEE MJPEG STREAMER (CHẠY TRÊN ROBOT YANSHEE)

Script này cần được copy và chạy TRÊN Raspberry Pi của Robot Yanshee
để mở luồng stream camera nội bộ ra mạng LAN.

Cách sử dụng:
1. SSH vào robot Yanshee (ví dụ: ssh pi@10.165.178.75)
2. Copy script này vào robot (hoặc tạo file mới trên robot và paste code này vào).
3. Cài đặt thư viện (nếu chưa có): pip install opencv-python Flask
4. Chạy script: python yanshee_mjpeg_streamer.py

Mặc định stream sẽ mở ở: http://<ROBOT_IP>:8000/stream.mjpg
"""

import cv2
import time
import threading
from flask import Flask, Response

app = Flask(__name__)
camera = None
lock = threading.Lock()
current_frame = None

def capture_loop():
    global current_frame, camera
    # Mở camera của Yanshee (thường là /dev/video0 tức index 0)
    camera = cv2.VideoCapture(0)
    camera.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    camera.set(cv2.CAP_PROP_FPS, 30)

    if not camera.isOpened():
        print("Lỗi: Không thể mở camera vật lý trên robot Yanshee!")
        return

    print("Camera Yanshee đã mở thành công. Bắt đầu capture...")
    
    while True:
        success, frame = camera.read()
        if success:
            # Nén thành JPEG để stream
            ret, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
            if ret:
                with lock:
                    current_frame = buffer.tobytes()
        else:
            time.sleep(0.1)

def generate_mjpeg():
    while True:
        with lock:
            frame = current_frame
        if frame is None:
            time.sleep(0.1)
            continue
            
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
        
        # Hạn chế loop quá nhanh
        time.sleep(1/30.0)

@app.route('/stream.mjpg')
def video_feed():
    return Response(generate_mjpeg(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/')
def index():
    return "Yanshee Camera MJPEG Streamer is running. Stream at /stream.mjpg"

if __name__ == '__main__':
    # Khởi động luồng đọc camera ngầm
    t = threading.Thread(target=capture_loop, daemon=True)
    t.start()
    
    # Khởi động web server Flask ở port 8000, lắng nghe mọi IP (0.0.0.0)
    print("Khởi động MJPEG Stream Server tại cổng 8000...")
    app.run(host='0.0.0.0', port=8000, debug=False, threaded=True, use_reloader=False)
