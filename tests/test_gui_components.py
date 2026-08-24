import pytest
from unittest.mock import patch
import customtkinter as ctk
from gui.components.status_cards import StatusCards
from gui.components.youtube_panel import YouTubePanel
from gui.components.collapsible_frame import CollapsibleFrame
from gui.components.console_toolbar import ConsoleToolbar
from gui.components.status_footer import StatusFooter
from gui.components.lol_settings_form import LolSettingsForm
from gui.components.obs_settings_form import ObsSettingsForm
from gui.components.tooltip import Tooltip

SURFACE_COLOR = "#1e1e1e"
BORDER_COLOR = "#333333"

@pytest.fixture(scope="module")
def tk_root():
    root = ctk.CTk()
    yield root
    root.destroy()

def test_status_cards_style(tk_root):
    comp = StatusCards(tk_root)
    assert comp.cget("fg_color") == "transparent"
    assert comp.bot_card.cget("fg_color") == SURFACE_COLOR
    assert comp.bot_card.cget("border_color") == BORDER_COLOR
    assert comp.bot_card.cget("border_width") == 1
    assert comp.stream_card.cget("fg_color") == SURFACE_COLOR
    assert comp.stream_card.cget("border_color") == BORDER_COLOR
    assert comp.stream_card.cget("border_width") == 1

def test_status_footer_style(tk_root):
    comp = StatusFooter(tk_root, version="1.0")
    assert comp.cget("fg_color") == SURFACE_COLOR

def test_youtube_panel_style(tk_root):
    comp = YouTubePanel(tk_root)
    assert comp.cget("fg_color") == SURFACE_COLOR
    assert comp.cget("border_color") == BORDER_COLOR
    assert comp.cget("border_width") == 1

def test_collapsible_frame_style(tk_root):
    comp = CollapsibleFrame(tk_root, title="Test")
    assert comp.cget("fg_color") == SURFACE_COLOR
    assert comp.cget("border_color") == BORDER_COLOR
    assert comp.cget("border_width") == 1

def test_settings_forms_style(tk_root):
    comp1 = LolSettingsForm(tk_root)
    assert comp1.cget("fg_color") == SURFACE_COLOR
    assert comp1.cget("border_color") == BORDER_COLOR
    assert comp1.cget("border_width") == 1
    
    comp2 = ObsSettingsForm(tk_root)
    assert comp2.cget("fg_color") == SURFACE_COLOR
    assert comp2.cget("border_color") == BORDER_COLOR
    assert comp2.cget("border_width") == 1


def test_youtube_panel_auth_state_displays_channel_name(tk_root):
    with patch("gui.components.youtube_panel.youtube_manager") as mock_yt:
        mock_yt.is_authenticated.return_value = True
        mock_yt.channel_name = "Hexgate Official"
        comp = YouTubePanel(tk_root)
        comp.refresh_auth_state()
        assert comp.account_label.cget("text") == "YouTube: Hexgate Official"
        assert comp.btn_auth.cget("text") == "Disconnect"


def test_youtube_panel_auth_state_displays_disconnected(tk_root):
    with patch("gui.components.youtube_panel.youtube_manager") as mock_yt:
        mock_yt.is_authenticated.return_value = False
        mock_yt.authenticate.return_value = False
        comp = YouTubePanel(tk_root)
        comp.refresh_auth_state()
        assert comp.account_label.cget("text") == "YouTube: Disconnected"
        assert comp.btn_auth.cget("text") == "Link Account"


def test_tooltip_lifecycle(tk_root):
    lbl = ctk.CTkLabel(tk_root, text="Target")
    tip = Tooltip(lbl, text="Sample hint", delay_ms=10)
    assert tip.text == "Sample hint"
    assert tip._tip_window is None

    # Simulate hover show and hide
    tip._show()
    assert tip._tip_window is not None
    tip._hide()
    assert tip._tip_window is None


def test_lol_settings_form_camera_delay_clarification(tk_root):
    form = LolSettingsForm(tk_root)
    assert form.lbl_camera_delay.cget("text") == "Camera Delay (s):"
    assert form.help_camera_delay.cget("text") == "?"
    assert form.entry_delay.cget("placeholder_text") == "e.g.: 3"

    form.load_config({"camera_delay": "5.5"})
    assert form.entry_delay.get() == "5.5"
    assert form.get_config()["camera_delay"] == "5.5"


def test_lol_settings_form_runtime_config_validation(tk_root):
    form = LolSettingsForm(tk_root)

    # Valid positive number
    form.load_config({"camera_delay": "4.5"})
    assert form.get_runtime_config()["camera_delay"] == 4.5

    # Invalid non-numeric string falls back to default 3.0
    form.entry_delay.delete(0, "end")
    form.entry_delay.insert(0, "not-a-number")
    assert form.get_runtime_config()["camera_delay"] == 3.0

    # Negative number falls back to default 3.0
    form.entry_delay.delete(0, "end")
    form.entry_delay.insert(0, "-5")
    assert form.get_runtime_config()["camera_delay"] == 3.0


def test_obs_settings_form_structure_and_comboboxes(tk_root):
    form = ObsSettingsForm(tk_root)
    assert not hasattr(form, "entry_obs_scene")
    assert hasattr(form, "combo_obs_profile")
    assert hasattr(form, "combo_obs_scene_collection")
    assert hasattr(form, "btn_scan_obs")
    assert form.btn_scan_obs.cget("text") == "Scan OBS"

    # Test load_config and get_config
    form.load_config({
        "obs_enabled": 1,
        "obs_host": "127.0.0.1",
        "obs_port": "4455",
        "obs_password": "pass",
        "obs_profile": "Scrims",
        "obs_scene_collection": "Scrims Layout",
    })

    assert form.combo_obs_profile.get() == "Scrims"
    assert form.combo_obs_scene_collection.get() == "Scrims Layout"
    cfg = form.get_config()
    assert cfg["obs_profile"] == "Scrims"
    assert cfg["obs_scene_collection"] == "Scrims Layout"
    assert "obs_scene" not in cfg


def test_obs_settings_form_scan_results_application(tk_root):
    form = ObsSettingsForm(tk_root)
    form.combo_obs_profile.set("")
    form.combo_obs_scene_collection.set("")

    profiles = ["Default", "1080p Stream", "Recording"]
    scenes = ["Main Overlay", "Secondary Layout"]

    form._apply_scan_results(profiles, scenes)

    assert form.combo_obs_profile.cget("values") == profiles
    assert form.combo_obs_profile.get() == "Default"
    assert form.combo_obs_scene_collection.cget("values") == scenes
    assert form.combo_obs_scene_collection.get() == "Main Overlay"
    assert form.btn_scan_obs.cget("text") == "Scan OBS"


