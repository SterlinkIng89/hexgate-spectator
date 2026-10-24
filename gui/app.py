import customtkinter as ctk
import logging
import queue
import json
import os
import sys
import re

# Add project root directory to sys.path if running app.py directly
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from core.version import __version__ as APP_VERSION
from core.hexgate import start_bot, stop_bot
from core.obs_controller import obs_controller, silence_external_loggers
from core.youtube_manager import youtube_manager
from gui.components import (
    ConsoleToolbar,
    StatusFooter,
    render_startup_banner,
    StatusCards,
    LolSettingsForm,
    ObsSettingsForm,
    YouTubePanel,
)
from gui.fonts import (
    init_fonts,
    get_title_font,
    get_button_font,
    get_console_font,
)


# User configuration saved in AppData
APPDATA = os.getenv('APPDATA', os.path.expanduser('~'))
CONFIG_DIR = os.path.join(APPDATA, 'HexgateSpectator')
CONFIG_FILE = os.path.join(CONFIG_DIR, 'config.json')
LOGS_DIR = os.path.join(CONFIG_DIR, 'logs')

# Maximum lines retained in the Tkinter console text widget before batch trimming
MAX_LOG_LINES = 1000
TRIM_CHUNK = 100

# Create folders if they don't exist
if not os.path.exists(CONFIG_DIR):
    os.makedirs(CONFIG_DIR)
if not os.path.exists(LOGS_DIR):
    os.makedirs(LOGS_DIR)

logger = logging.getLogger(__name__)

class TextboxHandler(logging.Handler):
    def __init__(self, log_queue):
        super().__init__()
        self.log_queue = log_queue

    def emit(self, record):
        try:
            msg = self.format(record)
            self.log_queue.put((record.levelname, msg))
        except Exception:
            self.handleError(record)

