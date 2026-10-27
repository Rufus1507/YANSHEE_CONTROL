"""
Tool: Reset all face embeddings after changing the recognition model.

Usage:
    python tools/reset_embeddings.py

This will:
  1. Delete ALL face embeddings from the database.
  2. List all registered users who need to be re-registered.
  3. Print instructions for re-registration.

IMPORTANT: Run this when you change the embedding model (e.g. from "code chay"
to ArcFace, or from one ArcFace model to another).
"""
import sys
import os

# Ensure project root is on sys.path
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

sys.stdout.reconfigure(encoding='utf-8')

from recognition.face_database import FaceDatabase
from config import FACE_MODEL_NAME


def main():
    db = FaceDatabase()

    print(f"\n{'='*60}")
    print("  RESET FACE EMBEDDINGS")
    print(f"{'='*60}")

    stats = db.count_stats()
    print(f"\nDatabase hiện tại:")
    print(f"  Users      : {stats['users']}")
    print(f"  Embeddings : {stats['embeddings']}")
    print(f"  Model mới  : {FACE_MODEL_NAME}")

    if stats['embeddings'] == 0:
        print("\nKhông có embedding nào để xóa.")
        return

    # Confirm
    print(f"\n⚠️  CẢNH BÁO: Thao tác này sẽ XÓA TẤT CẢ {stats['embeddings']} embeddings!")
    print("  Tất cả user đã đăng ký sẽ cần đăng ký lại khuôn mặt.")
    confirm = input("\nNhập 'YES' để xác nhận: ").strip()

    if confirm != "YES":
        print("Đã hủy.")
        return

    # Delete all embeddings
    deleted = db.delete_all_embeddings()
    print(f"\n✅ Đã xóa {deleted} embeddings.")

    # List users that need re-registration
    users = db.get_all_users()
    if users:
        print(f"\nDanh sách {len(users)} user cần đăng ký lại:")
        print(f"{'─'*50}")
        for u in users:
            print(f"  {u['user_id']}  |  {u['full_name']}  |  {u['role']}")
        print(f"{'─'*50}")

        print(f"\nĐể đăng ký lại từng user, chạy:")
        print(f'  python -m recognition.register_user --name "Tên User" --role Student')

    print(f"\n{'='*60}")
    print("  HOÀN TẤT — Hãy đăng ký lại khuôn mặt cho tất cả user")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
