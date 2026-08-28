"""
Windows Power Management Helper.

Prevents the operating system from entering Sleep / Standby mode while the
bot and scheduled stream monitor are actively running, ensuring background
daemon threads are not suspended.
"""

import os
import sys
import logging
import ctypes
import subprocess

logger = logging.getLogger(__name__)

# Windows SetThreadExecutionState Flags
ES_CONTINUOUS: int = 0x80000000
ES_SYSTEM_REQUIRED: int = 0x00000001

_shutdown_scheduled: bool = False


def _is_test_environment() -> bool:
    """Returns True if running inside pytest or automated testing."""
    return bool(
        "pytest" in sys.modules
        or os.environ.get("PYTEST_CURRENT_TEST")
        or os.environ.get("HEXGATE_TESTING")
    )


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


def shutdown_system(delay_seconds: int = 60, reason: str = "Hexgate Spectator stream ended") -> bool:
    """
    Schedules an operating system shutdown with a countdown delay.
    Returns True if successfully scheduled, False otherwise.
    """
    global _shutdown_scheduled
    if sys.platform != "win32":
        logger.warning("[Power] System shutdown is only supported on Windows.")
        return False

    delay = max(0, int(delay_seconds))
    if _is_test_environment() and not os.environ.get("HEXGATE_FORCE_REAL_SHUTDOWN"):
        logger.info(f"[Power] (Test Mode) Simulated shutdown in {delay} seconds.")
        _shutdown_scheduled = True
        return True

    try:
        cmd = ["shutdown", "/s", "/t", str(delay), "/c", reason]
        logger.warning(
            f"[Power] Scheduling system shutdown in {delay} seconds (Reason: {reason})..."
        )
        res = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if res.returncode == 0:
            _shutdown_scheduled = True
            logger.info(f"[Power] System shutdown scheduled successfully in {delay} seconds.")
            return True
        else:
            logger.error(f"[Power] Failed to schedule shutdown (code {res.returncode}): {res.stderr.strip()}")
            return False
    except Exception as e:
        logger.error(f"[Power] Error executing shutdown command: {e}")
        return False


def cancel_shutdown() -> bool:
    """
    Aborts a previously scheduled operating system shutdown.
    Returns True if successfully cancelled or no shutdown was pending, False on error.
    """
    global _shutdown_scheduled
    if sys.platform != "win32":
        return False

    if _is_test_environment() and not os.environ.get("HEXGATE_FORCE_REAL_SHUTDOWN"):
        logger.info("[Power] (Test Mode) Simulated shutdown cancellation.")
        _shutdown_scheduled = False
        return True

    try:
        logger.info("[Power] Cancelling scheduled system shutdown...")
        res = subprocess.run(["shutdown", "/a"], capture_output=True, text=True, check=False)
        _shutdown_scheduled = False
        if res.returncode == 0:
            logger.info("[Power] System shutdown was successfully cancelled.")
            return True
        else:
            err_msg = res.stderr.strip().lower()
            # If code 1116 (No shutdown was in progress), treat as clean success
            if "1116" in err_msg or "no shutdown" in err_msg or "unable to abort" in err_msg:
                logger.debug(f"[Power] No shutdown was in progress to cancel.")
                return True
            logger.warning(f"[Power] Abort shutdown returned code {res.returncode}: {res.stderr.strip()}")
            return False
    except Exception as e:
        logger.error(f"[Power] Error cancelling shutdown: {e}")
        return False


def is_shutdown_scheduled() -> bool:
    """Returns True if a system shutdown was initiated by Hexgate Spectator."""
    return _shutdown_scheduled
