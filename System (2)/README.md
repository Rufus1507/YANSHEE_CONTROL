# HỆ THỐNG ĐIỀU KHIỂN ROBOT YANSHEE AI (GIỌNG NÓI & CAMERA CỬ CHỈ)

Tài liệu này tổng hợp toàn bộ các giao diện lập trình **API (YanAPI)**, danh sách các **Động tác (Motions)** của robot Yanshee, và các cơ chế điều khiển thông qua Giọng nói (Voice) & Camera AI được tích hợp trong hệ thống.

---

## 📌 HƯỚNG DẪN CÀI ĐẶT NHANH

Để cài đặt tất cả các thư viện cần thiết chạy dự án, sử dụng file [requirements.txt](file:///c:/System/requirements.txt) bằng lệnh sau trong terminal:

```bash
pip install -r requirements.txt
```

> [!WARNING]
> **LỖI PYAUDIO TRÊN WINDOWS:** Nếu bạn gặp lỗi đỏ liên quan đến `Visual C++ Build Tools` khi lệnh trên cài thư viện `pyaudio`, hãy chạy 2 lệnh sau để khắc phục:
> ```bash
> pip install pipwin
> pipwin install pyaudio
> ```

### 🚀 Cách Khởi Chạy Hệ Thống

Sau khi cài đặt xong thư viện, chỉ cần chạy tệp trung tâm để tự động bật cả Camera và luồng nhận diện Giọng nói:

```bash
python main_control.py
```
*(Đảm bảo đã đổi `ROBOT_IPS = ["127.0.0.1"]` trong file `main_control.py` sang IP thực tế của robot Yanshee bạn đang dùng).*

### 🧪 Chạy thử không cần robot

Để kiểm tra đầy đủ luồng Camera, Voice, NLP và hàng đợi lệnh mà không kết nối tới Yanshee, chạy:

```bash
python main_control.py --test
```

Chế độ này vẫn mở Camera và Microphone như bình thường. Các lệnh được gửi tới `FakeRobot` và hiển thị trong terminal thay vì gửi qua mạng tới robot. Có thể thoát bằng cách nói `tắt chương trình`, nhấn `ESC` trong cửa sổ camera hoặc nhấn `Ctrl+C`.

> [!NOTE]
> * Dự án yêu cầu Python 3.8+ và đã được cấu hình chạy ổn định trên Windows.
> * Đối với chức năng ghi âm trực tiếp, đảm bảo thiết bị thu âm (Microphone) của bạn hoạt động bình thường.
> * Phần mềm mặc định dùng Google Speech API (miễn phí, không cần cài server). Nếu muốn dùng Whisper cục bộ ngoại tuyến, hãy cài đặt thêm `torch` và `openai-whisper` (có hướng dẫn chi tiết trong `requirements.txt`).

---

## 🔌 TỔNG HỢP API CỦA YANSHEE (LỚP `YanAPI`)

Lớp `YanAPI` (được định nghĩa trong [YanAPI.py](file:///c:/System/YanAPI.py)) là một wrapper OOP nâng cao viết dựa trên OpenADK SDK để gửi yêu cầu REST HTTP tới Robot Yanshee qua Wi-Fi.

### 1. Khởi tạo đối tượng
```python
from YanAPI import YanAPI
robot = YanAPI(ip_address="192.168.1.100", port=9090, api_version="v1")
```

### 2. Chi tiết các hàm API thành viên

| Tên Hàm API | Tham Số | Kiểu Trả Về | Mô Tả Chức Năng |
| :--- | :--- | :--- | :--- |
| **`sync_play_motion`** | `name: str`<br>`direction: str = None`<br>`repeat: int = 1`<br>`speed: str = "normal"` | `dict` | Gửi lệnh thực hiện động tác (ví dụ: `'RaiseRightHand'`, `'Forward'`). |
| **`stop_motion`** | Không có | `dict` | Dừng ngay động tác robot đang thực hiện (Bypass validate). |
| **`get_motions_status`** | Không có | `dict` | Lấy trạng thái thực thi hiện tại của động tác (Đang chạy `'run'` hay Rảnh `'idle'`). |
| **`get_motions_list`** | Không có | `dict` | Lấy danh sách toàn bộ các động tác đã được cài đặt trên hệ thống robot. |
| **`get_battery`** | Không có | `dict` | Lấy phần trăm dung lượng pin hiện tại của robot Yanshee. |
| **`get_device_volume`**| Không có | `dict` | Lấy mức âm lượng hiện tại của robot (từ `0` đến `100`). |
| **`set_device_volume`**| `volume: int` | `dict` | Cài đặt mức âm lượng cho robot (giới hạn từ `0` đến `100`). |
| **`play_music`** | `name: str` | `dict` | Phát file âm thanh hoặc bài nhạc lưu trên robot (ví dụ: `'WakaWaka'`). |
| **`stop_music`** | Không có | `dict` | Dừng phát nhạc ngay lập tức. |
| **`get_device_versions`**| Không có | `dict` | Xem thông tin chi tiết phiên bản hệ điều hành Core trên robot. |

---

## 🏃 DANH SÁCH ĐỘNG TÁC (MOTIONS) & LỆNH GIỌNG NÓI TƯƠNG ỨNG

Dưới đây là bảng tra cứu danh sách các **Tên Động tác (Motion Name)** trong Yanshee kèm theo **Từ khóa Giọng nói Tiếng Việt** mà hệ thống tự động nhận diện và chuyển đổi thông qua NLP (Fuzzy Match / Exact Match).

### 1. Nhóm Di chuyển & Đứng thẳng (Movement)

| Tên Motion trên Robot | Từ Khóa Giọng Nói Tiếng Việt Nhận Diện | Hành Động Thực Tế |
| :--- | :--- | :--- |
| **`Forward`** | *tiến, tiến lên, đi tới, đi lên, forward, go forward* | Đi bộ tiến về phía trước liên tục |
| **`Backward`** | *lùi, đi lùi, lùi lại, bước lui, back, go back* | Đi lùi về phía sau liên tục |
| **`TurnLeft`** | *rẽ trái, quay trái, left, turn left* | Xoay người sang bên trái |
| **`TurnRight`** | *rẽ phải, quay phải, right, turn right* | Xoay người sang bên phải |
| **`OneStepForward`** | *bước tới, bước lên* | Đi tiến duy nhất 1 bước |
| **`OneStepBackward`** | *bước lùi* | Đi lùi duy nhất 1 bước |
| **`OneStepTurnLeft`** | *xoay trái một bước* | Xoay sang trái 1 bước đơn |
| **`OneStepTurnRight`** | *xoay phải một bước* | Xoay sang phải 1 bước đơn |
| **`OneStepMoveLeft`** | *qua trái* | Bước dịch ngang sang bên trái |
| **`OneStepMoveRight`** | *qua phải* | Bước dịch ngang sang bên phải |
| **`Move_fast`** | *đi nhanh, nhanh lên* | Đi bộ với tốc độ nhanh |
| **`Stop`** | *dừng, dừng lại, stop, đứng yên* | Khẩn cấp dừng di chuyển / động tác |
| **`Reset`** | *reset, đứng thẳng* | Đứng thẳng ở tư thế mặc định ban đầu |

### 2. Giao tiếp, Chào hỏi & Sinh hoạt

| Tên Motion trên Robot | Từ Khóa Giọng Nói Tiếng Việt Nhận Diện | Hành Động Thực Tế |
| :--- | :--- | :--- |
| **`RaiseRightHand`** | *giơ tay lên, giơ tay, tạm biệt* | Giơ tay phải lên |
| **`H_WaveRH`** | *vẫy tay, wave, tạm biệt, bye, goodbye* | Vẫy tay chào / tạm biệt |
| **`Hug`** | *ôm, ôm đi* | Đưa hai tay ra trước thực hiện động tác ôm |
| **`Victory`** | *xin chào, ăn mừng, chào, hi, hello, hey* | Giơ cả hai tay lên cao ăn mừng chiến thắng |
| **`GetUp`** | *Tập thể dục, tập thể dục đi, tập thể dục lên* | Thực hiện chuỗi động tác thể dục khởi động |
| **`PushUp`** | *hít đất, hít đất đi, chống đẩy, chống đẩy đi* | Nằm xuống sàn thực hiện động tác hít đất |
| **`GetupFront`** | *ngã sấp đứng dậy, nằm sấp đứng lên, lật người* | Tự động đứng lên từ tư thế nằm sấp |
| **`GetupRear`** | *ngã ngửa đứng dậy, nằm ngửa đứng lên, ngồi dậy* | Tự động đứng lên từ tư thế nằm ngửa |
| **`EnterEnergySavingSquat`** | *nghỉ, nghỉ ngơi, tiết kiệm năng lượng* | Hạ thấp trọng tâm nghỉ, tắt motor để tiết kiệm pin |
| **`ExitEnergySavingReset`** | *dừng nghỉ, thoát tiết kiệm năng lượng* | Bật lại động cơ và trở về tư thế đứng thẳng |

### 3. Nhóm Bóng đá (Football / Sports)

| Tên Motion trên Robot | Từ Khóa Giọng Nói Tiếng Việt Nhận Diện | Hành Động Thực Tế |
| :--- | :--- | :--- |
| **`Football_LKick`** | *sút trái, đá trái, sút chân trái, đá chân trái* | Vung chân trái sút bóng nhẹ |
| **`Football_RKick`** | *sút phải, đá phải, sút chân phải, đá chân phải* | Vung chân phải sút bóng nhẹ |
| **`Football_LShoot`** | *dứt điểm trái, sút mạnh trái, sút bóng trái* | Sút bóng mạnh bằng chân trái |
| **`Football_RShoot`** | *dứt điểm phải, sút mạnh phải, sút bóng phải, đá bóng*| Sút bóng mạnh bằng chân phải |
| **`GoalKeeper1`** | *bắt bóng, thủ môn bắt bóng, bảo vệ khung thành* | Động tác thủ môn hạ trọng tâm cản bóng |
| **`GoalKeeper2`** | *bắt bóng trên, chuẩn bị bắt bóng, thủ môn* | Tư thế thủ môn sẵn sàng cản phá bóng cao |
| **`Football_LKeep`** | *bắt bóng trái, đổ người bên trái, đổ người trái* | Đổ người bay người bắt bóng sang bên trái |
| **`Football_RKeep`** | *bắt bóng phải, đổ người bên phải, đổ người phải* | Đổ người bay người bắt bóng sang bên phải |
| **`LeftTackle`** | *xoạc bóng trái, cướp bóng trái* | Xoạc chân trái cướp bóng |
| **`RightTackle`** | *xoạc bóng phải, cướp bóng phải* | Xoạc chân phải cướp bóng |
| **`Left slide tackle`**| *chồi bóng trái, trượt bóng trái* | Trượt dài xoạc cản bóng |

### 4. Nhóm Võ thuật / Chiến đấu (Combat)

| Tên Motion trên Robot | Từ Khóa Giọng Nói Tiếng Việt Nhận Diện | Hành Động Thực Tế |
| :--- | :--- | :--- |
| **`LeftSidePunch`** | *đấm ngang trái, đánh ngang trái, đấm tay trái* | Đấm móc ngang bằng tay trái |
| **`RightSidePunch`**| *đấm ngang phải, đánh ngang phải, đấm tay phải* | Đấm móc ngang bằng tay phải |
| **`LeftHitForward`**| *đấm thẳng trái, đánh thẳng trái, tấn công trái* | Đấm thẳng mạnh về phía trước bằng tay trái |
| **`RightHitForward`**| *đấm thẳng phải, đánh thẳng phải, tấn công phải* | Đấm thẳng mạnh về phía trước bằng tay phải |
| **`Fight_LSideHit`**| *đòn sườn trái, móc trái* | Đấm móc sườn trái |
| **`Fight_RSideHit`**| *đòn sườn phải, móc phải, đòn sườn* | Đấm móc sườn phải |

### 5. Nhóm Điều khiển Nhạc & Âm lượng (Media & Volume)

Hệ thống hỗ trợ đàm thoại và phát các tệp âm thanh trực tiếp trên Robot:

- **Bật nhạc:** Nói các câu chứa *"phát nhạc", "bật nhạc", "mở nhạc"*.
  - *Đặc biệt:* Có thể chỉ định bài hát cụ thể:
    - Nhạc nhảy Waka Waka: *"bật nhạc waka waka"*, *"nhảy đi"*
    - Nhạc Giáng sinh: *"mở nhạc giáng sinh"*, *"giáng sinh vui vẻ"*
    - Nhạc Sinh nhật: *"bật nhạc chúc mừng sinh nhật"*, *"happy birthday"*
    - Nhạc cất cánh: *"mở nhạc cất cánh"*, *"cất cánh thôi"*
- **Dừng nhạc:** Nói *"tắt nhạc", "dừng nhạc"*, hoặc *"dừng phát nhạc"*.
- **Tăng / Giảm âm lượng:** Nói *"tăng âm lượng"* (tăng +15 đơn vị) hoặc *"giảm âm lượng"* (giảm -15 đơn vị).
- **Tắt / Bật tiếng nhanh:** Nói *"tắt tiếng / im lặng"* (về `0`) hoặc *"bật âm thanh"* (lên `50`).
- **Đặt âm lượng theo tỷ lệ phần trăm:**
  - *"tăng âm lượng 20 phần trăm"* (tăng thêm 20)
  - *"giảm âm lượng 30 phần trăm"* (giảm đi 30)
  - *"đặt âm lượng về 70 phần trăm"* hoặc *"set âm lượng 80%"* (đặt chính xác chỉ số)

---

## 📷 BẢN ĐỒ CỬ CHỈ ĐIỀU KHIỂN QUA CAMERA (MediaPipe)

Trong [cam_control.py](file:///c:/System/cam_control.py), hệ thống nhận diện cử chỉ của bạn qua camera góc rộng máy tính để gửi lệnh song hành tới Robot.

### 🛡️ Cơ chế bảo mật 2 lớp (Lock/Unlock)

Để tránh robot thực hiện các hành động không mong muốn khi bạn vô tình di chuyển trước camera, hệ thống tích hợp chức năng khóa/mở bằng cử chỉ bàn tay:

1. **Để KÍCH HOẠT CỬA SỔ LỆNH:** Xòe bàn tay 5 ngón (Palm) giữ nguyên trong **5 giây** (Có thanh tiến trình màu vàng chạy dưới đáy màn hình).
2. **Xác nhận KHÓA HỆ THỐNG:** Khi camera báo đang chờ khóa/mở, đưa ngón tay cái xuống (**DISLIKE**). Hệ thống sẽ chuyển màu đỏ, chặn toàn bộ lệnh Pose.
3. **Xác nhận MỞ KHÓA HỆ THỐNG:** Khi camera báo đang chờ, đưa ngón tay cái hướng lên (**LIKE**). Hệ thống sẽ chạy boot chuẩn bị trong 3 giây trước khi sẵn sàng nhận cử chỉ.

### 🖖 Danh sách cử chỉ cơ thể và lệnh robot tương ứng

| Cử Chỉ Cơ Thể (Bạn thực hiện trước Camera) | Tên Lệnh Gửi Đi | Motion Robot Thực Thi |
| :--- | :--- | :--- |
| **Giơ tay phải qua vai** | `raise_right` | `RaiseRightHand` (Giơ tay phải chào) |
| **Giơ cả hai tay lên cao** | `victory` | `Victory` (Giơ hai tay chiến thắng) |
| **Đấm thẳng tay trái về trước** | `punch_forward_left` | `LeftHitForward` (Đấm thẳng trái) |
| **Đấm thẳng tay phải về trước** | `punch_forward_right`| `RightHitForward` (Đấm thẳng phải) |
| **Đấm ngang vai sang bên trái** | `punch_sideways_left`| `LeftSidePunch` (Đấm móc trái) |
| **Đấm ngang vai sang bên phải** | `punch_sideways_right`| `RightSidePunch` (Đấm móc phải) |
| **Đưa hai tay chéo/ôm trước ngực**| `hug` | `Hug` (Động tác ôm thân thiện) |
| **Nấc cao bàn chân trái lên** | `kick_left` | `Football_LKick` (Sút bóng bằng chân trái) |
| **Nấc cao bàn chân phải lên** | `kick_right` | `Football_RKick` (Sút bóng bằng chân phải) |
| **Buông cả hai tay về trạng thái nghỉ**| `stop` | `Reset` (Đứng thẳng mặc định) |

---

## 💡 CÁC TÍNH NĂNG NLP NÂNG CAO ĐÃ TÍCH HỢP

1. **Hỗ trợ ghép đa lệnh (Multi-command split):** Bạn có thể nói chuỗi lệnh dài như *"tiến lên 2 bước rồi ôm và rẽ trái quay trái"* → Hệ thống tự động bóc tách thành 3 hành động riêng biệt gửi tuần tự vào hàng đợi.
2. **Kháng nhiễu từ vựng (Fuzzy Matching):** Nhờ tích hợp thuật toán từ thư viện `rapidfuzz`, khi bạn nói không chuẩn từ khóa (ví dụ: *"lùi lại đi"* so với từ chuẩn *"lùi lại"*), hệ thống vẫn tính toán mức tương đồng trên 60% để khớp đúng motion `Backward`.
3. **Bộ đệm chống nhiễu camera (Pose Stability Gate):** Cử chỉ trước camera phải giữ yên ổn định trong **8 khung hình liên tiếp** mới được xác thực gửi đi, tránh trường hợp nhiễu khung hình hoặc chuyển động vô tình của cánh tay.
