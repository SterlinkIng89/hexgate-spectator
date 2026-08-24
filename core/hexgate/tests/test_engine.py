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
    def test_stop_bot_stops_stream(self, mock_stop_scheduler, mock_disconnect, mock_stop_stream, mock_allow_system_sleep):
        # Setup state
        bot_state.bot_active = True
        bot_state.is_searching = True
        
        # When bot is stopped
        stop_bot()
        
        # Then the stream should be explicitly stopped, synchronously
        mock_stop_stream.assert_called_once()
        mock_disconnect.assert_called_once()
        
        self.assertFalse(bot_state.bot_active)

if __name__ == '__main__':
    unittest.main()
