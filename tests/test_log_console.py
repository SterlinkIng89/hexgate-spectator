import logging
import queue
from unittest.mock import MagicMock, patch
import pytest
import customtkinter as ctk

from gui.app import App, TextboxHandler, MAX_LOG_LINES, TRIM_CHUNK


@pytest.fixture(scope="module")
def tk_root():
    root = ctk.CTk()
    yield root
    root.destroy()


def test_textbox_handler_emits_level_and_message_tuple():
    log_q = queue.Queue()
    handler = TextboxHandler(log_q)
    handler.setFormatter(logging.Formatter("[%(asctime)s] %(message)s", datefmt="%H:%M:%S"))

    record = logging.LogRecord(
        name="test_logger",
        level=logging.ERROR,
        pathname=__file__,
        lineno=10,
        msg="Sample error occurred",
        args=(),
        exc_info=None,
    )
    handler.emit(record)

    assert not log_q.empty()
    level, formatted = log_q.get()
    assert level == "ERROR"
    assert "Sample error occurred" in formatted


def test_log_queue_deduplication_and_semantic_highlighting(tk_root):
    with patch("gui.app.render_startup_banner"):
        app = App()
        app.withdraw()

        # Ensure textbox is empty for the test
        app.log_box.configure(state="normal")
        app.log_box._textbox.delete("1.0", "end")
        app.log_box.configure(state="disabled")

        # Push consecutive identical INFO messages
        app.log_queue.put(("INFO", "[10:00:00] [OBS] Polling stream status..."))
        app.log_queue.put(("INFO", "[10:00:01] [OBS] Polling stream status..."))
        app.log_queue.put(("INFO", "[10:00:02] [OBS] Polling stream status..."))
        app.process_log_queue()

        content = app.log_box.get("1.0", "end-1c").strip()
        assert content == "[10:00:00] [OBS] Polling stream status... (x3)"

        # Check tag assignments
        tk_text = app.log_box._textbox
        assert "log_time" in tk_text.tag_names("1.0")
        assert "sub_obs" in tk_text.tag_names("1.12")
        assert "log_info" in tk_text.tag_names("1.25")

        # Push a distinct message
        app.log_queue.put(("INFO", "[10:00:03] [YouTube] Broadcast created"))
        app.process_log_queue()

        lines = app.log_box.get("1.0", "end-1c").strip().split("\n")
        assert len(lines) == 2
        assert lines[0] == "[10:00:00] [OBS] Polling stream status... (x3)"
        assert lines[1] == "[10:00:03] [YouTube] Broadcast created"

        # Push an ERROR message
        app.log_queue.put(("ERROR", "[10:00:04] Something failed"))
        app.process_log_queue()

        lines = app.log_box.get("1.0", "end-1c").strip().split("\n")
        assert len(lines) == 3
        assert "log_error" in tk_text.tag_names("3.0")

        # Push a WARNING message
        app.log_queue.put(("WARNING", "[10:00:05] Deprecation notice"))
        app.process_log_queue()

        lines = app.log_box.get("1.0", "end-1c").strip().split("\n")
        assert len(lines) == 4
        assert "log_warning" in tk_text.tag_names("4.0")

        app.destroy()


def test_log_queue_smart_autoscroll_lock(tk_root):
    with patch("gui.app.render_startup_banner"):
        app = App()
        app.withdraw()

        app.log_box.configure(state="normal")
        app.log_box._textbox.delete("1.0", "end")
        app.log_box.configure(state="disabled")

        mock_see = MagicMock()
        app.log_box.see = mock_see

        # Case 1: When user is near the bottom (yview >= 0.98), see("end") IS called
        with patch.object(app.log_box._textbox, "yview", return_value=(0.5, 1.0)):
            app.log_queue.put(("INFO", "[10:00:00] Test message 1"))
            app.process_log_queue()
            mock_see.assert_called_with("end")

        mock_see.reset_mock()

        # Case 2: When user scrolled up (yview < 0.98), see("end") is NOT called
        with patch.object(app.log_box._textbox, "yview", return_value=(0.2, 0.6)):
            app.log_queue.put(("INFO", "[10:00:01] Test message 2"))
            app.process_log_queue()
            mock_see.assert_not_called()

        app.destroy()


def test_clear_console_resets_state_and_restores_banner(tk_root):
    with patch("gui.app.render_startup_banner") as mock_banner:
        app = App()
        app.withdraw()

        app._last_log_msg = "Last message"
        app._last_log_count = 5
        app._last_log_level = "INFO"
        app._last_log_prefix = "[10:00:00] "

        mock_banner.reset_mock()
        app.clear_console()

        assert app._last_log_msg is None
        assert app._last_log_count == 0
        assert app._last_log_level is None
        assert app._last_log_prefix is None
        mock_banner.assert_called_once()
        assert app.log_box.cget("state") == "disabled"

        app.destroy()


def test_log_buffer_cap_enforces_fifo_trimming(tk_root):
    with patch("gui.app.render_startup_banner"):
        app = App()
        app.withdraw()

        app.log_box.configure(state="normal")
        app.log_box._textbox.delete("1.0", "end")
        # Insert 1005 lines
        for i in range(1005):
            app.log_box._textbox.insert("end", f"Line {i}\n")
        app.log_box.configure(state="disabled")

        initial_lines = int(app.log_box._textbox.index("end-1c").split(".")[0])
        assert initial_lines > MAX_LOG_LINES

        # Enqueue one more message and process queue
        app.log_queue.put(("INFO", "[12:00:00] Overflow trigger line"))
        app.process_log_queue()

        final_lines = int(app.log_box._textbox.index("end-1c").split(".")[0])
        # TRIM_CHUNK lines should have been trimmed from the top
        assert final_lines <= MAX_LOG_LINES + 5
        assert final_lines < initial_lines

        app.destroy()
