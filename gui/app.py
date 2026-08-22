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
from core.obs_controller import obs_controller

# User configuration saved in AppData
APPDATA = os.getenv('APPDATA', os.path.expanduser('~'))
CONFIG_DIR = os.path.join(APPDATA, 'HexgateSpectator')
CONFIG_FILE = os.path.join(CONFIG_DIR, 'config.json')

# Create folder if it doesn't exist
if not os.path.exists(CONFIG_DIR):
    os.makedirs(CONFIG_DIR)

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
        "obs_host": "localhost",
        "obs_port": "4455",
        "obs_password": "",
        "obs_profile": "",
        "obs_scene_collection": "",
        "obs_scene": "",
        "obs_auto_start": 1,
        "obs_auto_stop": 1,
        "obs_schedule_enabled": 0,
        "obs_schedule_start_time": "",
        "obs_schedule_stop_time": "",
    }

    def __init__(self):
        super().__init__()
        
        # Window Configuration
        self.title("Hexgate - Scrim Auto Spectator")
        self.geometry("700x900")
        self.resizable(False, False)
        
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")
        
        self.is_running = False
        self.log_queue = queue.Queue()
        self.setup_logging()

        # Fonts
        title_font = ctk.CTkFont(family="Roboto", size=24, weight="bold")
        status_font = ctk.CTkFont(family="Roboto", size=15, weight="bold")
        section_font = ctk.CTkFont(family="Roboto", size=14, weight="bold")
        label_font = ctk.CTkFont(family="Roboto", size=13)
        sub_font = ctk.CTkFont(family="Roboto", size=12)
        btn_font = ctk.CTkFont(family="Roboto", size=16, weight="bold")

        # --- UI Layout ---
        
        self.top_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.top_frame.pack(pady=(12, 4), padx=25, fill="x")
        
        self.title_label = ctk.CTkLabel(self.top_frame, text="Hexgate Spectator", font=title_font)
        self.title_label.pack(pady=(0, 6))
        
        # Status Cards Container (2 distinct bordered cards, 50% width each)
        self.status_container = ctk.CTkFrame(self.top_frame, fg_color="transparent")
        self.status_container.pack(pady=(0, 4), fill="x")
        
        self.status_container.columnconfigure(0, weight=1, uniform="status_cards")
        self.status_container.columnconfigure(1, weight=1, uniform="status_cards")
        
        # Left Card: LoL Bot Status
        self.bot_card = ctk.CTkFrame(self.status_container, fg_color="#1e1e1e", border_width=1, border_color="#333333", corner_radius=8)
        self.bot_card.grid(row=0, column=0, padx=(0, 5), sticky="nsew")
        
        self.bot_status_header = ctk.CTkFrame(self.bot_card, fg_color="transparent")
        self.bot_status_header.pack(pady=(8, 1))
        
        self.bot_status_dot = ctk.CTkLabel(self.bot_status_header, text="●", font=ctk.CTkFont(family="Roboto", size=13, weight="bold"), text_color="#e74c3c")
        self.bot_status_dot.pack(side="left", padx=(0, 6))
        
        self.bot_status_label = ctk.CTkLabel(self.bot_status_header, text="Bot: Stopped", font=status_font, text_color="#e74c3c")
        self.bot_status_label.pack(side="left")
        
        self.bot_detail_label = ctk.CTkLabel(self.bot_card, text="Spectator service offline", font=sub_font, text_color="#888888", anchor="center")
        self.bot_detail_label.pack(pady=(0, 8), padx=8, fill="x")
        
        # Right Card: OBS / Stream Status
        self.stream_card = ctk.CTkFrame(self.status_container, fg_color="#1e1e1e", border_width=1, border_color="#333333", corner_radius=8)
        self.stream_card.grid(row=0, column=1, padx=(5, 0), sticky="nsew")
        
        self.stream_status_header = ctk.CTkFrame(self.stream_card, fg_color="transparent")
        self.stream_status_header.pack(pady=(8, 1))
        
        self.stream_status_dot = ctk.CTkLabel(self.stream_status_header, text="●", font=ctk.CTkFont(family="Roboto", size=13, weight="bold"), text_color="#7f8c8d")
        self.stream_status_dot.pack(side="left", padx=(0, 6))
        
        self.stream_status_label = ctk.CTkLabel(self.stream_status_header, text="Stream: Ready", font=status_font, text_color="#7f8c8d")
        self.stream_status_label.pack(side="left")
        
        self.stream_detail_label = ctk.CTkLabel(self.stream_card, text="Start bot to begin monitoring", font=sub_font, text_color="#888888", anchor="center")
        self.stream_detail_label.pack(pady=(0, 8), padx=8, fill="x")
        
        # --- LoL Client Settings Frame ---
        self.config_frame = ctk.CTkFrame(self, border_width=1, border_color="#333333")
        self.config_frame.pack(pady=5, padx=25, fill="x")
        
        self.config_frame.columnconfigure(0, weight=1)
        self.config_frame.columnconfigure(1, weight=1)
        self.config_frame.columnconfigure(2, weight=1)
        self.config_frame.columnconfigure(3, weight=1)
        
        ctk.CTkLabel(self.config_frame, text="Lobby Name(s):", font=label_font).grid(row=0, column=0, padx=10, pady=4, sticky="w")
        self.entry_lobby = ctk.CTkEntry(self.config_frame, placeholder_text="e.g.: est, vks", font=label_font, width=140)
        self.entry_lobby.grid(row=0, column=1, padx=10, pady=4, sticky="we")
        
        ctk.CTkLabel(self.config_frame, text="Passwords:", font=label_font).grid(row=0, column=2, padx=10, pady=4, sticky="w")
        self.entry_passwords = ctk.CTkEntry(self.config_frame, placeholder_text="e.g.: 123, test", font=label_font, width=140)
        self.entry_passwords.grid(row=0, column=3, padx=10, pady=4, sticky="we")
        
        ctk.CTkLabel(self.config_frame, text="Camera Delay (s):", font=label_font).grid(row=1, column=0, padx=10, pady=4, sticky="w")
        self.entry_delay = ctk.CTkEntry(self.config_frame, font=label_font, width=140)
        self.entry_delay.grid(row=1, column=1, padx=10, pady=4, sticky="we")
        
        ctk.CTkLabel(self.config_frame, text="Ignored Words:", font=label_font).grid(row=1, column=2, padx=10, pady=4, sticky="w")
        self.entry_ignored = ctk.CTkEntry(self.config_frame, placeholder_text="e.g.: Academy, AC", font=label_font, width=140)
        self.entry_ignored.grid(row=1, column=3, padx=10, pady=4, sticky="we")
        
        self.check_invite_only = ctk.CTkSwitch(self.config_frame, text="Invite Only Mode (Don't search)", font=label_font)
        self.check_invite_only.grid(row=2, column=0, columnspan=4, padx=10, pady=6, sticky="w")

        # --- OBS Integration Settings Frame ---
        self.obs_frame = ctk.CTkFrame(self, border_width=1, border_color="#333333")
        self.obs_frame.pack(pady=5, padx=25, fill="x")

        self.obs_frame.columnconfigure(0, weight=1)
        self.obs_frame.columnconfigure(1, weight=1)
        self.obs_frame.columnconfigure(2, weight=1)
        self.obs_frame.columnconfigure(3, weight=1)

        self.check_obs_enabled = ctk.CTkSwitch(self.obs_frame, text="Enable OBS Integration", font=section_font, command=self._on_toggle_obs_enabled)
        self.check_obs_enabled.grid(row=0, column=0, columnspan=2, padx=10, pady=6, sticky="w")

        self.check_obs_auto_start = ctk.CTkCheckBox(self.obs_frame, text="Auto-start stream", font=label_font)
        self.check_obs_auto_start.grid(row=0, column=2, padx=10, pady=6, sticky="w")

        self.check_obs_auto_stop = ctk.CTkCheckBox(self.obs_frame, text="Auto-stop stream", font=label_font)
        self.check_obs_auto_stop.grid(row=0, column=3, padx=10, pady=6, sticky="w")

        ctk.CTkLabel(self.obs_frame, text="OBS Host:", font=label_font).grid(row=1, column=0, padx=10, pady=4, sticky="w")
        self.entry_obs_host = ctk.CTkEntry(self.obs_frame, placeholder_text="localhost", font=label_font, width=140)
        self.entry_obs_host.grid(row=1, column=1, padx=10, pady=4, sticky="we")

        ctk.CTkLabel(self.obs_frame, text="OBS Port:", font=label_font).grid(row=1, column=2, padx=10, pady=4, sticky="w")
        self.entry_obs_port = ctk.CTkEntry(self.obs_frame, placeholder_text="4455", font=label_font, width=140)
        self.entry_obs_port.grid(row=1, column=3, padx=10, pady=4, sticky="we")

        ctk.CTkLabel(self.obs_frame, text="OBS Password:", font=label_font).grid(row=2, column=0, padx=10, pady=4, sticky="w")
        self.entry_obs_password = ctk.CTkEntry(self.obs_frame, placeholder_text="Optional password", show="*", font=label_font, width=140)
        self.entry_obs_password.grid(row=2, column=1, padx=10, pady=4, sticky="we")

        ctk.CTkLabel(self.obs_frame, text="OBS Profile:", font=label_font).grid(row=2, column=2, padx=10, pady=4, sticky="w")
        self.entry_obs_profile = ctk.CTkEntry(self.obs_frame, placeholder_text="e.g.: Scrims", font=label_font, width=140)
        self.entry_obs_profile.grid(row=2, column=3, padx=10, pady=4, sticky="we")

        ctk.CTkLabel(self.obs_frame, text="Scene Collection:", font=label_font).grid(row=3, column=0, padx=10, pady=4, sticky="w")
        self.entry_obs_scene_collection = ctk.CTkEntry(self.obs_frame, placeholder_text="e.g.: Scrims Layout", font=label_font, width=140)
        self.entry_obs_scene_collection.grid(row=3, column=1, padx=10, pady=4, sticky="we")

        ctk.CTkLabel(self.obs_frame, text="Active Scene:", font=label_font).grid(row=3, column=2, padx=10, pady=4, sticky="w")
        self.entry_obs_scene = ctk.CTkEntry(self.obs_frame, placeholder_text="e.g.: InGame", font=label_font, width=140)
        self.entry_obs_scene.grid(row=3, column=3, padx=10, pady=4, sticky="we")

        self.check_obs_schedule = ctk.CTkSwitch(self.obs_frame, text="Schedule Stream by Time", font=label_font, command=self._on_toggle_obs_schedule)
        self.check_obs_schedule.grid(row=4, column=0, columnspan=4, padx=10, pady=6, sticky="w")

        # --- Start time pickers (12h + AM/PM) ---
        ctk.CTkLabel(self.obs_frame, text="Stream Start:", font=label_font).grid(row=5, column=0, padx=10, pady=4, sticky="w")
        start_time_frame = ctk.CTkFrame(self.obs_frame, fg_color="transparent")
        start_time_frame.grid(row=5, column=1, padx=6, pady=4, sticky="we")
        self.combo_start_hour = ctk.CTkComboBox(start_time_frame, values=[f"{h:02d}" for h in range(1, 13)], width=60, font=label_font)
        self.combo_start_hour.pack(side="left", padx=(0, 2))
        ctk.CTkLabel(start_time_frame, text=":", font=label_font).pack(side="left")
        self.combo_start_min = ctk.CTkComboBox(start_time_frame, values=[f"{m:02d}" for m in range(0, 60, 5)], width=60, font=label_font)
        self.combo_start_min.pack(side="left", padx=(2, 4))
        self.combo_start_ampm = ctk.CTkComboBox(start_time_frame, values=["AM", "PM"], width=58, font=label_font)
        self.combo_start_ampm.pack(side="left")

        # --- Stop time pickers (12h + AM/PM) ---
        ctk.CTkLabel(self.obs_frame, text="Stream Stop:", font=label_font).grid(row=5, column=2, padx=10, pady=4, sticky="w")
        stop_time_frame = ctk.CTkFrame(self.obs_frame, fg_color="transparent")
        stop_time_frame.grid(row=5, column=3, padx=6, pady=4, sticky="we")
        self.combo_stop_hour = ctk.CTkComboBox(stop_time_frame, values=[f"{h:02d}" for h in range(1, 13)], width=60, font=label_font)
        self.combo_stop_hour.pack(side="left", padx=(0, 2))
        ctk.CTkLabel(stop_time_frame, text=":", font=label_font).pack(side="left")
        self.combo_stop_min = ctk.CTkComboBox(stop_time_frame, values=[f"{m:02d}" for m in range(0, 60, 5)], width=60, font=label_font)
        self.combo_stop_min.pack(side="left", padx=(2, 4))
        self.combo_stop_ampm = ctk.CTkComboBox(stop_time_frame, values=["AM", "PM"], width=58, font=label_font)
        self.combo_stop_ampm.pack(side="left")

        # Widget lists — used by _on_toggle_* and toggle_bot to avoid
        # manually listing every widget in multiple places.
        self._lol_widgets = [
            self.entry_lobby, self.entry_passwords, self.entry_delay,
            self.entry_ignored, self.check_invite_only,
        ]
        self._obs_connection_widgets = [
            self.entry_obs_host, self.entry_obs_port, self.entry_obs_password,
            self.entry_obs_profile, self.entry_obs_scene_collection, self.entry_obs_scene,
            self.check_obs_auto_start, self.check_obs_auto_stop, self.check_obs_schedule,
        ]
        self._schedule_picker_widgets = [
            self.combo_start_hour, self.combo_start_min, self.combo_start_ampm,
            self.combo_stop_hour, self.combo_stop_min, self.combo_stop_ampm,
        ]

        self.btn_toggle = ctk.CTkButton(self, text="Start Bot", command=self.toggle_bot, font=btn_font, height=38)
        self.btn_toggle.pack(pady=8, padx=25, fill="x")

        self.log_box = ctk.CTkTextbox(self, state="disabled", fg_color="#121212", text_color="#A5D6A7", font=("Consolas", 12), border_width=1, border_color="#333333")
        self.log_box.pack(pady=(5, 15), padx=25, fill="both", expand=True)

        self.after(100, self.process_log_queue)
        self.after(500, self._update_stream_indicator)

        # Load saved config (if exists)
        self.load_config()

    # ---- Helpers: 12h ↔ 24h conversion ----
    @staticmethod
    def _to_24h(hour_str: str, min_str: str, ampm: str) -> str:
        """Converts 12h picker values to HH:MM (24h) string."""
        h, m = int(hour_str), int(min_str)
        if ampm == "AM":
            h = 0 if h == 12 else h
        else:
            h = 12 if h == 12 else h + 12
        return f"{h:02d}:{m:02d}"

    @staticmethod
    def _from_24h(hhmm: str):
        """Converts HH:MM (24h) string to (hour_str, min_str, ampm). Returns defaults on error."""
        try:
            h, m = int(hhmm.split(":")[0]), int(hhmm.split(":")[1])
            ampm = "AM" if h < 12 else "PM"
            h12 = h % 12 or 12
            m5 = min(round(m / 5) * 5, 55)
            return f"{h12:02d}", f"{m5:02d}", ampm
        except Exception:
            return "06", "00", "AM"

    def _update_stream_indicator(self):
        """Called every second to refresh the header stream indicator and status details."""
        summary = obs_controller.get_status_summary(is_bot_running=self.is_running)

        if self.stream_status_dot.cget("text_color") != summary["color"]:
            self.stream_status_dot.configure(text_color=summary["color"])
        if self.stream_status_label.cget("text") != summary["label"]:
            self.stream_status_label.configure(text=summary["label"], text_color=summary["color"])
        if self.stream_detail_label.cget("text") != summary["detail"]:
            self.stream_detail_label.configure(text=summary["detail"])

        self.after(1000, self._update_stream_indicator)

    def _on_toggle_obs_enabled(self):
        """Updates OBS entry states depending on whether OBS integration is enabled."""
        state = "normal" if self.check_obs_enabled.get() == 1 else "disabled"
        for w in self._obs_connection_widgets:
            w.configure(state=state)
        self._on_toggle_obs_schedule()

    def _on_toggle_obs_schedule(self):
        """Enables/disables schedule picker widgets and syncs config to controller."""
        schedule_active = (self.check_obs_enabled.get() == 1 and self.check_obs_schedule.get() == 1)
        sched_state = "normal" if schedule_active else "disabled"
        for w in self._schedule_picker_widgets:
            w.configure(state=sched_state)
        if not self.is_running:
            obs_controller.configure(self._build_obs_config())

    def load_config(self):
        """Loads configuration from config.json and initializes fields."""
        default_config = {
            "lobby_name": "SCRIM_TEST",
            "passwords": "123",
            "camera_delay": "3",
            "ignored_words": "",
            "invite_only": 0,
            **self._OBS_DEFAULTS,
        }

        
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r") as f:
                    saved_config = json.load(f)
                    default_config.update(saved_config)
            except Exception as e:
                logging.error(f"Error loading configuration: {e}")
        
        lobby_val = default_config.get("lobby_name", "")
        if lobby_val:
            self.entry_lobby.insert(0, lobby_val)
            
        pass_val = default_config.get("passwords", "")
        if pass_val:
            self.entry_passwords.insert(0, pass_val)
            
        self.entry_delay.insert(0, str(default_config.get("camera_delay", "3")))
        
        ignored_val = default_config.get("ignored_words", "")
        if ignored_val:
            self.entry_ignored.insert(0, ignored_val)
        
        if default_config.get("invite_only", 0):
            self.check_invite_only.select()
        else:
            self.check_invite_only.deselect()

        # OBS Settings
        if default_config.get("obs_enabled", 0):
            self.check_obs_enabled.select()
        else:
            self.check_obs_enabled.deselect()

        if default_config.get("obs_auto_start", 1):
            self.check_obs_auto_start.select()
        else:
            self.check_obs_auto_start.deselect()

        if default_config.get("obs_auto_stop", 1):
            self.check_obs_auto_stop.select()
        else:
            self.check_obs_auto_stop.deselect()

        if default_config.get("obs_schedule_enabled", 0):
            self.check_obs_schedule.select()
        else:
            self.check_obs_schedule.deselect()

        self.entry_obs_host.insert(0, str(default_config.get("obs_host", "localhost")))
        self.entry_obs_port.insert(0, str(default_config.get("obs_port", "4455")))
        self.entry_obs_password.insert(0, str(default_config.get("obs_password", "")))
        self.entry_obs_profile.insert(0, str(default_config.get("obs_profile", "")))
        self.entry_obs_scene_collection.insert(0, str(default_config.get("obs_scene_collection", "")))
        self.entry_obs_scene.insert(0, str(default_config.get("obs_scene", "")))

        sh, sm, sampm = self._from_24h(str(default_config.get("obs_schedule_start_time", "")))
        self.combo_start_hour.set(sh)
        self.combo_start_min.set(sm)
        self.combo_start_ampm.set(sampm)

        eh, em, eampm = self._from_24h(str(default_config.get("obs_schedule_stop_time", "")))
        self.combo_stop_hour.set(eh)
        self.combo_stop_min.set(em)
        self.combo_stop_ampm.set(eampm)

        self._on_toggle_obs_enabled()
        obs_controller.configure(self._build_obs_config())

    def _build_obs_config(self) -> dict:
        """Single source of truth for the current OBS widget state as a config dict."""
        return {
            "obs_enabled": self.check_obs_enabled.get() == 1,
            "obs_host": self.entry_obs_host.get().strip(),
            "obs_port": self.entry_obs_port.get().strip(),
            "obs_password": self.entry_obs_password.get(),
            "obs_profile": self.entry_obs_profile.get().strip(),
            "obs_scene_collection": self.entry_obs_scene_collection.get().strip(),
            "obs_scene": self.entry_obs_scene.get().strip(),
            "obs_auto_start": self.check_obs_auto_start.get() == 1,
            "obs_auto_stop": self.check_obs_auto_stop.get() == 1,
            "obs_schedule_enabled": self.check_obs_schedule.get() == 1,
            "obs_schedule_start_time": self._to_24h(
                self.combo_start_hour.get(), self.combo_start_min.get(), self.combo_start_ampm.get()
            ),
            "obs_schedule_stop_time": self._to_24h(
                self.combo_stop_hour.get(), self.combo_stop_min.get(), self.combo_stop_ampm.get()
            ),
        }

    def save_config(self):
        """Saves current configuration to config.json."""
        config_data = {
            "lobby_name": self.entry_lobby.get().strip(),
            "passwords": self.entry_passwords.get().strip(),
            "camera_delay": self.entry_delay.get().strip(),
            "ignored_words": self.entry_ignored.get().strip(),
            "invite_only": self.check_invite_only.get(),
            **self._build_obs_config(),
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
        
        # GUI Handler
        gui_handler = TextboxHandler(self.log_queue)
        gui_handler.setFormatter(formatter)
        logger.addHandler(gui_handler)
        
        # File Handler (saves to AppData)
        try:
            import datetime
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            
            logs_dir = os.path.join(CONFIG_DIR, 'logs')
            if not os.path.exists(logs_dir):
                os.makedirs(logs_dir)
                
            log_file = os.path.join(logs_dir, f'session_{timestamp}.log')
            file_handler = logging.FileHandler(log_file, mode='w', encoding='utf-8')
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)
        except Exception as e:
            print(f"Could not setup file logger: {e}")

    def process_log_queue(self):
        while not self.log_queue.empty():
            msg = self.log_queue.get()
            self.log_box.configure(state="normal")
            self.log_box.insert("end", msg + "\n")
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
            self.bot_status_dot.configure(text_color=color)
            self.bot_status_label.configure(text=f"Bot: {status_title}", text_color=color)
            self.bot_detail_label.configure(text=detail)

        self.after(0, _apply)

    def toggle_bot(self):
        if not self.is_running:
            self.save_config()

            passwords_raw = self.entry_passwords.get()
            passwords = [p.strip() for p in passwords_raw.split(",")] if passwords_raw else []
            ignored_raw = self.entry_ignored.get()
            ignored = [w.strip() for w in ignored_raw.split(",")] if ignored_raw else []
            try:
                cam_delay = float(self.entry_delay.get())
            except ValueError:
                cam_delay = 3.0

            config_data = {
                "lobby_name": self.entry_lobby.get().strip(),
                "passwords": passwords,
                "camera_delay": cam_delay,
                "ignored_words": ignored,
                "invite_only": self.check_invite_only.get() == 1,
                **self._build_obs_config(),
            }

            for w in self._lol_widgets:
                w.configure(state="disabled")
            self.check_obs_enabled.configure(state="disabled")
            for w in self._obs_connection_widgets + self._schedule_picker_widgets:
                w.configure(state="disabled")

            self.is_running = True
            self.btn_toggle.configure(text="Stop Bot", fg_color="#e74c3c", hover_color="#c0392b")
            self.bot_status_dot.configure(text_color="#3498db")
            self.bot_status_label.configure(text="Bot: Starting", text_color="#3498db")
            self.bot_detail_label.configure(text="Initializing spectator bot...")
            start_bot(self.update_status, config_data)
        else:
            self.is_running = False
            self.btn_toggle.configure(text="Start Bot", fg_color=["#3a7ebf", "#1f538d"], hover_color=["#325882", "#14375e"])
            self.bot_status_dot.configure(text_color="#e74c3c")
            self.bot_status_label.configure(text="Bot: Stopped", text_color="#e74c3c")
            self.bot_detail_label.configure(text="Spectator service offline")

            for w in self._lol_widgets:
                w.configure(state="normal")
            self.check_obs_enabled.configure(state="normal")
            self._on_toggle_obs_enabled()
            stop_bot()

def run_app():
    app = App()
    app.mainloop()
