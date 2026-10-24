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
from gui.entry_utils import set_entry_text
from core.version import __version__

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
    comp = StatusFooter(tk_root)
    assert comp.cget("fg_color") == SURFACE_COLOR
    assert comp.version_label.cget("text") == f"v{__version__}"

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


def test_collapsible_frame_summary_badge_and_toggle(tk_root):
    comp = CollapsibleFrame(tk_root, title="Settings", collapsed=False)
    assert comp.is_collapsed is False
    assert comp.summary_label.cget("text") == ""
    assert comp.summary_label.cget("text_color") == "#888888"

    # Setting summary while expanded stores text but keeps label blank
    comp.set_summary("Lobby: est • Delay: 3s")
    assert comp.summary_label.cget("text") == ""

    # Collapsing reveals stored summary text
    comp.toggle()
    assert comp.is_collapsed is True
    assert comp.summary_label.cget("text") == "Lobby: est • Delay: 3s"

    # Updating summary while collapsed updates label immediately
    comp.set_summary("Invite Only")
    assert comp.summary_label.cget("text") == "Invite Only"

    # Expanding hides summary label again
    comp.toggle()
    assert comp.is_collapsed is False
    assert comp.summary_label.cget("text") == ""

    # Initialized as collapsed displays summary on set_summary
    comp2 = CollapsibleFrame(tk_root, title="OBS", collapsed=True)
    assert comp2.is_collapsed is True
    comp2.set_summary("Disabled")
    assert comp2.summary_label.cget("text") == "Disabled"

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


def test_lol_settings_form_summary_updates(tk_root):
    form = LolSettingsForm(tk_root, collapsed=True)
    assert form._summary_text == "Lobby: — • Delay: 3s"
    assert form.summary_label.cget("text") == "Lobby: — • Delay: 3s"

    form.load_config({"lobby_name": "EST scrims", "camera_delay": "4", "invite_only": 0})
    assert form._summary_text == "Lobby: EST scrims • Delay: 4s"
    assert form.summary_label.cget("text") == "Lobby: EST scrims • Delay: 4s"

    # Switch to invite only
    form.check_invite_only.select()
    form._update_summary()
    assert form._summary_text == "Invite Only"
    assert form.summary_label.cget("text") == "Invite Only"

    # Switch back
    form.check_invite_only.deselect()
    form._update_summary()
    assert form._summary_text == "Lobby: EST scrims • Delay: 4s"
    assert form.summary_label.cget("text") == "Lobby: EST scrims • Delay: 4s"


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


def test_lol_settings_invite_only_disables_search_entries(tk_root):
    form = LolSettingsForm(tk_root)
    form.load_config({
        "lobby_name": "LobbyA",
        "passwords": "123",
        "ignored_words": "AC",
        "camera_delay": "4",
        "invite_only": 0,
    })

    # Default/search mode: entries are normal
    assert form.entry_lobby.cget("state") == "normal"
    assert form.entry_passwords.cget("state") == "normal"
    assert form.entry_ignored.cget("state") == "normal"
    assert form.entry_delay.cget("state") == "normal"

    # Toggle invite only ON
    form.check_invite_only.select()
    form._on_toggle_invite_only()
    assert form.entry_lobby.cget("state") == "disabled"
    assert form.entry_passwords.cget("state") == "disabled"
    assert form.entry_ignored.cget("state") == "disabled"
    assert form.entry_delay.cget("state") == "normal"

    # Values preserved in config
    cfg = form.get_config()
    assert cfg["lobby_name"] == "LobbyA"
    assert cfg["passwords"] == "123"
    assert cfg["ignored_words"] == "AC"
    assert cfg["camera_delay"] == "4"
    assert cfg["invite_only"] == 1

    # Runtime config also preserves values
    rt_cfg = form.get_runtime_config()
    assert rt_cfg["lobby_name"] == "LobbyA"
    assert rt_cfg["passwords"] == ["123"]
    assert rt_cfg["ignored_words"] == ["AC"]
    assert rt_cfg["invite_only"] is True

    # When whole form disabled and re-enabled, invite-only disabled states are restored
    form.set_enabled(False)
    assert form.entry_delay.cget("state") == "disabled"
    assert form.check_invite_only.cget("state") == "disabled"

    form.set_enabled(True)
    assert form.entry_delay.cget("state") == "normal"
    assert form.check_invite_only.cget("state") == "normal"
    assert form.entry_lobby.cget("state") == "disabled"
    assert form.entry_passwords.cget("state") == "disabled"
    assert form.entry_ignored.cget("state") == "disabled"

    # Toggle invite only back OFF
    form.check_invite_only.deselect()
    form._on_toggle_invite_only()
    assert form.entry_lobby.cget("state") == "normal"
    assert form.entry_passwords.cget("state") == "normal"
    assert form.entry_ignored.cget("state") == "normal"
    assert form.entry_delay.cget("state") == "normal"


