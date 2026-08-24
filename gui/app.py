import customtkinter as ctk
import logging
import queue
import json
import os
import sys

# Add project root directory to sys.path if running app.py directly
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from core.hexgate import start_bot, stop_bot
from core.obs_controller import obs_controller, silence_external_loggers
from core.youtube_manager import youtube_manager
from core.discord_notifier import send_discord_notification_async
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

APP_VERSION = "1.0.0"

# User configuration saved in AppData
APPDATA = os.getenv('APPDATA', os.path.expanduser('~'))
CONFIG_DIR = os.path.join(APPDATA, 'HexgateSpectator')
CONFIG_FILE = os.path.join(CONFIG_DIR, 'config.json')
LOGS_DIR = os.path.join(CONFIG_DIR, 'logs')

# Create folders if they don't exist
if not os.path.exists(CONFIG_DIR):
    os.makedirs(CONFIG_DIR)
if not os.path.exists(LOGS_DIR):
    os.makedirs(LOGS_DIR)

class TextboxHandler(logging.Handler):
    def __init__(self, log_queue):
        super().__init__()
        self.log_queue = log_queue

    def emit(self, record):
        msg = self.format(record)
        self.log_queue.put(msg)

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
    }
    _YT_DEFAULTS = {
        "yt_enabled": 1,
        "yt_stream_title": "EST vs INTZ - {date}",
        "discord_enabled": 1,
        "discord_webhook_url": "",
    }

    def __init__(self):
        super().__init__()
        
        # Window Configuration
        self.title("Hexgate - Scrim Auto Spectator")
        self.geometry("700x940")
        self.resizable(False, False)
        
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")
        
        self.is_running = False
        self.log_queue = queue.Queue()
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

        # YouTube Stream Panel (Placed directly under Status Cards)
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

        self.btn_toggle = ctk.CTkButton(self, text="Start Bot", command=self.toggle_bot, font=btn_font, height=38)
        self.btn_toggle.pack(pady=8, padx=25, fill="x")

        self.log_toolbar = ConsoleToolbar(
            self,
            get_log_text=lambda: self.log_box.get("1.0", "end-1c"),
            logs_dir=LOGS_DIR,
        )
        self.log_toolbar.pack(pady=(6, 2), padx=25, fill="x")

        self.status_footer = StatusFooter(self, version=APP_VERSION)
        self.status_footer.pack(side="bottom", fill="x")

        self.log_box = ctk.CTkTextbox(self, state="disabled", fg_color="#121212", text_color="#A5D6A7", font=console_font, border_width=1, border_color="#333333")
        self.log_box.pack(pady=(2, 6), padx=25, fill="both", expand=True)

        # Configure tags for visual session dividers
        self.log_box._textbox.tag_config("session_start", foreground="#5dade2")
        self.log_box._textbox.tag_config("session_stop", foreground="#e67e22")

        # Render ASCII banner and initial system info
        render_startup_banner(self.log_box, version=APP_VERSION)

        self.after(100, self.process_log_queue)
        self.after(500, self._update_stream_indicator)

        # Load saved config (if exists)
        self.load_config()

    def _on_obs_config_changed(self, obs_config: dict):
        if not self.is_running:
            obs_controller.configure(obs_config)

    def _on_youtube_config_changed(self, yt_config: dict):
        if not self.is_running:
            pass

    def _update_stream_indicator(self):
        """Called every second to refresh the header stream indicator and status details."""
        summary = obs_controller.get_status_summary(is_bot_running=self.is_running)
        self.status_cards.update_stream_status(
            color=summary["color"],
            label=summary["label"],
            detail=summary["detail"],
        )
        self.after(1000, self._update_stream_indicator)

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

    def process_log_queue(self):
        while not self.log_queue.empty():
            msg = self.log_queue.get()
            self.log_box.configure(state="normal")
            tk_text = self.log_box._textbox
            if "[Session Started:" in msg:
                tk_text.insert("end", f"\n{msg}\n", "session_start")
            elif "[Session Stopped:" in msg:
                tk_text.insert("end", f"{msg}\n\n", "session_stop")
            else:
                tk_text.insert("end", msg + "\n")
            self.log_box.see("end")
            self.log_box.configure(state="disabled")
        self.after(100, self.process_log_queue)

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

            # Auto-create YouTube broadcast if enabled
            if yt_config.get("yt_enabled") and youtube_manager.is_authenticated():
                title_tpl = yt_config.get("yt_stream_title", "EST vs INTZ - {date}")
                
                def on_broadcast_success(watch_url):
                    self.after(0, lambda: self.youtube_panel.update_stream_url(watch_url))
                    
                    discord_enabled = yt_config.get("discord_enabled", False)
                    discord_webhook_url = yt_config.get("discord_webhook_url", "").strip()
                    if discord_enabled and discord_webhook_url:
                        formatted_title = youtube_manager.format_title(title_tpl)
                        send_discord_notification_async(discord_webhook_url, formatted_title, watch_url)

                    if obs_controller.cached_status.get("active", False):
                        youtube_manager.transition_to_live_async()

                youtube_manager.create_broadcast_async(
                    title_template=title_tpl,
                    on_success=on_broadcast_success
                )

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
