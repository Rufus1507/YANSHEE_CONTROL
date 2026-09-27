import cv2
import sys
import os

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _PROJECT_ROOT)

from config import CAMERA_INDEX

print(f"Kiểm tra Camera (Index: {CAMERA_INDEX})...")
cap = cv2.VideoCapture(CAMERA_INDEX)

if not cap.isOpened():
    print(" Lỗi: Không thể mở camera!")
    sys.exit(1)

print(" Camera đang mở. Nhấn 'q' để thoát.")
while True:
    ret, frame = cap.read()
    if not ret:
        print(" Lỗi: Không đọc được frame!")
        break
    
    cv2.imshow("Camera Test", frame)
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()
