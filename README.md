# Yanshee AI Face Recognition Smart Greeting System

Hệ thống nhận diện khuôn mặt và chào hỏi tự động sử dụng luồng video (MJPEG) từ camera vật lý tích hợp trên Robot Yanshee, thay thế hoàn toàn webcam laptop truyền thống.

## Tính năng Nổi bật
- **Nhận diện khuôn mặt Không Dùng AI Model**: Hoàn toàn tuân thủ yêu cầu không cài đặt bất kỳ mô hình AI nhận diện nào (InsightFace, ArcFace, FaceNet). Sử dụng thuật toán sinh trắc học **Face Geometry Embedding** dựa trên toán học thuần túy: tính toán tỷ lệ, khoảng cách, và góc giữa 478 điểm lưới khuôn mặt (Face Mesh landmarks).
- **Kháng khoảng cách (Scale-Invariant)**: Nhờ sử dụng tỷ lệ hình học thay vì so sánh điểm ảnh (Pixel/HOG), hệ thống tự động nhận diện chính xác kể cả khi người dùng đứng gần hay lùi ra xa camera.
- **Tự động Căn chỉnh Khuôn mặt (Alignment)**: Sử dụng MediaPipe Face Mesh tích hợp sẵn để định vị mắt, xoay và căn chỉnh ảnh.
- **Kiểm tra Chất lượng (Quality Check)**: Tự động từ chối khuôn mặt quá mờ, quá tối, hoặc không nằm giữa khung hình khi đăng ký.
- **Đăng ký 2 Pha (Gần & Xa)**: Quy trình đăng ký thông minh yêu cầu chụp cả khuôn mặt khi đứng gần (7 ảnh) và khi lui ra xa 1.5-2m (3 ảnh) để tạo dữ liệu sinh trắc phong phú. Chống lặp dữ liệu tự động.
- **Xử lý Bất đồng bộ Hiệu suất cao**: Pipeline nhận diện không chặn (non-blocking) qua `ThreadPoolExecutor` kết hợp throttle FPS, đảm bảo Stream Camera/Dashboard luôn mượt mà. 
- Hệ thống Event Bus thread-safe.
- Dashboard giám sát thời gian thực bằng FastAPI & WebSocket.
- Kết nối tự động với Robot Yanshee qua Wi-Fi để thực hiện action/TTS. Fallback TTS offline (pyttsx3) nếu không có Robot.

## Yêu cầu Hệ thống
- Windows 10/11
- Python 3.10 hoặc 3.11
- **Robot Yanshee** (đã bật nguồn, kết nối chung mạng LAN/Wi-Fi với máy tính).
- (Tùy chọn) Webcam/Camera laptop nếu sử dụng cấu hình legacy.

## Hướng dẫn Cài đặt & Khởi chạy

Hệ thống hoạt động theo mô hình **Client-Server**: Robot Yanshee đóng vai trò là Server phát (broadcast) camera stream, còn máy tính (Laptop/PC) đóng vai trò là Client nhận stream và xử lý nhận diện AI.

---

### PHẦN 1: Cài đặt trên Robot Yanshee (Chỉ làm 1 lần)
Bạn cần cài đặt một đoạn script nhỏ (service) lên robot để robot tự động mở camera stream mỗi khi bật nguồn.

**1. Mở Terminal (CMD) trên máy tính và SSH vào robot:**
```cmd
ssh pi@<ROBOT_IP>
```
*(Thay `<ROBOT_IP>` bằng IP của robot, ví dụ `10.165.178.75`. Mật khẩu mặc định thường là `raspberry` hoặc `pi`. Lưu ý: Khi gõ mật khẩu sẽ không hiện dấu `*`, bạn cứ gõ bình thường và nhấn Enter).*

**2. Tạo service khởi động Camera Stream:**
Gõ lệnh sau vào cửa sổ SSH và nhấn Enter để mở trình soạn thảo:
```bash
sudo nano /etc/systemd/system/yanshee-camera.service
```
Copy đoạn code dưới đây và dán (chuột phải) vào cửa sổ SSH:
```ini
[Unit]
Description=Yanshee MJPEG Camera Streamer
After=network.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi
ExecStart=/usr/bin/python3 /home/pi/yanshee_mjpeg_streamer.py
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
```
Nhấn **Ctrl + O**, sau đó nhấn **Enter** để lưu file. Cuối cùng nhấn **Ctrl + X** để thoát.

**3. Tạo file script Camera Stream:**
Tiếp tục gõ lệnh sau để tạo file code Python:
```bash
nano /home/pi/yanshee_mjpeg_streamer.py
```
Copy đoạn code dưới đây và dán vào cửa sổ SSH:
```python
import cv2, time, threading
from flask import Flask, Response

app = Flask(__name__)
camera = None
lock = threading.Lock()
current_frame = None

def capture_loop():
    global current_frame, camera
    camera = cv2.VideoCapture(0)
    camera.set(3, 640)
    camera.set(4, 480)
    camera.set(5, 30)
    while True:
        success, frame = camera.read()
        if success:
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
        yield (b'--frame\r\n' b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
        time.sleep(1/30.0)

@app.route('/stream.mjpg')
def video_feed():
    return Response(generate_mjpeg(), mimetype='multipart/x-mixed-replace; boundary=frame')

if __name__ == '__main__':
    threading.Thread(target=capture_loop, daemon=True).start()
    app.run(host='0.0.0.0', port=8000, debug=False, threaded=True, use_reloader=False)
```
Tương tự, nhấn **Ctrl + O** -> **Enter** -> **Ctrl + X** để lưu và thoát.

