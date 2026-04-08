# coding: utf-8
import os
import sys
import logging
import warnings
from typing import Optional, Dict, Any

# Tắt các cảnh báo không tương thích phiên bản (vd: urllib3/chardet) để console sạch hơn
warnings.filterwarnings("ignore", module="requests")
warnings.filterwarnings("ignore", category=UserWarning, message=".*doesn't match a supported version.*")

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
SDK_PATH = os.path.join(THIS_DIR, "Yan_ADK-latest", "Yan_ADK-latest")
if SDK_PATH not in sys.path:
    sys.path.insert(0, SDK_PATH)

try:
    import openadk
    from openadk.models.motions_operation import MotionsOperation
    from openadk.models.motions_parameter import MotionsParameter
    from openadk.rest import ApiException
except ImportError as exc:
    raise ImportError(
        "Cannot import openadk. Ensure Yan_ADK-latest/Yan_ADK-latest is present and the openadk package is available."
    ) from exc

# Cấu hình logging để dễ debug hơn
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("YanAPI")

class YanAPI:
    """Wrapper API OOP mạnh mẽ hơn cho Yanshee Robot với OpenADK."""
    
    def __init__(self, ip_address: str, port: int = 9090, api_version: str = "v1"):
        """Khởi tạo kết nối tới Yanshee Robot."""
        if not ip_address:
            raise ValueError("ip_address không được để trống")
        
        self.ip_address = ip_address
        self.port = port
        self.api_version = api_version
        self.host = f"http://{ip_address}:{port}/{api_version}"
        
        self._config = openadk.Configuration()
        self._config.host = self.host
        self._client = openadk.ApiClient(self._config)
        
        self._motions_api = openadk.MotionsApi(self._client)
        self._devices_api = openadk.DevicesApi(self._client)
        
        logger.info(f"YanAPI đã khởi tạo kết nối tới: {self.host}")

    def sync_play_motion(self, name: str, direction: Optional[str] = None, repeat: int = 1, speed: str = "normal") -> Dict[str, Any]:
        """Phát một motion trên Yanshee (vd: 'RaiseRightHand', 'walk')."""
        name = name.strip()
        if direction:
            direction = direction.strip().lower()

        logger.info(f"Gửi lệnh motion: {name} (repeat={repeat}, speed={speed}, direction={direction})")
        motion = MotionsParameter(name=name, direction=direction, repeat=repeat, speed=speed)
        operation = MotionsOperation(operation="start", motion=motion)
        
        try:
            response = self._motions_api.put_motions(operation)
            return self._as_dict(response)
        except ApiException as e:
            logger.error(f"Lỗi API khi chạy motion '{name}': {e.status} - {e.reason}")
            return {"error": e.reason, "status": e.status}
        except Exception as e:
            logger.error(f"Lỗi không xác định khi chạy motion '{name}': {e}")
            return {"error": str(e)}

    def stop_motion(self) -> Dict[str, Any]:
        """Dừng motion đang chạy hiện tại. (Bypass validate của openadk bằng requests)"""
        logger.info("Gửi lệnh dừng motion (stop)...")
        import requests
        try:
            url = f"{self.host}/motions"
            payload = {"operation": "stop"} # Yanshee firmware chuẩn yêu cầu chữ thường
            resp = requests.put(url, json=payload, timeout=5)
            logger.info(f"Robot Response (Stop): {resp.text}")
            return resp.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Lỗi API khi dừng motion: {e}")
            return {"error": str(e)}

    def get_motions_status(self) -> Any:
        """Lấy danh sách hoặc trạng thái motions hiện tại."""
        try:
            return self._as_dict(self._motions_api.get_motions())
        except Exception as e:
            logger.error(f"Lỗi khi lấy trạng thái motions: {e}")
            return {"error": str(e)}

    def get_motions_list(self) -> Any:
        """Lấy danh sách tất cả các motions (động tác) đã cài trên robot."""
        try:
            return self._as_dict(self._motions_api.get_motions_list())
        except Exception as e:
            logger.error(f"Lỗi khi lấy danh sách motions: {e}")
            return {"error": str(e)}

    def get_battery(self) -> Any:
        """Lấy phần trăm dung lượng pin."""
        try:
            return self._as_dict(self._devices_api.get_devices_battery())
        except Exception as e:
            logger.error(f"Lỗi khi lấy dung lượng pin: {e}")
            return {"error": str(e)}
            
    def get_device_volume(self) -> Any:
        """Lấy mức âm lượng của Yanshee."""
        try:
            return self._as_dict(self._devices_api.get_devices_volume())
        except Exception as e:
            logger.error(f"Lỗi khi lấy âm lượng: {e}")
            return {"error": str(e)}

    def set_device_volume(self, volume: int) -> Dict[str, Any]:
        """Cài đặt mức âm lượng của Yanshee (0-100)."""
        logger.info(f"Cài đặt âm lượng lên: {volume}")
        import requests
        try:
            volume = max(0, min(100, int(volume)))
            url = f"{self.host}/devices/volume"
            payload = {"volume": volume}
            resp = requests.put(url, json=payload, timeout=5)
            return resp.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Lỗi API khi cài đặt âm lượng: {e}")
            return {"error": str(e)}

    def play_music(self, name: str) -> Dict[str, Any]:
        """Phát nhạc (chỉ âm thanh, không nhảy)."""
        logger.info(f"Đang phát nhạc: {name}")
        import requests
        try:
            url = f"{self.host}/media/music"
            payload = {"operation": "start", "name": name}
            resp = requests.put(url, json=payload, timeout=5)
            return resp.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Lỗi API khi phát nhạc: {e}")
            return {"error": str(e)}

    def stop_music(self) -> Dict[str, Any]:
        """Dừng phát nhạc."""
        logger.info("Dừng nhạc...")
        import requests
        try:
            url = f"{self.host}/media/music"
            payload = {"operation": "stop"}
            resp = requests.put(url, json=payload, timeout=5)
            return resp.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Lỗi API khi dừng nhạc: {e}")
            return {"error": str(e)}

    def get_device_versions(self) -> Any:
        """Lấy phiên bản hệ thống của thiết bị."""
        try:
            return self._as_dict(self._devices_api.get_devices_versions(type='core'))
        except Exception as e:
            logger.error(f"Lỗi khi lấy phiên bản thiết bị: {e}")
            return {"error": str(e)}

    @staticmethod
    def _as_dict(obj: Any) -> Dict[str, Any]:
        """Helper để chuyển đổi response Object về kiểu Dictionary tiêu chuẩn."""
        if hasattr(obj, "to_dict"):
            return obj.to_dict()
        if isinstance(obj, dict):
            return obj
        # Bổ sung key 'data' vì test_yanshee.py cho thấy response có trường .data
        return {key: getattr(obj, key) for key in ("code", "msg", "data") if hasattr(obj, key)}


