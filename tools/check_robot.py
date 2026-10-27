import sys
import os

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _PROJECT_ROOT)

from config import ROBOT_IP, ROBOT_PORT
from robot.yanshee_client import YansheeClient

print(f"Kiểm tra Robot Yanshee tại IP: {ROBOT_IP}:{ROBOT_PORT}")
client = YansheeClient(ROBOT_IP, ROBOT_PORT)

if client.ping():
    print(" Kết nối Robot thành công!")
    print(" Đang thử gửi motion 'wave'...")
    if client.send_motion("wave"):
        print(" Gửi motion thành công!")
    else:
        print(" Gửi motion thất bại!")
else:
    print(" Lỗi: Không thể kết nối tới Robot. Vui lòng kiểm tra IP và mạng Wi-Fi.")
