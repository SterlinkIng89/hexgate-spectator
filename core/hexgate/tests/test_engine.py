from unittest.mock import patch
from core.hexgate.engine import stop_bot
from core.obs_controller import obs_controller, OBSController
from core.hexgate.state import bot_state


def test_stop_bot_invokes_obs_on_bot_stop():
    bot_state.bot_active = True
    with patch.object(obs_controller, 'on_bot_stop') as mock_on_bot_stop, \
         patch('core.hexgate.engine.allow_system_sleep'):
        stop_bot()
        mock_on_bot_stop.assert_called_once()
        assert not bot_state.bot_active


def test_obs_on_bot_stop_terminates_stream_outside_schedule():
    controller = OBSController()
    controller.enabled = True
    controller.schedule_enabled = False

    with patch.object(controller, 'stop_scheduler') as mock_stop_sched, \
         patch.object(controller, 'is_current_time_in_range', return_value=False), \
         patch.object(controller, 'stop_stream') as mock_stop_stream, \
         patch.object(controller, 'disconnect') as mock_disconnect:
        controller.on_bot_stop()

        mock_stop_sched.assert_called_once()
        mock_stop_stream.assert_called_once()
        mock_disconnect.assert_called_once()


def test_obs_on_bot_stop_keeps_stream_within_schedule():
    controller = OBSController()
    controller.enabled = True
    controller.schedule_enabled = True

    with patch.object(controller, 'stop_scheduler') as mock_stop_sched, \
         patch.object(controller, 'is_current_time_in_range', return_value=True), \
         patch.object(controller, 'stop_stream') as mock_stop_stream, \
         patch.object(controller, 'disconnect') as mock_disconnect:
        controller.on_bot_stop()

        mock_stop_sched.assert_called_once()
        mock_stop_stream.assert_not_called()
        mock_disconnect.assert_called_once()