def test_obs_settings_form_summary_updates(tk_root):
    form = ObsSettingsForm(tk_root, collapsed=True)
    assert form._summary_text == "Disabled"
    assert form.summary_label.cget("text") == "Disabled"

    # Enabled without schedule
    form.load_config({"obs_enabled": 1, "obs_schedule_enabled": 0})
    assert form._summary_text == "Enabled"
    assert form.summary_label.cget("text") == "Enabled"

    # Enabled with schedule
    form.load_config({
        "obs_enabled": 1,
        "obs_schedule_enabled": 1,
        "obs_schedule_start_time": "11:00",
        "obs_schedule_stop_time": "17:00",
    })
    assert form._summary_text == "Scheduled (11:00 AM - 05:00 PM)"
    assert form.summary_label.cget("text") == "Scheduled (11:00 AM - 05:00 PM)"

    # Toggle off obs_enabled
    form.check_obs_enabled.deselect()
    form._on_toggle_obs_enabled()
    assert form._summary_text == "Disabled"
    assert form.summary_label.cget("text") == "Disabled"


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
    assert form.btn_scan_obs.cget("text") == "✓ Found"

    # Empty scan results show offline feedback
    form._apply_scan_results([], [])
    assert form.btn_scan_obs.cget("text") == "✕ Offline"


def test_obs_settings_form_start_time_preserves_custom_stop_time(tk_root):
    form = ObsSettingsForm(tk_root)
    # Configure custom schedule: 10:00 AM to 05:00 PM (17:00)
    form.load_config({
        "obs_enabled": 1,
        "obs_schedule_enabled": 1,
        "obs_schedule_start_time": "10:00",
        "obs_schedule_stop_time": "17:00",
    })
    assert form.combo_stop_hour.get() == "05"
    assert form.combo_stop_ampm.get() == "PM"

    # Change start time to 11:00 AM (11:00 < 17:00, still valid duration)
    form._set_combo_value(form.combo_start_hour, "11")
    form._on_start_time_changed()

    # User's custom stop time should be preserved
    assert form.combo_stop_hour.get() == "05"
    assert form.combo_stop_min.get() == "00"
    assert form.combo_stop_ampm.get() == "PM"

    # Change start time to 06:00 PM (18:00 >= 17:00, stop becomes <= start)
    form._set_combo_value(form.combo_start_hour, "06")
    form._set_combo_value(form.combo_start_ampm, "PM")
    form._on_start_time_changed()

    # Automatically updates stop time to start + 6h (06:00 PM + 6h = 12:00 AM)
    assert form.combo_stop_hour.get() == "12"
    assert form.combo_stop_min.get() == "00"
    assert form.combo_stop_ampm.get() == "AM"


