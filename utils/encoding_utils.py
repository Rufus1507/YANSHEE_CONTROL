"""Encoding / string helpers (UTF-8 safe)."""


def safe_str(s) -> str:
    """Return a UTF-8 safe string, stripping un-decodable bytes."""
    return str(s).encode("utf-8", errors="ignore").decode("utf-8")
