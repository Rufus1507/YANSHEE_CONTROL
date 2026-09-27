# TÀI LIỆU TỔNG HỢP CHỨC NĂNG HỆ THỐNG ROBOT YANSHEE VÀ CÁCH SET UP MÔI TRƯỜNG, CHẠY ĐƯỢC YANSHEE
*(Bao gồm Nền tảng gốc và Các module cải tiến toàn diện)*

## PHẦN 1: TỔNG QUAN CHỨC NĂNG MẶC ĐỊNH CỦA YANSHEE (NỀN TẢNG CƠ SỞ)
Robot Yanshee sở hữu hệ thống phần cứng mạnh mẽ cùng kho hành động đa dạng được tích hợp sẵn, hỗ trợ điều khiển qua ứng dụng điện thoại hoặc giao tiếp qua API hệ thống.

**1. Nền tảng Hệ thống & Giao tiếp:**
*   **Phần cứng:** Hoạt động trên bo mạch Raspberry Pi, tích hợp hệ thống 17 khớp nối Servo (Degrees of Freedom) cho phép thực hiện các chuyển động linh hoạt.
*   **Điều khiển cơ bản:** Có thể điều khiển thủ công qua ứng dụng (App) Yanshee độc quyền trên điện thoại thông minh.
*   **Quản lý Thiết bị:** Hỗ trợ truy xuất phần trăm dung lượng pin thiết bị. Khả năng lấy thông tin phiên bản lõi của robot. Hỗ trợ đọc và điều chỉnh chi tiết mức âm lượng thiết bị từ 0 đến 100%, bao gồm cả chế độ im lặng (Mute).

**2. Thư viện Chuyển động (Locomotion & Action):**
*   **Điều hướng linh hoạt:** Khả năng đi tiến, đi lùi, rẽ trái, rẽ phải, bước ngang từng bước và chế độ đi nhanh.
*   **Chế độ Thể thao (Bóng đá):** Tích hợp chuỗi hành động sút bóng, dứt điểm mạnh bằng chân trái hoặc phải. Đóng vai trò thủ môn với khả năng đổ người cản phá bóng và xoạc bóng.
*   **Chế độ Thể chất & Chiến đấu:** Hỗ trợ thực hiện bài tập hít đất (chống đẩy). Khả năng tự lật người và đứng dậy an toàn khi bị ngã sấp hoặc ngã ngửa. Thực hiện các đòn tấn công như đấm thẳng và đấm ngang móc.
*   **Biểu cảm Cơ thể:** Các cử chỉ giao tiếp xã hội như vẫy tay chào tạm biệt, dang tay ôm, và giơ hai tay ăn mừng (Victory).
*   **Quản lý Năng lượng:** Chế độ tự động ngồi xổm để tiết kiệm năng lượng (Energy Saving Squat) khi không hoạt động và khả năng thức dậy trở lại.

**3. Giải trí & Tính năng Mở rộng (Của dự án cũ):**
*   **Âm nhạc & Vũ đạo:** Khả năng phát các tệp âm thanh. Tích hợp các bài nhảy múa được lập trình sẵn theo chủ đề âm nhạc như WakaWaka, Giáng sinh (Merry Christmas) và Sinh nhật (Happy Birthday).
*   **Điều khiển Đa Robot (Swarm Control):** Hệ thống mã nguồn nền tảng hỗ trợ duy trì kết nối TCP/IP đồng thời với nhiều robot Yanshee cùng lúc. Hỗ trợ giám sát sức khỏe (health check) định kỳ và phát lệnh đồng bộ (sync_play_motion) đến toàn bộ cụm robot.
*   **Điều khiển bằng Cử chỉ Camera (Legacy):** Hỗ trợ nhận diện cử chỉ tay (MediaPipe) để ra lệnh cho Yanshee. Tích hợp cơ chế bảo mật khóa/mở bằng biểu tượng ngón tay cái (Like/Dislike) và xòe tay (Palm) để tạm dừng lệnh.

---

## PHẦN 2: HỆ THỐNG NHẬN DIỆN KHUÔN MẶT THÔNG MINH (Nhánh Van)
Nâng cấp hệ thống thị giác máy tính, biến camera gốc của Yanshee thành một trạm phát luồng video (MJPEG Streamer) và xử lý AI độc lập trên máy tính.