def test_set_entry_text_helper_behavior(tk_root):
    entry = ctk.CTkEntry(tk_root, placeholder_text="Default Placeholder")
    assert entry._placeholder_text_active is True
    assert entry._entry.get() == "Default Placeholder"

    # Set non-empty text
    set_entry_text(entry, "Custom Value")
    assert entry._placeholder_text_active is False
    assert entry.get() == "Custom Value"
    assert entry._entry.get() == "Custom Value"

    # Reset to empty string
    set_entry_text(entry, "")
    assert entry._placeholder_text_active is True
    assert entry.get() == ""
    assert entry._entry.get() == "Default Placeholder"

    # Reset to None
    set_entry_text(entry, None)
    assert entry._placeholder_text_active is True
    assert entry.get() == ""
    assert entry._entry.get() == "Default Placeholder"


def test_lol_settings_form_placeholders_visibility_on_empty(tk_root):
    form = LolSettingsForm(tk_root)

    # Initial state
    assert form.entry_lobby._placeholder_text_active is True
    assert form.entry_lobby._entry.get() == "e.g.: est, vks"
    assert form.entry_passwords._placeholder_text_active is True
    assert form.entry_passwords._entry.get() == "e.g.: 123, test"
    assert form.entry_delay._placeholder_text_active is True
    assert form.entry_delay._entry.get() == "e.g.: 3"
    assert form.entry_ignored._placeholder_text_active is True
    assert form.entry_ignored._entry.get() == "e.g.: Academy, AC"

    # Load empty config
    form.load_config({
        "lobby_name": "",
        "passwords": "",
        "camera_delay": "",
        "ignored_words": "",
    })

    assert form.entry_lobby._placeholder_text_active is True
    assert form.entry_lobby._entry.get() == "e.g.: est, vks"
    assert form.entry_passwords._placeholder_text_active is True
    assert form.entry_passwords._entry.get() == "e.g.: 123, test"
    assert form.entry_delay._placeholder_text_active is True
    assert form.entry_delay._entry.get() == "e.g.: 3"
    assert form.entry_ignored._placeholder_text_active is True
    assert form.entry_ignored._entry.get() == "e.g.: Academy, AC"

    # Load populated config
    form.load_config({
        "lobby_name": "MyLobby",
        "passwords": "abc",
        "camera_delay": "5",
        "ignored_words": "test",
    })

    assert form.entry_lobby._placeholder_text_active is False
    assert form.entry_lobby.get() == "MyLobby"
    assert form.entry_passwords._placeholder_text_active is False
    assert form.entry_passwords.get() == "abc"
    assert form.entry_delay._placeholder_text_active is False
    assert form.entry_delay.get() == "5"
    assert form.entry_ignored._placeholder_text_active is False
    assert form.entry_ignored.get() == "test"

    # Clear back to empty config
    form.load_config({})
    assert form.entry_lobby._placeholder_text_active is True
    assert form.entry_lobby._entry.get() == "e.g.: est, vks"
    assert form.entry_passwords._placeholder_text_active is True
    assert form.entry_passwords._entry.get() == "e.g.: 123, test"
    assert form.entry_ignored._placeholder_text_active is True
    assert form.entry_ignored._entry.get() == "e.g.: Academy, AC"


def test_obs_settings_form_placeholders_visibility_on_empty(tk_root):
    form = ObsSettingsForm(tk_root)

    # Initial state
    assert form.entry_obs_host._placeholder_text_active is True
    assert form.entry_obs_host._entry.get() == "localhost"
    assert form.entry_obs_port._placeholder_text_active is True
    assert form.entry_obs_port._entry.get() == "4455"
    assert form.entry_obs_password._placeholder_text_active is True
    assert form.entry_obs_password._entry.get() == "Optional password"

    # Load empty config
    form.load_config({
        "obs_host": "",
        "obs_port": "",
        "obs_password": "",
    })

    assert form.entry_obs_host._placeholder_text_active is True
    assert form.entry_obs_host._entry.get() == "localhost"
    assert form.entry_obs_port._placeholder_text_active is True
    assert form.entry_obs_port._entry.get() == "4455"
    assert form.entry_obs_password._placeholder_text_active is True
    assert form.entry_obs_password._entry.get() == "Optional password"


