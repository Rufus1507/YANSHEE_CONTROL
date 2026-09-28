# 🤖 TÀI LIỆU HƯỚNG DẪN TOÀN TẬP HỆ THỐNG ĐIỀU KHIỂN ROBOT YANSHEE

Chào mừng bạn đến với dự án **Hệ thống Điều khiển và Tương tác Thông minh cho Robot Yanshee**. Tài liệu này cung cấp cái nhìn tổng quan về cách hoạt động của toàn bộ mã nguồn (code) và hướng dẫn chi tiết từng bước (step-by-step) để bất kỳ ai nhận được source code này cũng có thể tự cài đặt và chạy thành công.

---

## 🌟 PHẦN 1: TỔNG QUAN VỀ HỆ THỐNG VÀ FILE CODE

Hệ thống biến Robot Yanshee từ một robot vật lý cơ bản thành một **Trợ lý thông minh**, có khả năng nhìn (nhận diện khuôn mặt), nghe (nhận diện giọng nói tiếng Việt), suy nghĩ (tích hợp AI Gemini) và nói (Text-to-Speech).

### 🌟 Tính năng Nổi bật (Hệ thống Nhận diện Khuôn mặt):
- **Nhận diện khuôn mặt Không Dùng AI Model**: Sử dụng thuật toán sinh trắc học **Face Geometry Embedding** dựa trên toán học thuần túy: tính toán tỷ lệ, khoảng cách, và góc giữa 478 điểm lưới khuôn mặt (Face Mesh landmarks).
- **Kháng khoảng cách (Scale-Invariant)**: Nhờ sử dụng tỷ lệ hình học thay vì so sánh điểm ảnh (Pixel/HOG), hệ thống tự động nhận diện chính xác kể cả khi người dùng đứng gần hay lùi ra xa camera.
- **Tự động Căn chỉnh Khuôn mặt (Alignment)**: Sử dụng MediaPipe Face Mesh tích hợp sẵn để định vị mắt, xoay và căn chỉnh ảnh.
- **Kiểm tra Chất lượng (Quality Check)**: Tự động từ chối khuôn mặt quá mờ, quá tối, hoặc không nằm giữa khung hình khi đăng ký.
- **Đăng ký 2 Pha (Gần & Xa)**: Quy trình đăng ký thông minh yêu cầu chụp cả khuôn mặt khi đứng gần (7 ảnh) và khi lui ra xa 1.5-2m (3 ảnh) để tạo dữ liệu sinh trắc phong phú.
- **Xử lý Bất đồng bộ Hiệu suất cao**: Pipeline nhận diện không chặn (non-blocking) qua `ThreadPoolExecutor` đảm bảo Stream Camera/Dashboard luôn mượt mà. 

### Cấu trúc mã nguồn chính:
- **`main.py`**: File khởi chạy chính cho **Hệ thống Nhận diện Khuôn mặt** và khởi tạo Web Dashboard giám sát hệ thống. 
- **Thư mục `System/`**: Đóng vai trò là "bộ não" cục bộ, chứa các file cốt lõi (như `YanAPI.py`, `cam_control.py`, `main_control.py`) để giao tiếp trực tiếp với phần cứng robot.
- **Thư mục `Feature_VietNamese_TTS/`**: Chứa code tính năng **Trợ lý Ảo AI** (tích hợp Google Gemini và Text-to-Speech) giúp robot giao tiếp và trả lời câu hỏi bằng tiếng Việt một cách thông minh và tự nhiên.
- **Thư mục `Feature_Smart_Voice_Memory/`**: Chứa code tính năng **Điều khiển bằng giọng nói**, quản lý trạng thái động qua file từ điển `robot_memory.json` (không dùng if/else cứng nhắc) giúp ra lệnh điều hướng mượt mà.
- **`config.py`**: Nơi chứa toàn bộ các thông số cài đặt lõi của hệ thống (Địa chỉ IP robot, cấu hình nhận diện camera, API key, ngưỡng similarity...).
- **`requirements.txt`**: Danh sách các thư viện Python (dependencies) bắt buộc phải cài đặt để chạy được mã nguồn.

