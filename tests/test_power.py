import unittest
from unittest.mock import patch, MagicMock
from core.power import (
    prevent_system_sleep,
    allow_system_sleep,
    ES_CONTINUOUS,
    ES_SYSTEM_REQUIRED,
)


class TestPowerManagement(unittest.TestCase):
    @patch("sys.platform", "win32")
    @patch("ctypes.windll")
    def test_prevent_system_sleep_success_windows(self, mock_windll):
        mock_kernel32 = MagicMock()
        mock_kernel32.SetThreadExecutionState.return_value = 1
        mock_windll.kernel32 = mock_kernel32

        result = prevent_system_sleep()
        self.assertTrue(result)
        mock_kernel32.SetThreadExecutionState.assert_called_once_with(
            ES_CONTINUOUS | ES_SYSTEM_REQUIRED
        )

    @patch("sys.platform", "win32")
    @patch("ctypes.windll")
    def test_allow_system_sleep_success_windows(self, mock_windll):
        mock_kernel32 = MagicMock()
        mock_kernel32.SetThreadExecutionState.return_value = 1
        mock_windll.kernel32 = mock_kernel32

        result = allow_system_sleep()
        self.assertTrue(result)
        mock_kernel32.SetThreadExecutionState.assert_called_once_with(ES_CONTINUOUS)

    @patch("sys.platform", "linux")
    def test_non_windows_platform(self):
        self.assertFalse(prevent_system_sleep())
        self.assertFalse(allow_system_sleep())


if __name__ == "__main__":
    unittest.main()
