# 🤖 TÀI LIỆU HƯỚNG DẪN TOÀN TẬP HỆ THỐNG ĐIỀU KHIỂN ROBOT YANSHEE AI

Chào mừng bạn đến với dự án **Hệ thống Điều khiển và Tương tác Thông minh cho Robot Yanshee (Yanshee Integrated AI System)**. Tài liệu này cung cấp cái nhìn tổng quan về cách vận hành của toàn bộ hệ thống mã nguồn hiện tại và hướng dẫn chi tiết từng bước để cài đặt, cấu hình và vận hành dự án thành công.

---

## 🌟 PHẦN 1: TỔNG QUAN HỆ THỐNG VÀ CẤU TRÚC MÃ NGUỒN

Hệ thống biến Robot Yanshee thành một **Trợ lý Robot Thông minh**, tích hợp **10+ tính năng nâng cao** chạy đồng thời trên một kiến trúc bất đồng bộ (Asyncio + EventBus + ThreadPoolExecutor):

### 🌟 10+ Tính năng Nổi bật Vận hành Trong Hệ thống:
1. **Nhận diện Khuôn mặt Sinh trắc học (Face Recognition)**: Thuật toán Face Geometry Embedding v2 (kết hợp Pixel, HOG, LBP + Zero-Centering + Cosine Similarity) giúp nhận diện chính xác, kháng khoảng cách (Scale-Invariant) và chống nhận nhầm người lạ.
2. **Chống Giả mạo (Liveness Detection)**: Thử thách ngẫu nhiên (chớp mắt, xoay mặt) để xác thực người thật.
3. **Camera & Stream Network**: Phát trực tiếp luồng MJPEG HD từ camera trên đầu Robot Yanshee qua mạng không dây.
4. **Hàng đợi Hành động Ưu tiên (ActionQueue & Greeting)**: Điều khiển Robot thực hiện cử chỉ/hành động chào mừng phù hợp theo từng vai trò (`Admin`, `Teacher`, `Student`, `Guest`, `Stranger`).
5. **Nhận diện Giọng nói Tiếng Việt (Voice Control)**: Thu âm và xử lý lệnh tiếng Việt qua micro bất đồng bộ không gây hoãn/chặn luồng chính.
6. **Bộ nhớ Thông minh (Smart Memory - `RobotMemory`)**: Quản lý và liên kết động giữa từ khóa giọng nói và các hành động cử chỉ của robot từ file cấu hình `robot_memory.json`.
7. **Phát âm Tiếng Việt (Vietnamese TTS)**: Chuyển đổi văn bản phản hồi thành âm thanh (gTTS) và truyền tự động qua SSH để robot phát tiếng Việt trên loa tích hợp.
8. **Web Dashboard Giám sát Realtime**: Giao diện Web (FastAPI + WebSocket) hiển thị video stream, trạng thái liveness, danh sách nhận diện và biểu đồ hệ thống.
9. **Giám sát Tài nguyên (System Monitor)**: Theo dõi liên tục mức sử dụng CPU, RAM, Disk và lưu lượng mạng của hệ thống.
10. **Hạ tầng Bất đồng bộ (Core Infrastructure)**: Quản lý sự kiện qua `EventBus`, cơ sở dữ liệu SQLite `yanshee_faceid.db`, tự động làm mới cache (Auto-Reload DB Watchdog) và hệ thống ghi log `loguru`.
11. **Nhận diện Cử chỉ Tay/Pose (Gesture Control)**: Tích hợp MediaPipe Hands để nhận diện các tư thế tay và điều khiển robot tương ứng. Có khả năng chuyển đổi qua lại linh hoạt với chế độ nhận diện khuôn mặt ngay trên CLI.

---

### 📂 Cấu trúc Mã nguồn Chi tiết:
- **`main.py`**: Entry point chính chạy toàn bộ hệ thống 10+ tính năng integrated. Chứa vòng lặp CLI tương tác trực tiếp (`1/face`, `2/gesture`, `quit`).
- **`config.py`**: Nơi quản lý tập trung toàn bộ tham số cấu hình (IP Robot, ngưỡng sim 0.88, margin 0.020, required frames 5, cấu hình camera, voice, TTS, DB path...).
- **`requirements.txt`**: Danh sách toàn bộ thư viện Python bắt buộc để vận hành hệ thống.
- **`recognition/`**: Module xử lý nhận diện khuôn mặt (`face_detector.py`, `face_matcher.py`, `pipeline.py`, `register_user.py`).
- **`gesture/`**: Module nhận diện cử chỉ tay (`gesture_bridge.py`, `gesture_recognizer.py`).
- **`voice/`**: Module điều khiển giọng nói & bộ nhớ (`voice_controller.py`, `robot_memory.py`, `tts_engine.py`).
- **`dashboard/`**: Trình quản lý Web Dashboard giao diện giám sát thời gian thực (`app.py`).
- **`camera/`**: Quản lý kết nối & thu thập luồng camera (`camera_manager.py`).
- **`robot/`**: Quản lý kết nối robot và hàng đợi thực thi cử chỉ (`robot_connection.py`, `robot_action_engine.py`).
- **`System/`**: Module tầng thấp giao tiếp với API phần cứng Yanshee (`YanAPI.py`) và giám sát hệ thống (`monitor.py`).
- **`database/` & `data/`**: Quản lý cơ sở dữ liệu SQLite (`yanshee_faceid.db`) và file từ điển bộ nhớ (`robot_memory.json`).
- **`Feature_VietNamese_TTS/`**: Script kiểm tra tính năng Trợ lý AI Gemini (`yanshee_ai.py`).
- **`Feature_Smart_Voice_Memory/`**: Script thử nghiệm độc lập tính năng Voice & Memory.

