import pytest
from unittest.mock import MagicMock, patch
from core.obs_controller import OBSController


def test_obs_controller_configure_and_defaults():
    controller = OBSController()
    assert controller.profile == ""
    assert controller.scene_collection == ""
    assert not hasattr(controller, "scene")

    controller.configure({
        "obs_enabled": True,
        "obs_host": "192.168.1.50",
        "obs_port": "4456",
        "obs_password": "secret",
        "obs_profile": "Stream Profile",
        "obs_scene_collection": "Main Layout",
        "obs_scene": "ObsoleteScene",  # Should be ignored
    })

    assert controller.enabled is True
    assert controller.host == "192.168.1.50"
    assert controller.port == 4456
    assert controller.password == "secret"
    assert controller.profile == "Stream Profile"
    assert controller.scene_collection == "Main Layout"
    assert not hasattr(controller, "scene")


def test_obs_controller_get_profiles_success():
    controller = OBSController()
    controller.enabled = True
    
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.profiles = ["Default", "Scrims 1080p", "Recording"]
    mock_client.get_profile_list.return_value = mock_response

    with patch.object(controller, "_ensure_connected", return_value=True):
        controller._client = mock_client
        profiles = controller.get_profiles()
        assert profiles == ["Default", "Scrims 1080p", "Recording"]
        mock_client.get_profile_list.assert_called_once()


def test_obs_controller_get_profiles_not_connected():
    controller = OBSController()
    with patch.object(controller, "_ensure_connected", return_value=False):
        profiles = controller.get_profiles()
        assert profiles == []


def test_obs_controller_get_profiles_error_handling():
    controller = OBSController()
    mock_client = MagicMock()
    mock_client.get_profile_list.side_effect = Exception("WebSocket closed 10061")

    with patch.object(controller, "_ensure_connected", return_value=True):
        controller._client = mock_client
        profiles = controller.get_profiles()
        assert profiles == []
        assert controller._client is None  # Connection disconnected on unreachable error


def test_obs_controller_get_scene_collections_success():
    controller = OBSController()
    controller.enabled = True

    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.scene_collections = ["Scrims Overlay", "SoloQ Layout"]
    mock_client.get_scene_collection_list.return_value = mock_response

    with patch.object(controller, "_ensure_connected", return_value=True):
        controller._client = mock_client
        collections = controller.get_scene_collections()
        assert collections == ["Scrims Overlay", "SoloQ Layout"]
        mock_client.get_scene_collection_list.assert_called_once()


def test_obs_controller_get_scene_collections_not_connected():
    controller = OBSController()
    with patch.object(controller, "_ensure_connected", return_value=False):
        collections = controller.get_scene_collections()
        assert collections == []


def test_obs_controller_apply_scene_and_start_does_not_set_scene():
    controller = OBSController()
    controller.profile = "TestProfile"
    controller.scene_collection = "TestCollection"

    with patch.object(controller, "get_stream_status", return_value={"active": False}):
        with patch.object(controller, "set_profile") as mock_prof:
            with patch.object(controller, "set_scene_collection") as mock_col:
                with patch.object(controller, "start_stream") as mock_start:
                    controller._apply_scene_and_start()
                    mock_prof.assert_called_once_with("TestProfile")
                    mock_col.assert_called_once_with("TestCollection")
                    mock_start.assert_called_once()


def test_obs_controller_configure_shutdown():
    controller = OBSController()
    assert controller.shutdown_enabled is False
    assert controller.shutdown_delay == 60

    controller.configure({
        "obs_shutdown_enabled": True,
        "obs_shutdown_delay": 120,
    })
    assert controller.shutdown_enabled is True
    assert controller.shutdown_delay == 120


def test_obs_controller_stop_stream_triggers_shutdown():
    controller = OBSController()
    controller.enabled = True
    controller.shutdown_enabled = True
    controller.shutdown_delay = 45

    mock_client = MagicMock()
    mock_client.stop_stream.return_value = None

    with patch.object(controller, "_ensure_connected", return_value=True), \
         patch("core.youtube_manager.youtube_manager.complete_broadcast_async") as mock_yt, \
         patch("core.obs_controller.shutdown_system") as mock_shutdown:
        controller._client = mock_client
        res = controller.stop_stream(trigger_shutdown=True)
        assert res is True
        mock_client.stop_stream.assert_called_once()
        mock_yt.assert_called_once()
        mock_shutdown.assert_called_once_with(delay_seconds=45, reason="Hexgate Spectator stream ended")


def test_obs_controller_stop_stream_disabled_shutdown():
    controller = OBSController()
    controller.enabled = True
    controller.shutdown_enabled = False

    mock_client = MagicMock()
    mock_client.stop_stream.return_value = None

    with patch.object(controller, "_ensure_connected", return_value=True), \
         patch("core.youtube_manager.youtube_manager.complete_broadcast_async") as mock_yt, \
         patch("core.obs_controller.shutdown_system") as mock_shutdown:
        controller._client = mock_client
        res = controller.stop_stream(trigger_shutdown=True)
        assert res is True
        mock_yt.assert_called_once()
        mock_shutdown.assert_not_called()


def test_obs_controller_on_bot_stop_does_not_trigger_shutdown():
    controller = OBSController()
    controller.enabled = True
    controller.shutdown_enabled = True
    controller.schedule_enabled = False

    with patch.object(controller, "stop_stream") as mock_stop:
        controller.on_bot_stop()
        mock_stop.assert_called_once_with(trigger_shutdown=False)


def test_obs_controller_get_stream_status_reconnecting_transition():
    controller = OBSController()
    controller.enabled = True
    
    mock_client = MagicMock()
    mock_status = MagicMock()
    mock_status.output_active = True
    mock_status.output_reconnecting = True
    mock_status.output_timecode = "00:01:23"
    mock_client.get_stream_status.return_value = mock_status

    with patch.object(controller, "_ensure_connected", return_value=True), \
         patch("core.youtube_manager.youtube_manager.on_stream_start_async") as mock_yt_start:
        controller._client = mock_client
        res = controller.get_stream_status()
        assert res["active"] is True
        assert res["reconnecting"] is True
        assert res["timecode"] == "00:01:23"
        mock_yt_start.assert_called_once()


def test_obs_controller_start_stream_triggers_youtube_start():
    controller = OBSController()
    controller.enabled = True

    mock_client = MagicMock()
    mock_client.start_stream.return_value = None

    with patch.object(controller, "_ensure_connected", return_value=True), \
         patch("core.youtube_manager.youtube_manager.on_stream_start_async") as mock_yt_start:
        controller._client = mock_client
        res = controller.start_stream()
        assert res is True
        mock_client.start_stream.assert_called_once()
        mock_yt_start.assert_called_once()