---

## 💻 PHẦN 2: YÊU CẦU HỆ THỐNG

Để chạy được dự án một cách trơn tru, bạn cần chuẩn bị:
1. **Phần cứng:** 
   - Máy tính (Khuyên dùng Windows 10/11) có kết nối micro hoạt động tốt.
   - **Robot Yanshee** (đã bật nguồn và sẵn sàng).
   - Máy tính và Robot bắt buộc phải kết nối **cùng một mạng Wi-Fi (hoặc mạng LAN)**.
2. **Phần mềm:**
   - **Python** (Yêu cầu phiên bản từ 3.10 hoặc 3.11).
   - API Key của **Google Gemini** (Để sử dụng tính năng AI trò chuyện).

---

## 🛠️ PHẦN 3: HƯỚNG DẪN CÀI ĐẶT (SETUP) CHI TIẾT

Vui lòng làm theo đúng thứ tự các bước dưới đây để thiết lập môi trường hoàn chỉnh.

### Bước 1: Thiết lập luồng Camera trên Robot Yanshee (Chỉ làm 1 lần duy nhất)
Bạn cần cài đặt một đoạn script nhỏ (service) lên robot để robot tự động mở camera stream (phát video qua mạng) mỗi khi bật nguồn.

**1. Mở Terminal (CMD/PowerShell) trên máy tính và kết nối SSH vào robot:**
```cmd
ssh pi@<IP_CỦA_ROBOT>
```
*(Thay `<IP_CỦA_ROBOT>` bằng IP của robot, ví dụ `10.165.178.75`. Mật khẩu mặc định là `raspberry` hoặc `pi`. Khi gõ mật khẩu sẽ không hiện dấu `*`, bạn cứ gõ bình thường và nhấn Enter).*

**2. Tạo service khởi động Camera Stream:**
Gõ lệnh sau vào cửa sổ SSH và nhấn Enter để mở trình soạn thảo nano:
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

**3. Tạo file script Camera Stream bằng Python:**
Tiếp tục gõ lệnh sau để tạo file mã nguồn:
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
Cuối cùng, chạy lần lượt các lệnh này để cài đặt thư viện và cho phép service tự khởi động cùng robot:
```bash
pip install opencv-python Flask
sudo systemctl daemon-reload
sudo systemctl enable yanshee-camera
sudo systemctl start yanshee-camera
echo "XONG! Camera stream da san sang."
```
*(Từ nay về sau, cứ bật nguồn robot là camera sẽ tự động phát sóng. Bạn có thể đóng cửa sổ SSH lại).*

### Bước 2: Thiết lập môi trường trên Máy Tính (Laptop/PC)
Mở CMD (Command Prompt) hoặc Terminal **ngay tại thư mục chứa source code** (thư mục `YANSHEE_CONTROL-main`) và chạy lần lượt các lệnh:

1. **Tạo môi trường ảo (Khuyên dùng để tránh xung đột thư viện):**
   ```cmd
   python -m venv .venv
   ```
2. **Kích hoạt môi trường ảo:**
   ```cmd
   .venv\Scripts\activate
   ```
   *(Nếu kích hoạt thành công, bạn sẽ thấy chữ `(.venv)` xuất hiện ở đầu dòng lệnh).*
3. **Cài đặt toàn bộ thư viện cần thiết:**
   ```cmd
   pip install -r requirements.txt
   ```
   *(Lưu ý: Quá trình tải các thư viện AI như MediaPipe, FastAPI và xử lý ảnh sẽ mất vài phút).*