---

## 💻 PHẦN 2: YÊU CẦU HỆ THỐNG

1. **Phần cứng:**
   - Máy tính (Windows 10/11 hoặc Linux/macOS) có kết nối Microphone.
   - **Robot Yanshee** (đã bật nguồn và kết nối Wi-Fi).
   - Máy tính và Robot Yanshee **bắt buộc kết nối cùng một mạng Wi-Fi (hoặc LAN)**.
2. **Phần mềm:**
   - **Python** (Khuyên dùng bản 3.10 hoặc 3.11).
   - API Key Google Gemini (nếu muốn dùng tính năng trò chuyện AI trong `Feature_VietNamese_TTS/yanshee_ai.py`).

---

## 🛠️ PHẦN 3: HƯỚNG DẪN CÀI ĐẶT (SETUP) CHI TIẾT

### Bước 1: Thiết lập luồng Camera MJPEG trên Robot Yanshee (Chỉ làm 1 lần)
Để robot tự động phát luồng camera stream qua mạng khi bật nguồn:

1. **Kết nối SSH vào robot:**
   ```cmd
   ssh pi@<IP_CỦA_ROBOT>
   ```
   *(Ví dụ IP: `10.165.178.75`. Mật khẩu mặc định: `raspberry` hoặc `pi`).*

2. **Tạo service khởi động Camera Stream:**
   ```bash
   sudo nano /etc/systemd/system/yanshee-camera.service
   ```
   Dán nội dung sau vào file:
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
   Nhấn **Ctrl + O** -> **Enter** -> **Ctrl + X** để lưu và thoát.

3. **Tạo file script python camera streamer:**
   ```bash
   nano /home/pi/yanshee_mjpeg_streamer.py
   ```
   Dán đoạn code sau:
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
   Lưu và thoát (**Ctrl + O** -> **Enter** -> **Ctrl + X**).

4. **Kích hoạt Service:**
   ```bash
   pip install opencv-python Flask
   sudo systemctl daemon-reload
   sudo systemctl enable yanshee-camera
   sudo systemctl start yanshee-camera
   ```

---

### Bước 2: Thiết lập Môi trường trên Máy Tính

1. **Mở Terminal tại thư mục dự án (`YANSHEE_CONTROL-main`) và tạo môi trường ảo:**
   ```cmd
   python -m venv .venv
   ```
2. **Kích hoạt môi trường ảo:**
   - On Windows (CMD/PowerShell):
     ```cmd
     .venv\Scripts\activate
     ```
3. **Cài đặt toàn bộ thư viện cần thiết:**
   ```cmd
   pip install -r requirements.txt
   ```

---

### Bước 3: Cấu hình Hệ thống (`config.py`)

Mở file **`config.py`** và tinh chỉnh các thông số quan trọng:
- `ROBOT_IP = "10.165.178.75"` và `YANSHEE_IP = "10.165.178.75"`: Điền đúng địa chỉ IP thực tế của Robot Yanshee.
- `YANSHEE_CAMERA_ENABLED = True`: Bật thu luồng stream camera từ robot Yanshee.
- `VOICE_ENABLED = True`: Bật/tắt tính năng nhận diện giọng nói tiếng Việt.
- `VN_TTS_ENABLED = True`: Bật/tắt tính năng phát giọng nói tiếng Việt qua SSH robot.

---

## 🚀 PHẦN 4: HƯỚNG DẪN VẬN HÀNH HỆ THỐNG

### 1. Đăng ký Khuôn mặt Người mới (Register User)
Trước khi chạy hệ thống chính, bạn nên đăng ký khuôn mặt để robot nhận diện:
```cmd
python -X utf8 -m recognition.register_user --name "Ten Cua Ban" --role Student
```
*Các quyền (`--role`) hỗ trợ:* `Admin`, `Teacher`, `Student`, `Guest`.

---

### 2. Khởi chạy Hệ thống Tổng hợp Tích hợp (Main System)
Mọi tính năng (Nhận diện khuôn mặt, Liveness, Voice, Memory, TTS, Dashboard, System Monitor, Gesture CLI) đều được tích hợp chung trong `main.py`:

