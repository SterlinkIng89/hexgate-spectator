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
