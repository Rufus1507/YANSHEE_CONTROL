# pyrefly: ignore [missing-import]
import cv2
import os

def test_cameras():
    print("Scanning cameras...")
    for i in range(5):
        cap = cv2.VideoCapture(i)
        if not cap.isOpened():
            print(f"Camera {i} cannot be opened.")
            continue
        
        ret, frame = cap.read()
        if ret:
            h, w = frame.shape[:2]
            print(f"Camera {i} is working. Resolution: {w}x{h}")
            cv2.imwrite(f"camera_{i}_test.jpg", frame)
        else:
            print(f"Camera {i} opened but cannot read a frame.")
        cap.release()

if __name__ == "__main__":
    test_cameras()