def test_youtube_panel_placeholders_visibility_on_empty(tk_root):
    panel = YouTubePanel(tk_root)

    # Load empty/cleared config
    panel.load_config({
        "yt_stream_title": "",
        "discord_webhook_url": "",
    })

    assert panel.entry_stream_title._placeholder_text_active is True
    assert panel.entry_stream_title._entry.get() == "e.g. EST vs INTZ - {date}"
    assert panel.entry_discord_webhook._placeholder_text_active is True
    assert panel.entry_discord_webhook._entry.get() == "Optional: Webhook URL to auto-post stream link"


def test_youtube_panel_privacy_configuration(tk_root):
    panel = YouTubePanel(tk_root)

    # Default privacy should be Unlisted
    assert panel.option_privacy.get() == "Unlisted"
    assert panel.get_config()["yt_privacy"] == "unlisted"

    # Load public
    panel.load_config({"yt_privacy": "public"})
    assert panel.option_privacy.get() == "Public"
    assert panel.get_config()["yt_privacy"] == "public"

    # Load private
    panel.load_config({"yt_privacy": "private"})
    assert panel.option_privacy.get() == "Private"
    assert panel.get_config()["yt_privacy"] == "private"

    # Load invalid / empty fallback
    panel.load_config({"yt_privacy": "invalid_setting"})
    assert panel.option_privacy.get() == "Unlisted"
    assert panel.get_config()["yt_privacy"] == "unlisted"


def test_youtube_panel_privacy_enabled_state(tk_root):
    panel = YouTubePanel(tk_root)
    panel.load_config({"yt_enabled": 1})

    # Disabled when bot is running
    panel.set_enabled(False)
    assert panel.option_privacy.cget("state") == "disabled"

    # Enabled when bot is stopped and yt_enabled is True
    panel.set_enabled(True)
    assert panel.option_privacy.cget("state") == "normal"

    # Disabled when yt_enabled switch is toggled off
    panel.check_yt_enabled.deselect()
    panel._on_toggle_enabled()
    assert panel.option_privacy.cget("state") == "disabled"


def test_youtube_panel_discord_webhook_masking_on_focus(tk_root):
    panel = YouTubePanel(tk_root)
    # Default without URL -> mask empty (placeholder visible)
    assert panel.entry_discord_webhook.cget("show") == ""

    # Load populated webhook URL -> masked with bullet
    panel.load_config({"discord_webhook_url": "https://discord.com/api/webhooks/123/token"})
    assert panel.entry_discord_webhook.cget("show") == "•"

    # FocusIn reveals plain text
    panel._on_webhook_focus_in()
    assert panel.entry_discord_webhook.cget("show") == ""

    # FocusOut restores bullet mask
    panel._on_webhook_focus_out()
    assert panel.entry_discord_webhook.cget("show") == "•"

    # Emptying the field and focusing out clears show
    panel.entry_discord_webhook.delete(0, "end")
    panel._on_webhook_focus_out()
    assert panel.entry_discord_webhook.cget("show") == ""


def test_youtube_panel_discord_test_button(tk_root):
    with patch("gui.components.youtube_panel.send_discord_notification_async") as mock_notify:
        panel = YouTubePanel(tk_root)
        panel.entry_discord_webhook.delete(0, "end")

        # Empty webhook URL gives "No URL" feedback
        panel._test_discord_webhook()
        mock_notify.assert_not_called()
        assert panel.btn_test_discord.cget("text") == "No URL"

        # Populated webhook URL dispatches notification and gives "Sent!"
        panel.entry_discord_webhook.insert(0, "https://discord.com/api/webhooks/123/token")
        panel._test_discord_webhook()
        mock_notify.assert_called_once()
        assert panel.btn_test_discord.cget("text") == "Sent!"


def test_youtube_panel_title_live_preview(tk_root):
    panel = YouTubePanel(tk_root)
    panel.entry_stream_title.delete(0, "end")
    panel.entry_stream_title.insert(0, "Test Match - {date}")
    panel._update_title_preview()
    assert panel.lbl_title_preview.cget("text").startswith("Preview: Test Match - ")


