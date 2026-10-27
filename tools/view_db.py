import sqlite3
import os
import sys

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _PROJECT_ROOT)

from config import DATABASE_PATH

def show_data():
    if not os.path.exists(DATABASE_PATH):
        print(f"Không tìm thấy database tại: {DATABASE_PATH}")
        return

    print(f"\n--- ĐANG ĐỌC DATABASE TẠI: {DATABASE_PATH} ---\n")
    conn = sqlite3.connect(DATABASE_PATH)
    cur = conn.cursor()

    cur.execute("SELECT id, user_id, full_name, role FROM users")
    users = cur.fetchall()
    print("1. BẢNG USERS (Thông tin người dùng đã đăng ký):")
    if not users:
        print("  (Chưa có người dùng nào)")
    for u in users:
        print(f"  - ID DB: {u[0]} | Mã User: {u[1]} | Tên: {u[2]} | Role: {u[3]}")

    print("\n2. BẢNG FACE_EMBEDDINGS (Vector khuôn mặt đại diện):")
    cur.execute("SELECT id, user_id, angle_label, length(embedding) FROM face_embeddings")
    embeddings = cur.fetchall()
    if not embeddings:
        print("  (Chưa có vector khuôn mặt nào)")
    for e in embeddings:
        print(f"  - ID DB: {e[0]} | Mã User: {e[1]} | Góc mặt: {e[2]} | Dung lượng Binary: {e[3]} bytes")

    conn.close()
    print("\n=======================================================")
    print("Giải thích:")
    print("- Thay vì lưu ảnh JPG/PNG (dễ lộ quyền riêng tư), hệ thống biến đổi")
    print("  ảnh thành một file mã hóa nhị phân (Binary Blob) và lưu thẳng")
    print("  vào cột 'embedding' trong file SQLite này.")

if __name__ == "__main__":
    show_data()
