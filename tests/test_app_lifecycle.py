from unittest.mock import MagicMock, patch
import customtkinter as ctk
import pytest

from gui.app import App


@pytest.fixture(scope="module")
def tk_root():
    root = ctk.CTk()
    yield root
    root.destroy()


def test_app_window_resize_and_min_size(tk_root):
    with patch("gui.app.render_startup_banner"), \
         patch("gui.app.youtube_manager"), \
         patch("gui.app.obs_controller"):
        app = App()
        app.withdraw()

        try:
            # Resizable in Y only (width fixed, height resizable)
            resizable_x, resizable_y = app.resizable()
            assert not resizable_x
            assert resizable_y

            # Minimum dimensions
            assert app._min_width == 700
            assert app._min_height == 840

            # Layout hierarchy: btn_toggle is in top_frame
            assert app.btn_toggle.master == app.top_frame

            # Sequence inside top_frame: title -> status_cards -> btn_toggle -> youtube_panel
            children = app.top_frame.pack_slaves()
            idx_status = children.index(app.status_cards)
            idx_btn = children.index(app.btn_toggle)
            idx_yt = children.index(app.youtube_panel)
            assert idx_status < idx_btn < idx_yt
        finally:
            app.destroy()


def test_app_on_close_saves_config_and_stops_bot_when_running(tk_root):
    with patch("gui.app.render_startup_banner"), \
         patch("gui.app.youtube_manager"), \
         patch("gui.app.obs_controller"), \
         patch("gui.app.stop_bot") as mock_stop_bot:
        app = App()
        app.withdraw()

        app.save_config = MagicMock()
        app.destroy = MagicMock()
        app.is_running = True

        app.on_close()

        app.save_config.assert_called_once()
        assert app.is_running is False
        mock_stop_bot.assert_called_once()
        app.destroy.assert_called_once()


def test_app_on_close_saves_config_without_stopping_when_idle(tk_root):
    with patch("gui.app.render_startup_banner"), \
         patch("gui.app.youtube_manager"), \
         patch("gui.app.obs_controller"), \
         patch("gui.app.stop_bot") as mock_stop_bot:
        app = App()
        app.withdraw()

        app.save_config = MagicMock()
        app.destroy = MagicMock()
        app.is_running = False

        app.on_close()

        app.save_config.assert_called_once()
        mock_stop_bot.assert_not_called()
        app.destroy.assert_called_once()
