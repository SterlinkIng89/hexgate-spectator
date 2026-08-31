from unittest.mock import patch
import core.hexgate
from core.version import __version__
from core.hexgate.engine import stop_bot
from core.obs_controller import obs_controller, OBSController
from core.hexgate.state import bot_state


def test_hexgate_version():
    assert core.hexgate.__version__ == __version__
    assert core.hexgate.__version__ == "2.1.0"


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


def test_start_bot_configures_youtube():
    from core.hexgate.engine import start_bot
    from core.youtube_manager import youtube_manager

    config = {
        "discord_webhook_url": "https://discord.com/api/webhooks/bot_test",
        "discord_enabled": True,
        "invite_only": False,
        "lobby_name": "TEST"
    }

    with patch("core.hexgate.engine.prevent_system_sleep"), \
         patch.object(obs_controller, "configure"), \
         patch.object(youtube_manager, "configure") as mock_conf_yt, \
         patch("core.hexgate.state.bot_state.update_gui_status"):
        start_bot(lambda s: None, config)
        mock_conf_yt.assert_called_once_with(config)