**4. Kích hoạt Service:**
Cuối cùng, chạy các lệnh này để cài đặt thư viện và cho phép service tự khởi động:
```bash
pip install opencv-python Flask
sudo systemctl daemon-reload
sudo systemctl enable yanshee-camera
sudo systemctl start yanshee-camera
echo "XONG! Camera stream da san sang."
```
*(Từ nay về sau, cứ bật nguồn robot là camera sẽ tự động phát sóng. Bạn có thể đóng cửa sổ SSH lại).*

---

### PHẦN 2: Chạy hệ thống trên Máy tính (Laptop/PC)

**1. Tạo & Kích hoạt môi trường ảo (venv)**
```cmd
python -m venv .venv
.venv\Scripts\activate
```

**2. Cài đặt thư viện**
```cmd
pip install -r requirements.txt
```

**3. Cấu hình IP (Quan trọng)**
Mở file `config.py` bằng trình soạn thảo và sửa biến `ROBOT_IP` cùng `YANSHEE_IP` thành địa chỉ IP thực tế của robot Yanshee của bạn.

**4. Đăng ký người dùng**
Để hệ thống nhận diện và chào đúng tên, bạn cần đăng ký khuôn mặt. Tránh đăng ký ngược sáng hoặc bị nhòe.
```cmd
python -X utf8 -m recognition.register_user --name "Nguyen Van A" --role Student
```
> **Lưu ý về các Role (Vai trò):** Tham số `--role` xác định chức danh của người dùng để kịch bản robot chào hỏi phù hợp. Các role có sẵn:
> `Admin` (Quản trị viên) | `Teacher` (Giáo viên) | `Student` (Học sinh) | `Guest` (Khách mời)

> **Quy trình đăng ký tự động 2 PHA:**
> - **Pha 1 (Đứng gần - 7 ảnh)**: Đứng cách robot 0.5-1m, quay mặt từ từ sang trái, phải, lên, xuống.
> - **Pha 2 (Đứng xa - 3 ảnh)**: Khi có thông báo hiện lên trên màn hình, hãy lui ra xa khoảng 1.5-2m và nhìn thẳng camera. Việc này rất quan trọng để hệ thống nhận diện chính xác khi bạn đứng xa.

**5. Chạy hệ thống chính**
```cmd
python main.py
```

**6. Mở Dashboard giám sát**
Vào trình duyệt và truy cập:
**http://127.0.0.1:8000**

## Cấu hình Nâng cao (config.py)
Bạn có thể tinh chỉnh thuật toán trong `config.py`:
- `FACE_SIMILARITY_THRESHOLD = 0.88`: Ngưỡng quyết định "đúng người" cho thuật toán Face Geometry. Hạ xuống (ví dụ 0.85) nếu khó nhận diện, tăng lên (ví dụ 0.90) nếu sợ bị nhận nhầm người khác.
- `FACE_SIMILARITY_MARGIN = 0.020`: Khoảng cách bắt buộc giữa người giống nhất và người giống nhì để đảm bảo tính an toàn.
- `REQUIRED_CONSISTENT_FRAMES = 2`: Số khung hình liên tiếp cần nhận diện giống nhau để đưa ra kết quả cuối cùng (giúp phản hồi siêu nhanh).
- `PIPELINE_PROCESS_MAX_FPS = 15`: Giới hạn FPS xử lý nhận diện để không gây quá tải CPU (tránh đơ lag UI).
- `YANSHEE_CAMERA_ENABLED = True`: Bật sử dụng luồng mạng MJPEG từ camera của robot Yanshee. Nếu đặt `False`, hệ thống sẽ quay về dùng webcam máy tính.
- `YANSHEE_IP`: Địa chỉ IP của robot (thường đặt trùng với `ROBOT_IP`).
- `MAX_FRAME_QUEUE = 2`: Giới hạn hàng đợi khung hình giúp duy trì độ trễ cực thấp, chống đọng frame (backlog) khi mạng chập chờn.
- `ROBOT_ENABLED = True / False`: Bật/tắt việc gọi action/TTS tới robot Yanshee.
- `ROBOT_IP`: Thay đổi địa chỉ IP của robot.
- `ROBOT_RESET_DELAY`: Thời gian (giây) chờ sau khi robot chào xong trước khi thực hiện reset / trở về vị trí "Reset".
- `BLINK_REQUIRED_COUNT`: Số lần chớp mắt tối thiểu cần cho thử thách "blink" trong liveness.
- `LIVENESS_TIMEOUT`: Thời gian tối đa (giây) cho một phiên liveness trước khi bị đánh dấu thất bại.
## Xử lý sự cố
- **Không kết nối được Camera Yanshee**: Kiểm tra lại `YANSHEE_IP` trong `config.py`. Đảm bảo máy tính và robot cùng chung một mạng Wi-Fi. Bạn có thể dùng lệnh `python -m tools.test_yanshee_camera` để chẩn đoán xem luồng MJPEG có đang hoạt động hay không.
- **Robot không nói hoặc không chuyển động**: Kiểm tra lại `ROBOT_IP` trong `config.py` và đảm bảo kết nối mạng giữa máy tính và robot ổn định.
- **Hệ thống cảnh báo "Move closer" hoặc "Too dark" liên tục khi đăng ký**: Kiểm tra ánh sáng phòng và nhìn thẳng vào camera, đảm bảo khuôn mặt chiếm tỷ lệ lớn trong khung hình.
- **Xung đột Camera với App điện thoại**: Camera của Raspberry Pi chỉ cho phép 1 luồng truy cập. Khi Service chạy ngầm, bạn sẽ không thể xem camera trên App Yanshee. Để nhường lại camera cho App, hãy SSH vào robot và gõ: `sudo systemctl stop yanshee-camera`. Khi muốn dùng lại AI thì gõ `sudo systemctl start yanshee-camera`.