def test_youtube_panel_open_stream_button(tk_root):
    with patch("gui.components.youtube_panel.webbrowser.open") as mock_open:
        panel = YouTubePanel(tk_root)
        assert panel.btn_open_link.cget("state") == "disabled"

        # Opening when disabled does not launch browser
        panel._open_stream_url()
        mock_open.assert_not_called()

        # Update stream URL enables open button
        panel.update_stream_url("https://youtube.com/live/abc123xyz")
        assert panel.btn_open_link.cget("state") == "normal"

        panel._open_stream_url()
        mock_open.assert_called_once_with("https://youtube.com/live/abc123xyz")

        # Clearing URL disables open button
        panel.update_stream_url("")
        assert panel.btn_open_link.cget("state") == "disabled"


def test_obs_settings_form_shutdown_config_and_widgets(tk_root):
    form = ObsSettingsForm(tk_root)
    form.load_config({
        "obs_enabled": 1,
        "obs_shutdown_enabled": 1,
        "obs_shutdown_delay": 120,
    })

    assert form.check_obs_shutdown.get() == 1
    assert form.combo_shutdown_delay.get() == "120s"
    assert form.combo_shutdown_delay.cget("state") == "normal"

    cfg = form.get_config()
    assert cfg["obs_shutdown_enabled"] is True
    assert cfg["obs_shutdown_delay"] == 120

    # Turn off shutdown
    form.check_obs_shutdown.deselect()
    form._on_toggle_obs_shutdown()
    assert form.combo_shutdown_delay.cget("state") == "disabled"
    assert form.get_config()["obs_shutdown_enabled"] is False


def test_obs_settings_form_shutdown_disabled_when_form_disabled(tk_root):
    form = ObsSettingsForm(tk_root)
    form.load_config({
        "obs_enabled": 1,
        "obs_shutdown_enabled": 1,
    })

    form.set_enabled(False)
    assert form.check_obs_shutdown.cget("state") == "disabled"
    assert form.combo_shutdown_delay.cget("state") == "disabled"

    form.set_enabled(True)
    assert form.check_obs_shutdown.cget("state") == "normal"
    assert form.combo_shutdown_delay.cget("state") == "normal"


def test_obs_settings_form_shutdown_toggle_only_cancels_if_scheduled(tk_root):
    with patch("gui.components.obs_settings_form.cancel_shutdown") as mock_cancel, \
         patch("gui.components.obs_settings_form.is_shutdown_scheduled") as mock_is_scheduled:
        form = ObsSettingsForm(tk_root)
        form.check_obs_shutdown.deselect()

        # Case 1: When no shutdown is scheduled, toggling off should NOT call cancel_shutdown
        mock_is_scheduled.return_value = False
        form._on_toggle_obs_shutdown()
        mock_cancel.assert_not_called()

        # Case 2: When a shutdown is scheduled, toggling off SHOULD call cancel_shutdown
        mock_is_scheduled.return_value = True
        form._on_toggle_obs_shutdown()
        mock_cancel.assert_called_once()


def test_console_toolbar_clear_button(tk_root):
    cleared = []
    def on_clear():
        cleared.append(True)

    toolbar = ConsoleToolbar(
        tk_root,
        get_log_text=lambda: "sample log text",
        logs_dir="logs",
        on_clear=on_clear,
    )

    assert hasattr(toolbar, "btn_clear")
    assert toolbar.btn_clear.cget("text") == "Clear"
    assert toolbar.btn_clear.cget("fg_color") == "transparent"
    assert toolbar.btn_clear.cget("border_width") == 1
    assert toolbar.btn_clear.cget("border_color") == BORDER_COLOR

    # Trigger clear command
    toolbar._clear_logs()
    assert len(cleared) == 1

    # Verify toolbar without on_clear callback does not error
    toolbar_no_callback = ConsoleToolbar(
        tk_root,
        get_log_text=lambda: "",
        logs_dir="logs",
    )
    toolbar_no_callback._clear_logs()


