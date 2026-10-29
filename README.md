# 🤖 TÀI LIỆU VẬN HÀNH HỆ THỐNG YANSHEE AI (INTEGRATED SYSTEM)

Hệ thống biến Robot Yanshee thành **Trợ lý Robot Thông minh**, tích hợp **11 tính năng nâng cao** chạy đồng bộ trên kiến trúc bất đồng bộ (`asyncio` + `EventBus` + đa luồng `threading`). Hệ thống có thể hoạt động độc lập trên máy tính (sử dụng Webcam máy tính và loa PC) hoặc kết nối trực tiếp điều khiển Robot Yanshee qua mạng không dây.

---

## 🌟 PHẦN 1: CÁC TÍNH NĂNG VẬN HÀNH TRONG HỆ THỐNG

1. **Nhận diện Khuôn mặt Sinh trắc học (Face Recognition)**:
   - Thuật toán trích xuất đặc trưng `Enhanced (Pixel + HOG + LBP) v2` đạt vector 512 chiều.
   - So khớp Cosine Similarity kết hợp Zero-Centering và biên an toàn (`FACE_SIMILARITY_MARGIN = 0.020`, `FACE_SIMILARITY_THRESHOLD = 0.88`).
   - Kháng khoảng cách (Scale-Invariant), chống nhận nhầm người lạ (`Khách Lạ`).
2. **Chống Giả mạo (Liveness Detection)**:
   - Thử thách ngẫu nhiên cử động (chớp mắt, quay đầu trái/phải, ngửa/cúi mặt) trước khi xác thực.
3. **Quản lý Nguồn Camera Đa năng (Camera Manager)**:
   - Hỗ trợ cả **Webcam máy tính** (OpenCV) và **Camera MJPEG từ đầu Robot Yanshee** (HTTP Stream).
   - Cơ chế hàng đợi kích thước tối đa 2 frame (`MAX_FRAME_QUEUE = 2`) để triệt tiêu độ trễ hình ảnh.
4. **Hàng đợi Hành động Robot Có Ưu tiên (ActionQueue & Greeting)**:
   - Quản lý các lệnh gửi tới robot theo hàng đợi ưu tiên: `VOICE > GESTURE > GREETING > IDLE`.
   - Tự động chào hỏi và thực hiện cử chỉ theo vai trò người dùng (`Admin`, `Teacher`, `Student`, `Guest`, `Stranger`).
5. **Nhận diện Giọng nói Tiếng Việt (Voice Control)**:
   - Lắng nghe liên tục trên luồng riêng (`threading.Thread`), tự động khử ồn môi trường và nhận diện qua Google Speech Recognition.
   - Hoàn toàn không gây đơ/lag khung hình camera.
