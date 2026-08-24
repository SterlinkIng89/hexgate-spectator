"""
Windows Power Management Helper.

Prevents the operating system from entering Sleep / Standby mode while the
bot and scheduled stream monitor are actively running, ensuring background
daemon threads are not suspended.
"""

import sys
import logging
import ctypes

logger = logging.getLogger(__name__)

# Windows SetThreadExecutionState Flags
ES_CONTINUOUS: int = 0x80000000
ES_SYSTEM_REQUIRED: int = 0x00000001


def prevent_system_sleep() -> bool:
    """
    Prevents the OS from going to sleep while allowing display power down.
    Returns True if successfully set on Windows, False otherwise.
    """
    if sys.platform != "win32":
        logger.debug("[Power] Sleep prevention is only supported on Windows.")
        return False

    try:
        result = ctypes.windll.kernel32.SetThreadExecutionState(
            ES_CONTINUOUS | ES_SYSTEM_REQUIRED
        )
        if result == 0:
            logger.warning("[Power] Failed to set thread execution state to prevent sleep.")
            return False
        logger.info("[Power] Windows sleep prevention enabled (ES_CONTINUOUS | ES_SYSTEM_REQUIRED).")
        return True
    except Exception as e:
        logger.error(f"[Power] Error setting sleep prevention: {e}")
        return False


def allow_system_sleep() -> bool:
    """
    Restores normal system power/sleep behavior.
    Returns True if successfully set on Windows, False otherwise.
    """
    if sys.platform != "win32":
        return False

    try:
        result = ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS)
        if result == 0:
            logger.warning("[Power] Failed to restore normal thread execution state.")
            return False
        logger.info("[Power] Windows sleep prevention disabled (ES_CONTINUOUS restored).")
        return True
    except Exception as e:
        logger.error(f"[Power] Error restoring sleep behavior: {e}")
        return False