**Các chức năng nổi bật:**
1. **Nhận diện Khuôn mặt không dùng AI Model nặng:** Sử dụng thuật toán sinh trắc học Face Geometry Embedding, tính toán tỷ lệ, khoảng cách và góc giữa 478 điểm lưới khuôn mặt (MediaPipe Face Mesh) thay vì các model tốn tài nguyên.
2. **Kháng khoảng cách & Tự động căn chỉnh:** Nhận diện chính xác dù người dùng đứng gần hay lùi ra xa. Tự động định vị mắt, xoay và căn chỉnh ảnh trước khi xử lý.
3. **Đăng ký sinh trắc 2 Pha (Gần & Xa):** Yêu cầu chụp 7 ảnh khi đứng gần (0.5-1m) và 3 ảnh khi đứng xa (1.5-2m) để làm phong phú dữ liệu, kèm cơ chế kiểm tra chất lượng chống ảnh mờ/tối.
4. **Kiểm tra thực thể sống (Liveness Detection):** Yêu cầu người dùng thực hiện thử thách chớp mắt để chống giả mạo bằng hình ảnh tĩnh.
5. **Hiệu suất cao & Dashboard giám sát:** Xử lý bất đồng bộ (non-blocking) qua `ThreadPoolExecutor` giúp luồng camera luôn mượt mà. Cung cấp Dashboard giám sát thời gian thực xây dựng bằng FastAPI & WebSocket.
6. **Tương tác Tự động:** Nhận diện đúng người sẽ tự động kết nối qua Wi-Fi để gọi action (hành động vẫy tay/chào) và đọc tên người dùng (phân quyền Admin, Teacher, Student, Guest).

---

## PHẦN 3: HỆ THỐNG TRỢ LÝ ẢO TIẾNG VIỆT & BỘ NHỚ ĐỘNG (Nhánh Linh)
Đập bỏ hoàn toàn hệ thống giao tiếp cứng nhắc cũ, tích hợp Trí tuệ nhân tạo sinh tạo (Generative AI) và kiến trúc quản lý bộ nhớ linh hoạt.

**Các chức năng nổi bật:**
1. **Trợ lý Ảo AI Tiếng Việt (Feature_VietNamese_TTS):** 
   * Khắc phục rào cản ngôn ngữ mặc định (chỉ hỗ trợ tiếng Anh/Trung). Lắng nghe dữ liệu giọng nói tiếng Việt mượt mà qua micro máy tính.
   * Tích hợp API Google Gemini (LLM) để xử lý Ngôn ngữ Tự nhiên (NLP). Yanshee có thể hiểu ngữ cảnh phức tạp, trò chuyện tự nhiên và giải đáp đa lĩnh vực thay vì phản hồi rập khuôn.
   * Sử dụng Google Text-to-Speech (`gTTS`) xuất đoạn hội thoại thành file âm thanh tiếng Việt chuẩn, đẩy qua giao thức mạng xuống loa của Yanshee phát ngay lập tức.
2. **Điều khiển Giọng nói qua Bộ nhớ Động (Feature_Smart_Voice_Memory):**
   * **Quản lý Trạng thái bằng JSON:** Xây dựng tệp `robot_memory.json` đóng vai trò như "não bộ" lưu trữ các lệnh, thay thế hoàn toàn hàng chục dòng lệnh điều kiện `if/else` chằng chịt cũ.
   * **Ánh xạ Hành động (Dynamic Mapping):** Tự động đối chiếu chuỗi lệnh văn bản thu được trong từ điển JSON để trích xuất file chuyển động tương ứng, giúp robot thực thi hành động liền mạch.
   * Hỗ trợ gỡ rối và nhận diện đa lệnh liên tiếp thông qua cơ chế phân tách và đánh giá từ khóa (Fuzzy Matching).
   * Hỗ trợ bóc tách linh hoạt các lệnh đếm số lượng (ví dụ: tiến "3" bước, đấm "2" lần). Tự động gom các lệnh vào hàng đợi ưu tiên (Priority Queue) để robot thực hiện tuần tự mà không bị xung đột.




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

# Yanshee AI Assistant & Smart Voice Control System

Hệ thống Trợ lý ảo giao tiếp tiếng Việt và Điều khiển robot Yanshee bằng giọng nói thông minh, tích hợp Trí tuệ nhân tạo sinh tạo (Generative AI) và hệ thống lưu trữ trạng thái động (Dynamic Memory) thay thế hoàn toàn cho các kịch bản hard-code truyền thống.

---

# Trợ lý Ảo AI Tiếng Việt (`Feature_VietNamese_TTS`)
Khắc phục giới hạn giao tiếp mặc định của Yanshee (chỉ hỗ trợ tiếng Anh/Trung), module này mang đến khả năng giao tiếp tự nhiên hoàn toàn bằng tiếng Việt:
*   **Xử lý Ngôn ngữ Tự nhiên (NLP) với LLM:** Tích hợp API **Google Gemini** qua thư viện `google-genai`. Hệ thống không dùng các câu trả lời rập khuôn `if/else`, mà có khả năng phân tích ngữ cảnh, hiểu câu lệnh phức tạp và sinh ra câu trả lời thông minh trên đa dạng lĩnh vực.
*   **Text-to-Speech (TTS) Thời gian thực:** Sử dụng `gTTS` để chuyển đổi luồng văn bản sinh ra từ AI thành tệp âm thanh `.mp3` chất lượng cao.
*   **Giao tiếp Phần cứng Trực tiếp:** Luồng âm thanh sau xử lý được truyền tải qua giao thức mạng xuống phần cứng robot Yanshee (thông qua `YanAPI.py`) để phát ra loa ngoài với độ trễ thấp nhất.