```cmd
python main.py
```

Khi hệ thống khởi động hoàn tất, bạn sẽ thấy giao diện CLI Tương tác trực tiếp:
```text
─"*60
  🎮  BẢNG ĐIỀU KHIỂN YANSHEE AI  (gõ lệnh + Enter)
─"*60
  [1 / face   ]  ▶ ĐANG CHẠY   — Nhận diện Khuôn mặt
  [2 / gesture]    chờ         — Nhận diện Cử chỉ tay
  [quit / exit]               — Dừng toàn bộ hệ thống
─"*60
>>
```

#### 🔄 Điều khiển Chuyển đổi Chế độ On-The-Fly (CLI Commands):
- Gõ **`1`** hoặc **`face`**: Kích hoạt chế độ **Nhận diện Khuôn mặt** (Camera robot).
- Gõ **`2`** hoặc **`gesture`**: Chuyển sang chế độ **Nhận diện Cử chỉ Tay** (Mở camera Gesture).
- Gõ **`quit`** hoặc **`exit`**: Dừng an toàn toàn bộ hệ thống (dừng camera, voice thread, action queue, web server).

---

### 3. Truy cập Web Dashboard Giám sát Realtime
Sau khi chạy `main.py`, hãy mở trình duyệt web và truy cập địa chỉ:
👉 **http://127.0.0.1:8000**

Web Dashboard hiển thị:
- Video Stream realtime từ camera.
- Trạng thái Liveness & thông tin người được nhận diện.
- Biểu đồ tài nguyên CPU, RAM, Disk, Network.
- Danh sách sự kiện & nhật ký log hệ thống.

---

### 4. Chạy Thử nghiệm Trợ lý Ảo AI Trò chuyện (Tùy chọn)
Nếu muốn trò chuyện hỏi đáp kiến thức với AI Gemini qua giọng nói:
1. Điền Gemini API Key vào file `Feature_VietNamese_TTS/yanshee_ai.py`.
2. Chạy file:
   ```cmd
   python Feature_VietNamese_TTS/test_voice_ys.py
   ```

---

## ⚙️ PHẦN 5: BẢNG CẤU HÌNH THAM SỐ LÕI (`config.py`)

| Tham số | Giá trị hiện tại | Ý nghĩa / Chức năng |
| :--- | :--- | :--- |
| `FACE_SIMILARITY_THRESHOLD` | `0.88` | Ngưỡng Cosine similarity xác nhận đúng người. |
| `FACE_SIMILARITY_MARGIN` | `0.020` | Khoảng chênh lệch giữa người đứng top 1 và top 2. |
| `REQUIRED_CONSISTENT_FRAMES` | `5` | Số khung hình liên tiếp cần khớp trước khi đưa ra quyết định nhận diện. |
| `MIN_FACE_SIZE` | `70` | Kích thước khuôn mặt tối thiểu (px) để nhận diện. |
| `MIN_FACE_QUALITY` | `0.75` | Ngưỡng chất lượng ảnh tối thiểu (loại ảnh mờ/nhiễu). |
| `MIN_BLUR_THRESHOLD` | `80.0` | Ngưỡng kiểm tra độ nét của ảnh mặt. |
| `YANSHEE_CAMERA_ENABLED` | `True` | Bật/tắt luồng camera MJPEG từ robot. |
| `VOICE_ENABLED` | `True` | Bật/tắt thu âm và nhận diện giọng nói tiếng Việt. |
| `VN_TTS_ENABLED` | `True` | Bật/tắt phát âm thanh tiếng Việt qua SSH robot. |
| `GESTURE_CAMERA_INDEX` | `1` | Index camera dùng cho nhận diện cử chỉ (Gesture). |

---

## 🔧 PHẦN 6: XỬ LÝ SỰ CỐ (TROUBLESHOOTING)

1. **Lỗi `ModuleNotFoundError`?**
   👉 Đảm bảo bạn đã kích hoạt môi trường ảo `.venv` và đã chạy `pip install -r requirements.txt`.
2. **Camera Yanshee không stream được hoặc báo lỗi kết nối?**
   👉 Kiểm tra lại địa chỉ IP robot trong `config.py`. Đảm bảo service `yanshee-camera` trên robot đang chạy và máy tính cùng mạng Wi-Fi với robot.
3. **Microphone không thu âm được?**
   👉 Đảm bảo micro máy tính đang bật và cấp quyền ứng dụng truy cập micro trong Settings > Privacy > Microphone của Windows.
4. **Robot nhận diện đúng người trên màn hình nhưng không phát tiếng / không cử động?**
   👉 Kiểm tra `ROBOT_ENABLED = True` và `VN_TTS_ENABLED = True` trong `config.py`. Kiểm tra SSH password/user (`pi` / `raspberry`).

---
*Chúc bạn vận hành thành công Hệ thống Robot Yanshee AI!*