### Bước 3: Cấu hình hệ thống (RẤT QUAN TRỌNG)
1. **Cấu hình IP Robot:**
   - Dùng trình soạn thảo (như VSCode hoặc Notepad) mở file **`config.py`**.
   - Tìm dòng `ROBOT_IP` và `YANSHEE_IP`. Sửa giá trị này thành địa chỉ IP thực tế của robot (VD: `'10.165.178.75'`).
   - Kiểm tra và sửa đổi tương tự cho biến lưu IP trong các file tính năng lẻ như: `Feature_VietNamese_TTS/test_voice_ys.py` và `Feature_Smart_Voice_Memory/main_control2.py` (nếu có yêu cầu).
2. **Cấu hình API Key AI (Dành riêng cho trợ lý ảo trò chuyện):**
   - Mở file **`Feature_VietNamese_TTS/yanshee_ai.py`**.
   - Tìm biến `GEMINI_API_KEY = ""` và điền API Key Google Gemini của bạn vào giữa 2 dấu ngoặc kép. *(Không chia sẻ key này ra ngoài)*.

---

## 🚀 PHẦN 4: HƯỚNG DẪN SỬ DỤNG (CHẠY HỆ THỐNG)

Hệ thống được chia làm 3 module chức năng độc lập. Bạn muốn dùng chức năng nào thì mở CMD, **đảm bảo đã kích hoạt môi trường ảo `(.venv)`**, đứng tại thư mục gốc và chạy file của chức năng đó.

### Chức năng 1: Nhận diện khuôn mặt thông minh & Dashboard Web
Chức năng này dùng camera của robot để phát hiện người đã lưu và tự động chào hỏi bằng giọng nói/hành động tương ứng.

**A. Đăng ký khuôn mặt người mới:**
*(Hãy đứng ở nơi đủ sáng, tránh ngược sáng, làm theo hướng dẫn trên màn hình: Chụp 7 ảnh khi đứng gần và 3 ảnh khi lùi ra xa)*
```cmd
python -X utf8 -m recognition.register_user --name "Ten Cua Ban" --role Student
```
*(Tham số `--role` hỗ trợ các quyền: `Admin`, `Teacher`, `Student`, `Guest`)*

**B. Chạy hệ thống nhận diện chính:**
```cmd
python main.py
```
**C. Theo dõi qua Dashboard giám sát thời gian thực:**
Khi hệ thống chạy `main.py` thành công, hãy mở trình duyệt web (Chrome/Edge/Safari) trên máy tính và truy cập vào địa chỉ: 
👉 **http://127.0.0.1:8000**

---

### Chức năng 2: Trợ lý Ảo AI Tiếng Việt (Giao tiếp tự nhiên)
Cho phép bạn nói chuyện, hỏi đáp kiến thức với robot như một người bạn thực sự. (Sử dụng Google Gemini + Text-to-Speech).
```cmd
python Feature_VietNamese_TTS/test_voice_ys.py
```
*Cách dùng: Sau khi file chạy, hãy nói vào micro của máy tính. Hệ thống sẽ gửi câu hỏi cho AI xử lý, và câu trả lời Tiếng Việt sẽ được phát ra trực tiếp trên loa của robot.*

---

### Chức năng 3: Điều khiển Robot bằng Giọng nói (Smart Memory)
Cho phép bạn ra lệnh bằng tiếng Việt (Ví dụ: "tiến lên", "lùi lại", "tập thể dục", "đá bóng",...) để robot làm theo.
```cmd
python Feature_Smart_Voice_Memory/main_control2.py
```
*Cách dùng: Đọc rõ lệnh vào micro. Hệ thống sẽ chuyển thành văn bản, tự động dò tìm độ khớp trong file `robot_memory.json` và kích hoạt luồng hành động chuẩn xác.*

---

## ⚙️ PHẦN 5: CẤU HÌNH NÂNG CAO (`config.py`)

