"""
=== KIỂM TRA KẾT NỐI YANSHEE ===
Sử dụng thư viện chính thức: openadk (Yan_ADK)
Cài đặt: pip install https://github.com/UBTEDU/Yan_ADK/archive/latest.tar.gz

API Server chạy trên Yanshee ở port 9090
Endpoint gốc: http://<IP_ROBOT>:9090/v1
"""

import sys

ROBOT_IP = "192.168.150.75"
BASE_URL = f"http://{ROBOT_IP}:9090/v1"

print(f"=== KIỂM TRA KẾT NỐI YANSHEE ({ROBOT_IP}) ===")
print(f"    Thư viện: openadk (Yan_ADK)")
print(f"    Endpoint: {BASE_URL}\n")

# -------------------------------------------------------
# Kiểm tra thư viện openadk đã cài chưa
# -------------------------------------------------------
try:
    import openadk
    from openadk.rest import ApiException
    print("[OK] Thư viện openadk đã được cấu hình.\n")
except ImportError as e:
    if "chardet" in str(e):
        print("[LỖI] Thiếu thư viện 'chardet' (dependency của openadk)!")
        print("      Vui lòng chạy lệnh: pip install chardet\n")
    else:
        print("[LỖI] Thư viện openadk bị thiếu hoặc lỗi:", e)
        print("      Vui lòng chạy lệnh sau để cài:")
        print("      pip install https://github.com/UBTEDU/Yan_ADK/archive/latest.tar.gz\n")
    sys.exit(1)

# -------------------------------------------------------
# Cấu hình kết nối
# -------------------------------------------------------
configuration = openadk.Configuration()
configuration.host = BASE_URL

client = openadk.ApiClient(configuration)

# -------------------------------------------------------
# TEST 1: Lấy thông tin pin (DevicesApi - GET /devices/battery)
# -------------------------------------------------------
print("[TEST 1] Đọc thông tin pin...")
try:
    devices_api = openadk.DevicesApi(client)
    response = devices_api.get_devices_battery()
    print(f"  -> Thành công! Thông tin pin: {response}")
except ApiException as e:
    print(f"  -> Lỗi API (mã {e.status}): {e.reason}")
except Exception as e:
    print(f"  -> Không kết nối được: {type(e).__name__} - {e}")

# -------------------------------------------------------
# TEST 2: Lấy danh sách motion đã cài trên robot
# -------------------------------------------------------
print("\n[TEST 2] Lấy trạng thái motions...")
try:
    motions_api = openadk.MotionsApi(client)
    # Có thể robot trả về JSON không chuẩn (missing fields) nên nó báo lỗi parsing, bỏ qua catch cụ thể
    response = motions_api.get_motions()
    print(f"  -> Thành công! Trạng thái: {response}")
except ApiException as e:
    print(f"  -> Lỗi API (mã {e.status}): {e.reason}")
except Exception as e:
    print(f"  -> Không lấy được thông tin motions: {type(e).__name__} - {e}")

# -------------------------------------------------------
# TEST 3: Gửi lệnh giơ tay (motion: RaiseRightHand)
# -------------------------------------------------------
print("\n[TEST 3] Gửi lệnh giơ tay phải (motion: RaiseRightHand)...")
try:
    motions_api = openadk.MotionsApi(client)
    # Tên motion bắt buộc phải chính xác giống trong file hệ thống
    motion_param = openadk.MotionsParameter(
        name="RaiseRightHand", 
        repeat=1, 
        speed="normal"
    )
    motion_request = openadk.MotionsOperation(
        operation="start",
        motion=motion_param
    )
    
    response = motions_api.put_motions(body=motion_request)
    print(f"  -> Lệnh gửi thành công! Phản hồi: {response}")
except ApiException as e:
    print(f"  -> Lỗi API (mã {e.status}): {e.reason}")
except Exception as e:
    print(f"  -> Không kết nối được: {type(e).__name__} - {e}")

# -------------------------------------------------------
# TEST 4: Kiểm tra âm lượng 
# -------------------------------------------------------
print("\n[TEST 4] Đọc âm lượng hiện tại...")
try:
    devices_api = openadk.DevicesApi(client)
    response = devices_api.get_devices_volume()
    print(f"  -> Thành công! Âm lượng: {response}")
except ApiException as e:
    print(f"  -> Lỗi API (mã {e.status}): {e.reason}")
except Exception as e:
    print(f"  -> Không kết nối được: {type(e).__name__} - {e}")

# -------------------------------------------------------
# TEST 5: Kiểm tra phiên bản hệ thống
# -------------------------------------------------------
print("\n[TEST 5] Đọc phiên bản hệ thống (type='core')...")
try:
    devices_api = openadk.DevicesApi(client)
    response = devices_api.get_devices_versions(type='core')
    print(f"  -> Thành công! Phiên bản: {response}")
except ApiException as e:
    print(f"  -> Lỗi API (mã {e.status}): {e.reason}")
except Exception as e:
    print(f"  -> Không kết nối được: {type(e).__name__} - {e}")

print("\n=== HOÀN TẤT KIỂM TRA ===")
