import sys
import pytest
from unittest.mock import patch, MagicMock
from core.power import (
    prevent_system_sleep,
    allow_system_sleep,
    shutdown_system,
    cancel_shutdown,
    is_shutdown_scheduled,
)


def test_prevent_system_sleep_non_windows():
    with patch('sys.platform', 'darwin'):
        assert prevent_system_sleep() is False


def test_prevent_system_sleep_windows_success():
    with patch('sys.platform', 'win32'), patch('ctypes.windll.kernel32.SetThreadExecutionState', return_value=1):
        assert prevent_system_sleep() is True


def test_prevent_system_sleep_windows_failure():
    with patch('sys.platform', 'win32'), patch('ctypes.windll.kernel32.SetThreadExecutionState', return_value=0):
        assert prevent_system_sleep() is False


def test_allow_system_sleep_non_windows():
    with patch('sys.platform', 'linux'):
        assert allow_system_sleep() is False


def test_allow_system_sleep_windows_success():
    with patch('sys.platform', 'win32'), patch('ctypes.windll.kernel32.SetThreadExecutionState', return_value=1):
        assert allow_system_sleep() is True


def test_shutdown_system_test_mode_simulation():
    res = shutdown_system(delay_seconds=60)
    assert res is True
    assert is_shutdown_scheduled() is True


def test_shutdown_system_non_windows():
    with patch('sys.platform', 'darwin'):
        assert shutdown_system(delay_seconds=60) is False


def test_shutdown_system_windows_success():
    mock_run = MagicMock()
    mock_run.returncode = 0
    with patch('sys.platform', 'win32'), \
         patch.dict('os.environ', {'HEXGATE_FORCE_REAL_SHUTDOWN': '1'}), \
         patch('subprocess.run', return_value=mock_run) as mock_sub:
        res = shutdown_system(delay_seconds=60, reason='Custom reason')
        assert res is True
        assert is_shutdown_scheduled() is True
        mock_sub.assert_called_once_with(
            ['shutdown', '/s', '/t', '60', '/c', 'Custom reason'],
            capture_output=True,
            text=True,
            check=False,
        )


def test_shutdown_system_windows_failure():
    mock_run = MagicMock()
    mock_run.returncode = 1
    mock_run.stderr = 'Access denied'
    with patch('sys.platform', 'win32'), \
         patch.dict('os.environ', {'HEXGATE_FORCE_REAL_SHUTDOWN': '1'}), \
         patch('subprocess.run', return_value=mock_run):
        res = shutdown_system(delay_seconds=30)
        assert res is False


def test_cancel_shutdown_test_mode_simulation():
    res = cancel_shutdown()
    assert res is True
    assert is_shutdown_scheduled() is False


def test_cancel_shutdown_non_windows():
    with patch('sys.platform', 'linux'):
        assert cancel_shutdown() is False


def test_cancel_shutdown_windows_success():
    mock_run = MagicMock(returncode=0)
    with patch('sys.platform', 'win32'), \
         patch.dict('os.environ', {'HEXGATE_FORCE_REAL_SHUTDOWN': '1'}), \
         patch('subprocess.run', return_value=mock_run) as mock_sub:
        res = cancel_shutdown()
        assert res is True
        assert is_shutdown_scheduled() is False
        mock_sub.assert_called_once_with(
            ['shutdown', '/a'],
            capture_output=True,
            text=True,
            check=False,
        )


def test_cancel_shutdown_windows_no_shutdown_in_progress():
    mock_run = MagicMock()
    mock_run.returncode = 1
    mock_run.stderr = 'Unable to abort the system shutdown because no shutdown was in progress.(1116)'
    with patch('sys.platform', 'win32'), \
         patch.dict('os.environ', {'HEXGATE_FORCE_REAL_SHUTDOWN': '1'}), \
         patch('subprocess.run', return_value=mock_run):
        res = cancel_shutdown()
        assert res is True
        assert is_shutdown_scheduled() is False
