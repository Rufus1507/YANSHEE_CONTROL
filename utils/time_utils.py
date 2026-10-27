"""Time-related utilities."""
import time
from datetime import datetime


def now_seconds() -> float:
    """Current time as a Unix timestamp (float seconds)."""
    return time.time()


def now_iso() -> str:
    """Current local time formatted as ISO-like string for display / logging."""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