6. **Bộ nhớ Thông minh (Smart Memory - `RobotMemory`)**:
   - Quản lý từ khóa lệnh tiếng Việt và ánh xạ tới 30+ động tác cử chỉ của robot.
   - Dữ liệu được lưu trong file [`data/robot_memory.json`](file:///c:/Users/LENOVO/YANSHEE_CONTROL-main/data/robot_memory.json) với cấu trúc JSON: mỗi motion là khóa, giá trị là mảng các từ khóa.
   - Thư viện thực hiện tải và tra cứu nằm ở `voice/robot_memory.py`. Để xem chi tiết và hướng dẫn cập nhật, tham khảo tài liệu [Robot Memory Documentation](file:///C:/Users/LENOVO/.gemini/antigravity/brain/432fabeb-a34f-427b-92af-10b79d0e0481/robot_memory_documentation.md).
   - Quản lý từ khóa lệnh tiếng Việt và ánh xạ tới 30+ động tác cử chỉ của robot qua file [`data/robot_memory.json`](file:///c:/Users/LENOVO/YANSHEE_CONTROL-main/data/robot_memory.json).
7. **Phát âm Tiếng Việt (Vietnamese TTS & Audio Routing)**:
   - Tạo âm thanh tiếng Việt bằng `gTTS`.
   - Hỗ trợ 3 chế độ phát loa qua cấu hình `AUDIO_OUTPUT_MODE`: `"PC"` (loa máy tính), `"ROBOT"` (loa robot qua SSH + `mpg123`), hoặc `"BOTH"` (phát cả hai).
   - Tự động chuyển về loa máy tính (`local_tts` / `pyttsx3`) khi robot offline.
8. **Web Dashboard Giám sát Realtime**:
   - Máy chủ FastAPI (`http://127.0.0.1:8000`) cung cấp luồng video trực tiếp và WebSocket đẩy sự kiện thời gian thực.
9. **Giám sát Tài nguyên Hệ thống (System Monitor)**:
   - Thu thập thông số CPU, RAM, ổ đĩa, lưu lượng mạng và phát sự kiện `SYSTEM_METRICS` định kỳ 3 giây/lần.
10. **Hạ tầng Cốt lõi (Core Infrastructure)**:
    - Quản lý thông điệp tập trung qua `EventBus`, cơ sở dữ liệu SQLite [`data/yanshee_faceid.db`](file:///c:/Users/LENOVO/YANSHEE_CONTROL-main/data/yanshee_faceid.db), tự động làm mới bộ nhớ khi có người đăng ký mới (Auto-Reload DB Watchdog), ghi log với `loguru`.
11. **Nhận diện Cử chỉ Tay (Gesture Control)**:
    - Sử dụng MediaPipe Hands để nhận diện các cử chỉ (Xòe tay, Nắm tay, Like, Dislike, Vẫy tay...).
    - Chuyển đổi qua lại mượt mà với chế độ Nhận diện khuôn mặt trực tiếp ngay trên Terminal (CLI).

---

## 📂 PHẦN 2: CẤU TRÚC THƯ MỤC DỰ ÁN

```text
YANSHEE_CONTROL-main/
├── main.py                  # Entry point chính chạy toàn bộ hệ thống
├── config.py                # File cấu hình duy nhất của toàn bộ hệ thống
├── requirements.txt         # Danh sách thư viện Python phụ thuộc
├── YanAPI.py                # SDK giao tiếp phần cứng Robot Yanshee
├── activate_env.ps1         # Script kích hoạt nhanh môi trường ảo
├── camera/                  # Quản lý nguồn camera
│   ├── camera_manager.py       # Bộ điều phối và chuyển nguồn camera
│   ├── camera_source.py        # Interface trừu tượng nguồn camera
│   ├── webcam_camera_source.py # Thu hình từ Webcam laptop/PC
│   └── yanshee_camera_source.py# Thu luồng MJPEG từ đầu Robot Yanshee
├── recognition/             # Nhận diện khuôn mặt & Liveness
│   ├── pipeline.py             # Luồng xử lý pipeline nhận diện
│   ├── face_matcher.py         # So khớp vector khuôn mặt (Cosine + Centroid)
│   ├── embedding_extractor.py  # Trích xuất đặc trưng 512 chiều (Pixel+HOG+LBP)
│   ├── canonical_normalizer.py # Chuẩn hóa khuôn mặt (căn chỉnh kích thước, góc)
│   ├── face_database.py        # Thao tác đọc/ghi vector vào Database
│   └── register_user.py        # Script đăng ký khuôn mặt người dùng mới
├── vision/                  # Thị giác máy tính cơ bản
│   ├── face_detector.py        # Bắt vị trí khuôn mặt bằng MediaPipe
│   └── quality_checker.py      # Kiểm tra chất lượng ảnh (độ nét, ánh sáng, góc nghiêng)
├── liveness/                # Chống giả mạo
│   ├── liveness_manager.py     # Quản lý thử thách cử động khuôn mặt
│   └── head_pose_detector.py   # Đo góc ngẩng/nghiêng/quay đầu
├── robot/                   # Điều khiển & kết nối robot
│   ├── robot_connection.py     # Giám sát nhịp tim (Heartbeat) & kết nối Robot
│   ├── yanshee_client.py       # REST API client gửi lệnh motion / tts tới Robot
│   ├── robot_action_engine.py  # Điều phối hành động chào đón, TTS, cử chỉ
│   ├── action_queue.py         # Hàng đợi ưu tiên tránh xung đột lệnh
│   ├── robot_audio_stream.py   # Stream âm thanh từ Robot về PC
│   └── speech_engine.py        # TTS fallback trên máy tính cục bộ
├── voice/                   # Giọng nói tiếng Việt
│   ├── voice_controller.py     # Thu âm và nhận diện giọng nói nền
│   ├── robot_memory.py         # Nạp và tra cứu từ khóa cử chỉ robot
│   └── tts_engine.py           # Chuyển văn bản thành tiếng Việt (gTTS + SSH)
├── gesture/                 # Điều khiển bằng cử chỉ tay
│   ├── gesture_bridge.py       # Cầu nối gửi lệnh gesture vào ActionQueue
│   └── cam_control.py          # Thuật toán MediaPipe nhận diện cử chỉ tay
├── dashboard/               # Giao diện Web Dashboard
│   ├── app.py                  # Máy chủ FastAPI + WebSocket
│   ├── templates/              # HTML giao diện giám sát
│   └── static/                 # CSS, JavaScript cho dashboard
├── database/                # Khởi tạo SQLite
│   ├── db.py                   # Quản lý kết nối SQLAlchemy
│   └── models.py               # Định nghĩa bảng Users và Embeddings
├── data/                    # Dữ liệu hệ thống
│   ├── yanshee_faceid.db       # Cơ sở dữ liệu người dùng & vector khuôn mặt
│   └── robot_memory.json       # Từ điển lệnh giọng nói ánh xạ hành động
├── utils/                   # Tiện ích bổ trợ
│   └── monitor.py              # Thu thập thông số phần cứng (CPU, RAM, Disk)
├── logs/                    # Quản lý file log
│   ├── logger.py               # Thiết lập định dạng loguru
│   └── system.log              # File nhật ký hoạt động
└── tools/                   # Các công cụ kiểm tra độc lập
    ├── check_robot.py          # Kiểm tra kết nối và gửi lệnh thử tới Robot
    ├── check_camera.py         # Kiểm tra danh sách camera kết nối PC
    ├── check_tts.py            # Kiểm tra phát âm thanh TTS
    ├── check_db.py             # Kiểm tra nhanh số lượng user trong database
    ├── view_db.py              # Xem chi tiết danh sách user đã đăng ký
    ├── reset_embeddings.py     # Xóa và tạo lại vector khi đổi model
    └── install_streamer_service.sh # Cài service camera stream trên Robot
```

---

## 💻 PHẦN 3: YÊU CẦU HỆ THỐNG & CÀI ĐẶT

### 1. Yêu cầu môi trường
- **Hệ điều hành**: Windows 10/11, Ubuntu 20.04+, hoặc macOS.
- **Python**: Khuyến nghị phiên bản **3.10** hoặc **3.11** (64-bit).
- **Thiết bị**:
  - Microphone (thu âm lệnh giọng nói).
  - Webcam máy tính (nếu chạy chế độ độc lập) hoặc Robot Yanshee (nếu chạy điều khiển robot).
  - Khi dùng Robot, PC và Robot **phải kết nối chung mạng Wi-Fi/LAN**.

### 2. Các bước cài đặt trên Máy tính

1. **Mở Terminal tại thư mục dự án và kích hoạt môi trường ảo:**
   - Trên PowerShell (Windows):
     ```powershell
     .\activate_env.ps1
     ```
     *Hoặc thủ công:*
     ```cmd
     python -m venv .venv
     .\.venv\Scripts\activate
     ```

2. **Cài đặt các gói thư viện phụ thuộc:**
   ```cmd
   pip install -r requirements.txt
   ```

---

## ⚙️ PHẦN 4: THIẾT LẬP CẤU HÌNH (`config.py`)

Tất cả cấu hình được quản lý tập trung trong file [`config.py`](file:///c:/Users/LENOVO/YANSHEE_CONTROL-main/config.py):

| Nhóm tham số | Tên biến | Giá trị khuyên dùng | Chức năng |
| :--- | :--- | :--- | :--- |
| **Chế độ Camera** | `USE_WEBCAM` | `True` (dùng webcam PC)<br>`False` (dùng camera Robot) | Chọn nguồn camera cho hệ thống. |
| | `CAMERA_INDEX` | `0` | Chỉ số Webcam máy tính (thường là 0 cho camera tích hợp). |
| | `YANSHEE_CAMERA_ENABLED` | `False` (khi dùng webcam)<br>`True` (khi lấy stream Robot) | Bật/tắt kết nối luồng camera đầu robot. |
| **Kết nối Robot** | `ROBOT_ENABLED` | `True` | Bật/tắt tính năng kết nối robot. |
| | `ROBOT_IP` | `"10.36.31.75"` *(IP thực tế)* | Địa chỉ IP của Robot Yanshee trong mạng Wi-Fi. |
| | `ROBOT_PORT` | `9090` | Cổng REST API của Robot (OpenADK). |
| | `YANSHEE_IP` | `ROBOT_IP` | Tự động đồng bộ với `ROBOT_IP`. |
| **Nhận diện Mặt** | `FACE_SIMILARITY_THRESHOLD` | `0.88` | Ngưỡng Cosine Similarity xác nhận đúng người. |
| | `FACE_SIMILARITY_MARGIN` | `0.020` | Khoảng cách an toàn giữa người top 1 và top 2. |
| | `REQUIRED_CONSISTENT_FRAMES` | `5` | Số khung hình liên tiếp khớp để xác nhận danh tính. |
| | `LIVENESS_ENABLED` | `True` | Bật/tắt chống giả mạo khuôn mặt. |
| **Giọng nói & Loa** | `VOICE_ENABLED` | `True` | Bật/tắt nhận diện giọng nói tiếng Việt. |
| | `VN_TTS_ENABLED` | `True` | Bật/tắt phát âm phản hồi tiếng Việt. |
| | `AUDIO_OUTPUT_MODE` | `"BOTH"` / `"PC"` / `"ROBOT"` | Chọn nơi phát âm thanh phản hồi. |
| **Cử chỉ tay** | `GESTURE_ENABLED` | `False` | Mặc định khởi động ở chế độ Face (có thể đổi qua CLI). |

---

## 🚀 PHẦN 5: HƯỚNG DẪN VẬN HÀNH

### 1. Hai chế độ vận hành chính

#### 🔹 Chế độ A: Chạy độc lập trên máy tính (Không cần Robot)
Dùng khi phát triển, thuyết trình hoặc kiểm tra tính năng nhận diện, giọng nói, cử chỉ:
1. Mở [`config.py`](file:///c:/Users/LENOVO/YANSHEE_CONTROL-main/config.py):
   ```python
   USE_WEBCAM = True
   YANSHEE_CAMERA_ENABLED = False
   AUDIO_OUTPUT_MODE = "PC"
   ```
2. Khởi chạy hệ thống:
   ```cmd
   python main.py
   ```
   *Hệ thống tự động sử dụng Webcam laptop và loa máy tính. Trạng thái robot tự chuyển `offline` mà không gây lỗi.*

#### 🔹 Chế độ B: Chạy đầy đủ kết nối với Robot Yanshee
1. Khởi động Robot Yanshee, kết nối Robot vào cùng mạng Wi-Fi với máy tính.
2. Kiểm tra IP của robot và điền vào [`config.py`](file:///c:/Users/LENOVO/YANSHEE_CONTROL-main/config.py):
   ```python
   ROBOT_IP = "10.36.31.75"  # Thay bằng IP thực tế của Robot
   USE_WEBCAM = False
   YANSHEE_CAMERA_ENABLED = True
   AUDIO_OUTPUT_MODE = "BOTH"
   ```
3. Chạy công cụ kiểm tra kết nối nhanh:
   ```cmd
   python tools/check_robot.py
   ```
   *Nếu màn hình hiện "Kết nối Robot thành công!", bạn đã sẵn sàng.*

---

### 2. Đăng ký Khuôn mặt Người dùng Mới

Trước khi bắt đầu, hãy đăng ký khuôn mặt để robot có dữ liệu nhận diện:
```cmd
python -m recognition.register_user --name "Nguyen Van A" --role Student
```
- Các vai trò (`--role`): `Admin`, `Teacher`, `Student`, `Guest`.
- Camera sẽ mở ra, bạn chỉ cần nhìn thẳng vào camera, quay nhẹ mặt để hệ thống tự động lưu 20-24 mẫu vector đặc trưng vào database.
- Cơ chế **Auto-Reload Watchdog** sẽ tự động nạp dữ liệu người mới ngay lập tức mà **không cần khởi động lại `main.py`**.

---

### 3. Khởi chạy Hệ thống Chính (`main.py`)

Chạy lệnh duy nhất trong terminal:
```cmd
python main.py
```

Sau khi khởi động, **mọi thao tác vận hành hàng ngày đều được thực hiện trực tiếp trên Web Dashboard** mà không cần quay lại terminal.

---

### 4. Truy cập Giao diện Web Dashboard (Trung Tâm Điều Khiển Chính)

Mở trình duyệt web và truy cập địa chỉ:
👉 **[http://127.0.0.1:8000](http://127.0.0.1:8000)**

Giao diện Web Dashboard tích hợp đầy đủ mọi chức năng vận hành thực tế:
1. **Chuyển chế độ hoạt động (Mode Control Bar)**:
   - **`Face Recognition (1)`**: Nhận diện khuôn mặt, chống giả mạo sinh trắc học và hiển thị khung nhận diện.
   - **`Gesture Control (2)`**: Giải phóng camera nhận diện, chuyển giao cho MediaPipe nhận diện cử chỉ tay (Like, Dislike, Vẫy tay, Ôm...).
   - **`Gemini AI (3)`**: Chế độ trò chuyện và điều khiển robot tự nhiên qua mô hình ngôn ngữ lớn Gemini.
   - **`Dừng Hệ Thống (Shutdown)`**: Dừng an toàn toàn bộ luồng, camera, micro, kết nối robot và máy chủ từ giao diện web.
2. **Khung video trực tiếp (`/video_feed`)**:
   - Stream MJPEG tốc độ cao lấy trực tiếp từ `CameraManager`.
   - Lớp vẽ đồ họa (Canvas Overlay) thể hiện Bounding Box, tên người dùng, tỷ lệ nhận diện (`Confidence`) và trạng thái thử thách `Liveness`.
3. **Bảng điều khiển Robot trực tiếp (Robot Direct Motion)**:
   - Các nút cử động nhanh: Tiến (`Forward`), Lùi (`Backward`), Rẽ trái (`TurnLeft`), Rẽ phải (`TurnRight`), Chào (`RaiseRightHand`), Vẫy tay (`H_WaveRH`), Ôm (`Hug`), Sút bóng (`Football_RKick`), Đứng nghiêm (`Reset`).
   - Lệnh được đưa trực tiếp vào `ActionQueue` có độ ưu tiên, xử lý an toàn không xung đột.
4. **Giọng nói, TTS Tiếng Việt & Bộ nhớ thông minh (Smart Memory)**:
   - Bật/Tắt thu âm micro (`Voice Controller`).
   - Ô nhập văn bản tiếng Việt và nút phát âm thanh TTS qua loa máy tính hoặc robot.
   - Form dạy từ khóa mới cho robot: chọn động tác và gõ từ mới để robot tự nạp vào [`data/robot_memory.json`](file:///c:/Users/LENOVO/YANSHEE_CONTROL-main/data/robot_memory.json).
5. **Giám sát tài nguyên & Nhật ký sự kiện thời gian thực**:
   - Vòng tròn đo % CPU, RAM, Ổ đĩa, Camera FPS, độ trễ và thời gian hoạt động (`Uptime`).
   - Luồng log sự kiện thời gian thực đẩy qua WebSocket (`/ws`).

#### 🎮 Phương án kỹ thuật dự phòng (Terminal CLI):
Nếu thao tác trên terminal, bạn vẫn có thể gõ `1`/`face`, `2`/`gesture`, `3`/`ai` hoặc `quit`. Cả CLI và Dashboard đều gọi chung qua tầng điều phối [`mode_coordinator.py`](file:///c:/Users/LENOVO/YANSHEE_CONTROL-main/mode_coordinator.py) đảm bảo đồng bộ 100%.

---

### 5. Điều khiển bằng Giọng nói Tiếng Việt

Khi tính năng giọng nói được bật (`VOICE_ENABLED = True`), hệ thống tự động nghe lệnh qua micro. Các lệnh mẫu được định nghĩa sẵn trong [`data/robot_memory.json`](file:///c:/Users/LENOVO/YANSHEE_CONTROL-main/data/robot_memory.json):
- *"Đi thẳng"* / *"Tiến lên"* → Robot thực hiện động tác `Forward`.
- *"Lùi lại"* → Robot thực hiện động tác `Backward`.
- *"Rẽ trái"* / *"Rẽ phải"* → Robot rẽ hướng.
- *"Đứng yên"* / *"Dừng lại"* → Robot `Reset` về tư thế chuẩn.
- *"Chào bạn"* / *"Vẫy tay"* → Robot thực hiện động tác `RaiseRightHand` hoặc `Hug`.

---

## 🛠️ PHẦN 6: CÔNG CỤ HỖ TRỢ KIỂM TRA ĐỘC LẬP (`tools/`)

| Lệnh | Chức năng kiểm tra |
| :--- | :--- |
| `python tools/check_robot.py` | Kiểm tra kết nối mạng REST API tới robot và thử gửi 1 cử động. |
| `python tools/check_camera.py` | Quét và kiểm tra chỉ số camera khả dụng trên máy tính. |
| `python tools/check_tts.py` | Kiểm tra giọng nói TTS phát trên loa máy tính. |
| `python tools/view_db.py` | Xem danh sách tất cả người dùng và số vector đã lưu trong DB. |
| `python tools/reset_embeddings.py` | Xóa và tạo lại vector khi nâng cấp thuật toán trích xuất đặc trưng. |

---

## ❓ PHẦN 7: XỬ LÝ SỰ CỐ THƯỜNG GẶP (FAQ)

1. **Lỗi `ModuleNotFoundError` khi chạy?**
   - Đảm bảo đã kích hoạt môi trường ảo: `.\.venv\Scripts\activate`.
   - Cài đặt đầy đủ gói: `pip install -r requirements.txt`.
2. **Không có robot thì có chạy được nhận diện không?**
   - Có! Đặt `USE_WEBCAM = True` và `YANSHEE_CAMERA_ENABLED = False` trong [`config.py`](file:///c:/Users/LENOVO/YANSHEE_CONTROL-main/config.py), hệ thống sẽ chạy hoàn hảo trên webcam máy tính.
3. **Camera bị đơ hoặc báo `Cannot open webcam`?**
   - Kiểm tra xem có ứng dụng khác (Zoom, Teams, trình duyệt) đang chiếm quyền webcam không.
   - Chạy `python tools/check_camera.py` để tìm đúng `CAMERA_INDEX` (thường là 0 hoặc 1).
4. **Robot không phản hồi lệnh khi đã kết nối Wi-Fi?**
   - Dùng lệnh `ping <IP_ROBOT>` trong terminal để kiểm tra thông mạng.
   - Kiểm tra cổng REST API của robot (mặc định là `9090`).
   - Chạy `python tools/check_robot.py` để xem thông báo lỗi chi tiết.

## 🗂️ Chi tiết mã nguồn (Sync with README)

- **Voice Control**  
  - Mã: [`voice/voice_controller.py`](file:///C:/Users/LENOVO/YANSHEE_CONTROL-main/voice/voice_controller.py)  
  - Thực hiện: lắng nghe, chuẩn hoá, gọi `RobotMemory.find_motion`.

- **Smart Memory**  
  - Dữ liệu: [`data/robot_memory.json`](file:///C:/Users/LENOVO/YANSHEE_CONTROL-main/data/robot_memory.json)  
  - Mã: [`voice/robot_memory.py`](file:///C:/Users/LENOVO/YANSHEE_CONTROL-main/voice/robot_memory.py)  

- **Cấu hình hệ thống**  
  - Mã: [`config.py`](file:///C:/Users/LENOVO/YANSHEE_CONTROL-main/config.py) – liệt kê tất cả tham số cấu hình.

- **Entry point**  
  - Mã: [`main.py`](file:///C:/Users/LENOVO/YANSHEE_CONTROL-main/main.py) – khởi tạo EventBus, RobotMemory, VoiceController, Dashboard, v.v.

- **Dashboard**  
  - Mã: [`dashboard/app.py`](file:///C:/Users/LENOVO/YANSHEE_CONTROL-main/dashboard/app.py) – FastAPI server cho Web UI.

Bạn có thể mở các file trên để xem chi tiết thực thi và cập nhật tài liệu khi có thay đổi.