# Hệ thống Nhớ Giọng nói & Điều khiển Động (`Feature_Smart_Voice_Memory`)
Nâng cấp toàn diện phương thức điều khiển bằng giọng nói:
*   **Nhận diện Giọng nói Tiếng Việt (Speech-to-Text):** Sử dụng `SpeechRecognition` thu thập dữ liệu từ micro máy tính, lọc nhiễu và chuyển đổi chính xác thành văn bản (text).
*   **Quản lý Trạng thái bằng JSON (Dynamic Memory):** Đập bỏ cấu trúc rẽ nhánh điều kiện chằng chịt. Toàn bộ hệ thống lệnh và hành động được lưu trữ tại file từ điển `robot_memory.json`. Tính năng này đóng vai trò như "não bộ" mở rộng, cho phép dễ dàng thêm/bớt câu lệnh mới mà không cần can thiệp vào mã nguồn lõi.
*   **Ánh xạ Hành động (Action Mapping) Tự động:** Khi nhận được văn bản từ giọng nói, hệ thống tự động đối chiếu với cơ sở dữ liệu JSON để kích hoạt luồng chuyển động (motions) tương ứng, giúp Yanshee phản hồi mượt mà.

---

## Yêu cầu Hệ thống
*   Máy tính chạy Windows 10/11 hoặc Ubuntu/Linux.
*   Python 3.10 trở lên.
*   Microphone đang hoạt động bình thường trên máy tính.
*   Tài khoản Google và API Key của Google Gemini.
*   Robot Yanshee (đã bật nguồn, kết nối chung mạng LAN/Wi-Fi với máy tính).

---

## Hướng dẫn Cài đặt & Khởi chạy

### Bước 1: Kích hoạt môi trường ảo (Khuyến nghị)
Để tránh xung đột thư viện, hãy chạy hệ thống trong môi trường ảo `.venv`:
**Trên Windows:**
```bash
python -m venv .venv
.venv\Scripts\activate
**Trên Ubuntu/Linux:**
python3 -m venv .venv
source .venv/bin/activate

### Bước 2: Cài đặt Thư viện lõi
Chạy lệnh sau để cài đặt các gói phụ thuộc cho xử lý âm thanh và AI:
pip install gTTS google-genai SpeechRecognition PyAudio
**Lưu ý cho Ubuntu:** Nếu cài PyAudio bị lỗi, hãy chạy lệnh sudo apt-get install portaudio19-dev trước khi pip install 

### Bước 3: Cấu hình hệ thống (Quan Trọng)
* Cấu hình IP Robot
  - Mở file Feature_VietNamese_TTS/test_voice_ys.py
  - Mở file Feature_Smart_Voice_Memory/main_control2.py
  - Tìm biến ROBOT_IP và đổi thành địa chỉ IP thực tế của robot Yanshee (VD: 10.165.178.75).
* Cấu hình API key AI
  - Mở file Feature_VietNamese_TTS/yanshee_ai.py.
  - Tìm biến GEMINI_API_KEY và thay chuỗi rỗng bằng API Key hợp lệ của bạn. (Tuyệt đối không push API Key thật lên public repository).

### Bước 4: Khởi chạy Chức năng
Hệ thống được chia thành 2 module hoạt động độc lập, bạn mở Terminal và chạy lệnh tương ứng với tính năng muốn sử dụng:
* Chạy Trợ lý Ảo Giao tiếp Tiếng Việt (TTS & Gemini):
  - Đưa micro lại gần, hỏi Yanshee bất kỳ câu hỏi nào, AI sẽ phân tích và robot sẽ trả lời bằng giọng nói.
  - python Feature_VietNamese_TTS/test_voice_ys.py
* Chạy Hệ thống Điều khiển Giọng nói (Smart Memory):
  - Ra lệnh bằng giọng nói (VD: "Tiến lên", "Lùi lại", "Nhảy múa"), hệ thống sẽ tra cứu JSON và điều khiển robot thực hiện hành động.
  - python Feature_Smart_Voice_Memory/main_control2.py

## Xử lý Sự cố (Troubleshooting)
  - Lỗi "Microphone not found" hoặc lỗi PyAudio: Kiểm tra lại giắc cắm micro. Đảm bảo bạn đã cấp quyền truy cập micro cho Terminal/Python trong cài đặt hệ thống (Privacy settings).
  - Lỗi google_genai.errors.APIError (401/403): API Key của Gemini bị sai, hết hạn hoặc chưa được kích hoạt. Hãy kiểm tra lại file yanshee_ai.py.
  - Lỗi Connection Refused hoặc Timeout khi robot không nói/chuyển động: Máy tính và robot không cùng lớp mạng Wi-Fi, hoặc bạn điền sai ROBOT_IP. Ping thử IP của Yanshee trong Terminal để kiểm tra kết nối.
