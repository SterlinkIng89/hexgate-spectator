import unittest
from unittest.mock import patch, MagicMock

# We need to patch prevent_system_sleep, allow_system_sleep
from core.hexgate.engine import stop_bot
from core.obs_controller import obs_controller
from core.hexgate.state import bot_state

class TestEngine(unittest.TestCase):
    @patch('core.hexgate.engine.allow_system_sleep')
    @patch('core.obs_controller.OBSController.stop_stream')
    @patch('core.obs_controller.OBSController.disconnect')
    @patch('core.obs_controller.OBSController.stop_scheduler')
    @patch('core.obs_controller.OBSController.is_current_time_in_range')
    def test_stop_bot_stops_stream_outside_schedule(self, mock_is_in_range, mock_stop_scheduler, mock_disconnect, mock_stop_stream, mock_allow_system_sleep):
        # Setup state
        bot_state.bot_active = True
        obs_controller.schedule_enabled = False
        mock_is_in_range.return_value = False
        
        # When bot is stopped
        stop_bot()
        
        # Then the stream should be explicitly stopped, synchronously
        mock_stop_stream.assert_called_once()
        mock_disconnect.assert_called_once()
        
        self.assertFalse(bot_state.bot_active)

    @patch('core.hexgate.engine.allow_system_sleep')
    @patch('core.obs_controller.OBSController.stop_stream')
    @patch('core.obs_controller.OBSController.disconnect')
    @patch('core.obs_controller.OBSController.stop_scheduler')
    @patch('core.obs_controller.OBSController.is_current_time_in_range')
    def test_stop_bot_keeps_stream_in_schedule(self, mock_is_in_range, mock_stop_scheduler, mock_disconnect, mock_stop_stream, mock_allow_system_sleep):
        # Setup state
        bot_state.bot_active = True
        obs_controller.schedule_enabled = True
        mock_is_in_range.return_value = True
        
        # When bot is stopped
        stop_bot()
        
        # Then the stream should NOT be stopped
        mock_stop_stream.assert_not_called()
        mock_disconnect.assert_called_once()
        
        self.assertFalse(bot_state.bot_active)

if __name__ == '__main__':
    unittest.main()
