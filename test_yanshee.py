import requests

print("Đang gọi trực tiếp API Yanshee bằng thư viện requests...")
url = "http://10.33.21.75:9090/v1/motions/list"

try:
    response = requests.get(url, timeout=5)
    data = response.json()
    
    if "data" in data and "motions" in data["data"]:
        motions = data["data"]["motions"]
        if motions:
            print(f"\n=> Đã tìm thấy {len(motions)} động tác:")
            for m in motions:
                print(f"  - {m}")
        else:
            print("\nKhông có động tác nào (list motions rỗng).")
    else:
        print("\nCấu trúc JSON không như dự kiến:")
        print(data)

except Exception as e:
    print(f"\nLỗi khi gọi API: {e}")