class App(ctk.CTk):
    _OBS_DEFAULTS = {
        "obs_enabled": 0,
        "obs_host": "",
        "obs_port": "",
        "obs_password": "",
        "obs_profile": "",
        "obs_scene_collection": "",
        "obs_auto_start": 1,
        "obs_auto_stop": 1,
        "obs_schedule_enabled": 1,
        "obs_schedule_start_time": "10:00",
        "obs_schedule_stop_time": "16:00",
        "obs_shutdown_enabled": 0,
        "obs_shutdown_delay": 60,
    }
    _YT_DEFAULTS = {
        "yt_enabled": 1,
        "yt_stream_title": "EST vs INTZ - {date}",
        "yt_privacy": "unlisted",
        "discord_enabled": 1,
        "discord_webhook_url": "",
    }

    def __init__(self):
        super().__init__()
        
        # Window Configuration
        self.title("Hexgate - Scrim Auto Spectator")
        self.geometry("700x940")
        self.minsize(700, 840)
        self.resizable(False, True)
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")
        
        self.is_running = False
        self.log_queue = queue.Queue()
        self._reset_dedup_state()
        self.setup_logging()

        # Initialize Typography System
        init_fonts()
        title_font = get_title_font()
        btn_font = get_button_font()
        console_font = get_console_font()

        # --- UI Layout ---
        
        self.top_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.top_frame.pack(pady=(12, 4), padx=25, fill="x")
        
        self.title_label = ctk.CTkLabel(self.top_frame, text="Hexgate Spectator", font=title_font)
        self.title_label.pack(pady=(0, 6))
        
        # Status Cards Container (LoL Bot & OBS Stream)
        self.status_cards = StatusCards(self.top_frame)
        self.status_cards.pack(pady=(0, 4), fill="x")

        # Primary Action Button (Start Bot / Stop Bot)
        self.btn_toggle = ctk.CTkButton(
            self.top_frame,
            text="Start Bot",
            command=self.toggle_bot,
            font=btn_font,
            height=38,
        )
        self.btn_toggle.pack(pady=(4, 4), fill="x")

        # YouTube Stream Panel (Placed directly under Start Bot button)
        self.youtube_panel = YouTubePanel(
            self.top_frame,
            on_config_changed=self._on_youtube_config_changed,
        )
        self.youtube_panel.pack(pady=(4, 4), fill="x")

        # League Client Settings Frame
        self.lol_settings_form = LolSettingsForm(self)
        self.lol_settings_form.pack(pady=5, padx=25, fill="x")

        # OBS Integration Settings Frame
        self.obs_settings_form = ObsSettingsForm(
            self,
            on_config_changed=self._on_obs_config_changed,
        )
        self.obs_settings_form.pack(pady=5, padx=25, fill="x")

        self.log_toolbar = ConsoleToolbar(
            self,
            get_log_text=lambda: self.log_box.get("1.0", "end-1c"),
            logs_dir=LOGS_DIR,
            on_clear=self.clear_console,
        )
        self.log_toolbar.pack(pady=(6, 2), padx=25, fill="x")

        self.status_footer = StatusFooter(self, version=APP_VERSION)
        self.status_footer.pack(side="bottom", fill="x")

        self.log_box = ctk.CTkTextbox(self, state="disabled", fg_color="#121212", text_color="#A5D6A7", font=console_font, border_width=1, border_color="#333333")
        self.log_box.pack(pady=(2, 6), padx=25, fill="both", expand=True)

        # Configure tags for visual session dividers
        self.log_box._textbox.tag_config("session_start", foreground="#5dade2")
        self.log_box._textbox.tag_config("session_stop", foreground="#e67e22")

        # Configure semantic log level tags
        self.log_box._textbox.tag_config("log_error", foreground="#e74c3c")
        self.log_box._textbox.tag_config("log_warning", foreground="#f1c40f")
        self.log_box._textbox.tag_config("log_info", foreground="#A5D6A7")
        self.log_box._textbox.tag_config("log_dim", foreground="#888888")
        self.log_box._textbox.tag_config("log_time", foreground="#777777")

        # Configure subsystem badge tags
        self.log_box._textbox.tag_config("sub_obs", foreground="#5dade2")
        self.log_box._textbox.tag_config("sub_yt", foreground="#e06c75")
        self.log_box._textbox.tag_config("sub_power", foreground="#e67e22")
        self.log_box._textbox.tag_config("sub_discord", foreground="#7289da")
        self.log_box._textbox.tag_config("sub_gameflow", foreground="#2ecc71")

        # Render ASCII banner and initial system info
        render_startup_banner(self.log_box, version=APP_VERSION)

        # Register YouTube stream URL updates callback to keep UI in sync
        youtube_manager.set_url_callback(
            lambda url: self.after(0, lambda: self.youtube_panel.update_stream_url(url))
        )

        self.after(100, self.process_log_queue)
        self.after(500, self._update_stream_indicator)

        # Load saved config (if exists)
        self.load_config()

    def _on_obs_config_changed(self, obs_config: dict):
        if not self.is_running:
            obs_controller.configure(obs_config)

    def _on_youtube_config_changed(self, yt_config: dict):
        if not self.is_running:
            youtube_manager.configure(yt_config)

    def _update_stream_indicator(self):
        """Called every second to refresh the header stream indicator and status details."""
        try:
            if not self.winfo_exists():
                return
            summary = obs_controller.get_status_summary(is_bot_running=self.is_running)
            self.status_cards.update_stream_status(
                color=summary["color"],
                label=summary["label"],
                detail=summary["detail"],
            )
            self.after(1000, self._update_stream_indicator)
        except Exception:
            pass

    def load_config(self):
        """Loads configuration from config.json and initializes fields."""
        default_config = {
            "lobby_name": "SCRIM_TEST",
            "passwords": "123",
            "camera_delay": "3",
            "ignored_words": "",
            "invite_only": 0,
            **self._OBS_DEFAULTS,
            **self._YT_DEFAULTS,
        }

        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r") as f:
                    saved_config = json.load(f)
                    default_config.update(saved_config)
            except Exception as e:
                logging.error(f"Error loading configuration: {e}")

        self.lol_settings_form.load_config(default_config)
        self.obs_settings_form.load_config(default_config)
        self.youtube_panel.load_config(default_config)
        obs_controller.configure(self.obs_settings_form.get_config())
        youtube_manager.configure(self.youtube_panel.get_config())

    def save_config(self):
        """Saves current configuration to config.json."""
        config_data = {
            **self.lol_settings_form.get_config(),
            **self.obs_settings_form.get_config(),
            **self.youtube_panel.get_config(),
        }
        try:
            with open(CONFIG_FILE, "w") as f:
                json.dump(config_data, f, indent=4)
        except Exception as e:
            logging.error(f"Error saving configuration: {e}")

    def on_close(self) -> None:
        """Saves configuration and cleanly stops background tasks before closing."""
        try:
            self.save_config()
        except Exception as e:
            logging.error(f"Error saving configuration on close: {e}")

        if self.is_running:
            try:
                self.is_running = False
                stop_bot()
            except Exception as e:
                logging.error(f"Error stopping bot on close: {e}")

        self.destroy()

    def setup_logging(self):
        logger = logging.getLogger()
        logger.setLevel(logging.INFO)
        formatter = logging.Formatter('[%(asctime)s] %(message)s', datefmt='%H:%M:%S')

        # Silence verbose external library tracebacks
        silence_external_loggers()
        
        # GUI Handler
        gui_handler = TextboxHandler(self.log_queue)
        gui_handler.setFormatter(formatter)
        logger.addHandler(gui_handler)
        
        # File Handler (saves to AppData)
        try:
            import datetime
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            log_file = os.path.join(LOGS_DIR, f'session_{timestamp}.log')
            file_handler = logging.FileHandler(log_file, mode='w', encoding='utf-8')
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)
        except Exception as e:
            print(f"Could not setup file logger: {e}")

    _SUBSYSTEM_TAGS = [
        ("[YouTube]", "sub_yt"),
        ("[OBS Schedule]", "sub_obs"),
        ("[OBS]", "sub_obs"),
        ("[Power]", "sub_power"),
        ("[Discord]", "sub_discord"),
        ("[GAMEFLOW]", "sub_gameflow"),
        ("[SPECTATE]", "sub_gameflow"),
    ]

    def _reset_dedup_state(self) -> None:
        self._last_log_msg = None
        self._last_log_count = 0
        self._last_log_level = None
        self._last_log_prefix = None

    def clear_console(self) -> None:
        """Clears the console log textbox and restores the startup banner."""
        self.log_box.configure(state="normal")
        self.log_box._textbox.delete("1.0", "end")
        self._reset_dedup_state()
        render_startup_banner(self.log_box, version=APP_VERSION)
        self.log_box.configure(state="disabled")

    def _insert_log_line(self, tk_text, prefix: str, body: str, level: str, count: int = 1) -> None:
        suffix = f" (x{count})" if count > 1 else ""
        if level in ("ERROR", "CRITICAL"):
            tk_text.insert("end", f"{prefix}{body}{suffix}\n", "log_error")
        elif level == "WARNING":
            tk_text.insert("end", f"{prefix}{body}{suffix}\n", "log_warning")
        elif level == "DEBUG":
            tk_text.insert("end", f"{prefix}{body}{suffix}\n", "log_dim")
        else:
            if prefix:
                tk_text.insert("end", prefix, "log_time")
            for sub_name, tag_name in self._SUBSYSTEM_TAGS:
                if body.startswith(sub_name):
                    tk_text.insert("end", sub_name, tag_name)
                    tk_text.insert("end", f"{body[len(sub_name):]}{suffix}\n", "log_info")
                    return
            tk_text.insert("end", f"{body}{suffix}\n", "log_info")

    def process_log_queue(self):
        if not self.log_queue.empty():
            self.log_box.configure(state="normal")
            tk_text = self.log_box._textbox
            try:
                at_bottom = tk_text.yview()[1] >= 0.98
            except Exception:
                at_bottom = True

            while not self.log_queue.empty():
                item = self.log_queue.get()
                if isinstance(item, tuple) and len(item) == 2:
                    level, msg = item
                else:
                    level, msg = "INFO", str(item)

                if "[Session Started:" in msg:
                    self._reset_dedup_state()
                    tk_text.insert("end", f"\n{msg}\n", "session_start")
                elif "[Session Stopped:" in msg:
                    self._reset_dedup_state()
                    tk_text.insert("end", f"{msg}\n\n", "session_stop")
                else:
                    m = re.match(r"^(\[\d{2}:\d{2}:\d{2}\]\s*)(.*)$", msg, re.DOTALL)
                    if m:
                        prefix = m.group(1)
                        body = m.group(2)
                    else:
                        prefix = ""
                        body = msg

                    if (
                        self._last_log_msg is not None
                        and body == self._last_log_msg
                        and level == self._last_log_level
                    ):
                        self._last_log_count += 1
                        tk_text.delete("end-2l", "end-1l")
                        self._insert_log_line(
                            tk_text,
                            self._last_log_prefix,
                            body,
                            level,
                            count=self._last_log_count,
                        )
                    else:
                        self._last_log_msg = body
                        self._last_log_count = 1
                        self._last_log_level = level
                        self._last_log_prefix = prefix
                        self._insert_log_line(
                            tk_text,
                            prefix,
                            body,
                            level,
                            count=1,
                        )

            # Cap log buffer to MAX_LOG_LINES
            try:
                total_lines = int(tk_text.index("end-1c").split(".")[0])
                if total_lines > MAX_LOG_LINES:
                    tk_text.delete("1.0", f"{TRIM_CHUNK + 1}.0")
            except Exception as e:
                logger.debug(f"Error capping log buffer: {e}")

            if at_bottom:
                self.log_box.see("end")
            self.log_box.configure(state="disabled")

        try:
            if self.winfo_exists():
                self.after(100, self.process_log_queue)
        except Exception:
            pass

    _STATUS_PATTERNS = [
        (("in progress",), "#3498db", "In Match", "Spectating game in progress"),
        (("searching",), "#3498db", "Searching", None),
        (("waiting for invitation",), "#3498db", "Waiting Invite", "Invite only mode active"),
        (("starting",), "#3498db", "Starting", None),
        (("switch", "mov", "waiting for lcu", "finding match"), "#f1c40f", "Connecting", None),
        (("stop", "end of game", "quit", "error"), "#e74c3c", "Stopped", "Spectator service offline"),
        (("lobby", "connected", "accepted", "champ"), "#2ecc71", "In Lobby", None),
    ]

    def update_status(self, text):
        text_lower = text.lower()
        color = "#ffffff"
        status_title = text
        detail = "LCU client active"

        for keywords, c, title, det in self._STATUS_PATTERNS:
            if any(kw in text_lower for kw in keywords):
                color = c
                status_title = title
                detail = det if det is not None else text
                if "error" in text_lower:
                    detail = text
                break

        def _apply():
            self.status_cards.update_bot_status(color, status_title, detail)

        self.after(0, _apply)

    def toggle_bot(self):
        if not self.is_running:
            self.save_config()

            yt_config = self.youtube_panel.get_config()
            config_data = {
                **self.lol_settings_form.get_runtime_config(),
                **self.obs_settings_form.get_config(),
                **yt_config,
            }

            self.lol_settings_form.set_enabled(False)
            self.obs_settings_form.set_enabled(False)
            self.youtube_panel.set_enabled(False)

            self.is_running = True
            self.btn_toggle.configure(text="Stop Bot", fg_color="#e74c3c", hover_color="#c0392b")
            self.status_cards.update_bot_status("#3498db", "Starting", "Initializing spectator bot...")
            start_bot(self.update_status, config_data)
        else:
            self.is_running = False
            self.btn_toggle.configure(text="Start Bot", fg_color=["#3a7ebf", "#1f538d"], hover_color=["#325882", "#14375e"])
            self.status_cards.update_bot_status("#e74c3c", "Stopped", "Spectator service offline")

            self.lol_settings_form.set_enabled(True)
            self.obs_settings_form.set_enabled(True)
            self.youtube_panel.set_enabled(True)
            stop_bot()

def run_app():
    app = App()
    app.mainloop()
