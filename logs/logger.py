from loguru import logger as _logger
import sys
import os

# Ensure logs directory exists
LOG_DIR = os.path.join(os.path.dirname(__file__), "..", "logs")
os.makedirs(LOG_DIR, exist_ok=True)

# Configure Loguru: console (INFO) + file (DEBUG)
_logger.remove()
_logger.add(sys.stderr, level="INFO", colorize=True)
_logger.add(os.path.join(LOG_DIR, "system.log"), rotation="10 MB", level="DEBUG", enqueue=True)

def get_logger(name: str = __name__):
    """Return a Loguru logger bound with the module name for consistent tagging."""
    return _logger.bind(module=name)