# ==============================================================================
# HỖ TRỢ TƯƠNG THÍCH NGƯỢC (Backward Compatibility)
# Giữ lại các hàm cục bộ cũ lỡ code của bạn ở file khác gọi đến trực tiếp:
# ==============================================================================
_api_instance = None
_client_instance = None
_config = None

def set_robot_ip(ip_address: str, port: int = 9090, api_version: str = "v1"):
    """(Hàm cũ) Khởi tạo cấu hình cho robot."""
    global _api_instance, _config, _client_instance
    if not ip_address:
        raise ValueError("ip_address must not be empty")

    host = f"http://{ip_address}:{port}/{api_version}"
    _config = openadk.Configuration()
    _config.host = host
    _client_instance = openadk.ApiClient(_config)
    _api_instance = openadk.MotionsApi(_client_instance)
    return _api_instance

def sync_play_motion(name: str, direction: Optional[str] = None, repeat: int = 1, speed: str = "normal"):
    """(Hàm cũ) Chạy motion dạng đồng bộ dựa trên API Instance toàn cục."""
    if _api_instance is None:
        raise RuntimeError("YanAPI is not configured. Call set_robot_ip() first.")

    if isinstance(name, str):
        name = name.strip()
    if isinstance(direction, str):
        direction = direction.strip().lower()

    motion = MotionsParameter(name=name, direction=direction, repeat=repeat, speed=speed)
    operation = MotionsOperation(operation="start", motion=motion)
    
    try:
        response = _api_instance.put_motions(operation)
        return _as_dict_global(response)
    except ApiException as e:
        return {"error": e.reason, "status": e.status}
    except Exception as e:
        return {"error": str(e)}

def _as_dict_global(obj):
    """(Hàm cũ)"""
    if hasattr(obj, "to_dict"):
        return obj.to_dict()
    if isinstance(obj, dict):
        return obj
    return {key: getattr(obj, key) for key in ("code", "msg", "data") if hasattr(obj, key)}