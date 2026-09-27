import sys
import os

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _PROJECT_ROOT)

from recognition.face_database import FaceDatabase

print("Kiểm tra Database...")
db = FaceDatabase()
stats = db.count_stats()

print("Kết quả:")
print(f" - Tổng số Users: {stats['users']}")
print(f" - Tổng số Embeddings: {stats['embeddings']}")