Bạn có thể tinh chỉnh thuật toán và hệ thống trong file `config.py` để đạt hiệu suất tốt nhất:
- `FACE_SIMILARITY_THRESHOLD = 0.88`: Ngưỡng quyết định "đúng người" cho thuật toán Face Geometry. Hạ xuống (ví dụ 0.85) nếu khó nhận diện, tăng lên (ví dụ 0.90) nếu sợ bị nhận nhầm người khác.
- `FACE_SIMILARITY_MARGIN = 0.020`: Khoảng cách bắt buộc giữa người giống nhất và người giống nhì để đảm bảo tính an toàn.
- `REQUIRED_CONSISTENT_FRAMES = 2`: Số khung hình liên tiếp cần nhận diện giống nhau để đưa ra kết quả cuối cùng (giúp phản hồi siêu nhanh).
- `PIPELINE_PROCESS_MAX_FPS = 15`: Giới hạn FPS xử lý nhận diện để không gây quá tải CPU (tránh đơ lag UI).
- `YANSHEE_CAMERA_ENABLED = True`: Bật sử dụng luồng mạng MJPEG từ camera của robot Yanshee. Nếu đặt `False`, hệ thống sẽ quay về dùng webcam máy tính.
- `MAX_FRAME_QUEUE = 2`: Giới hạn hàng đợi khung hình giúp duy trì độ trễ cực thấp, chống đọng frame (backlog) khi mạng chập chờn.
- `ROBOT_ENABLED = True / False`: Bật/tắt việc gọi action/TTS tới robot Yanshee.
- `ROBOT_RESET_DELAY`: Thời gian (giây) chờ sau khi robot chào xong trước khi thực hiện reset / trở về vị trí "Reset".
- `BLINK_REQUIRED_COUNT`: Số lần chớp mắt tối thiểu cần cho thử thách "blink" trong Liveness Detection.
- `LIVENESS_TIMEOUT`: Thời gian tối đa (giây) cho một phiên liveness trước khi bị đánh dấu thất bại.

---

## 🔧 PHẦN 6: XỬ LÝ SỰ CỐ THƯỜNG GẶP (TROUBLESHOOTING)

1. **Lỗi `ModuleNotFoundError` khi chạy file Python?**
   👉 Nguyên nhân: Bạn chưa kích hoạt môi trường ảo `.venv` ở phiên làm việc hiện tại, hoặc chưa chạy lệnh `pip install -r requirements.txt`.
2. **Camera Yanshee không nhận diện được / Báo lỗi kết nối mạng?**
   👉 Kiểm tra lại chính xác địa chỉ IP của Yanshee trong file `config.py`. Chắc chắn rằng robot và máy tính đang cùng kết nối chung một mạng Wi-Fi. 
   👉 **Lưu ý quan trọng**: Khi luồng camera AI đang bật, bạn sẽ không thể mở camera từ App điện thoại Yanshee để xem đồng thời (do camera phần cứng bị chiếm dụng luồng).
3. **Lỗi `Microphone not found` hoặc lỗi thư viện `PyAudio`?**
   👉 Đảm bảo máy tính có micro. Nếu bạn dùng Windows, hãy vào **Settings > Privacy > Microphone** và cấp quyền cho phép các ứng dụng Desktop (bao gồm Terminal/Python) truy cập vào micro.
4. **Lỗi `APIError` hoặc `401/403` khi chạy tính năng AI trò chuyện?**
   👉 API Key của Google Gemini không hợp lệ, đã hết hạn hoặc chưa được nhập vào file `yanshee_ai.py`. Vui lòng tạo API Key mới từ Google AI Studio.
5. **Khuôn mặt được nhận diện thành công trên màn hình nhưng Robot không phản ứng (không nói, không cử động)?**
   👉 Kiểm tra biến `ROBOT_ENABLED = True` trong file `config.py`. Đồng thời kiểm tra lại kết nối mạng (Ping thử IP robot), nếu mạng chập chờn sẽ khiến tín hiệu gửi lệnh tới robot bị gián đoạn.

---
*Chúc bạn có những trải nghiệm tuyệt vời và phát triển thành công dự án cùng Robot Yanshee!*
