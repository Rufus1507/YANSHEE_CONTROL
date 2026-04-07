import openadk

# Cấu hình kết nối
ROBOT_IP = "10.33.21.75"
BASE_URL = f"http://{ROBOT_IP}:9090/v1"

configuration = openadk.Configuration()
configuration.host = BASE_URL
client = openadk.ApiClient(configuration)

# Lấy danh sách motions
motions_api = openadk.MotionsApi(client)

# Lấy trạng thái motions hiện tại
print("=== TRẠNG THÁI MOTION HIỆN TẠI ===")
response = motions_api.get_motions()
print(response)

# In chi tiết từng trường
print("\n=== CHI TIẾT ===")
print(f"Type: {type(response)}")
print(f"Response object: {response}")

# Thử in các thuộc tính
if hasattr(response, 'data') and response.data:
    print(f"Motion name: {response.data.name}")
    print(f"Status: {response.data.status}")
    print(f"Timestamp: {response.data.timestamp}")