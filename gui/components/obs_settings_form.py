import logging
import customtkinter as ctk
from gui.components.collapsible_frame import CollapsibleFrame
from gui.fonts import get_label_font, get_section_font


class ObsSettingsForm(CollapsibleFrame):
    def __init__(self, master, on_config_changed=None, **kwargs):
        kwargs.setdefault("title", "OBS Integration Settings")
        kwargs.setdefault("collapsed", True)
        kwargs.setdefault("border_width", 1)
        kwargs.setdefault("border_color", "#333333")
        super().__init__(master, **kwargs)

        self._on_config_changed = on_config_changed
        label_font = get_label_font()
        section_font = get_section_font()

        self.content_frame.columnconfigure(0, weight=1)
        self.content_frame.columnconfigure(1, weight=1)
        self.content_frame.columnconfigure(2, weight=1)
        self.content_frame.columnconfigure(3, weight=1)

        self.check_obs_enabled = ctk.CTkSwitch(
            self.content_frame,
            text="Enable OBS Integration",
            font=section_font,
            command=self._on_toggle_obs_enabled,
        )
        self.check_obs_enabled.grid(row=0, column=0, columnspan=2, padx=10, pady=6, sticky="w")

        self.check_obs_auto_start = ctk.CTkCheckBox(self.content_frame, text="Auto-start stream", font=label_font)
        self.check_obs_auto_start.grid(row=0, column=2, padx=10, pady=6, sticky="w")

        self.check_obs_auto_stop = ctk.CTkCheckBox(self.content_frame, text="Auto-stop stream", font=label_font)
        self.check_obs_auto_stop.grid(row=0, column=3, padx=10, pady=6, sticky="w")

        ctk.CTkLabel(self.content_frame, text="OBS Host:", font=label_font).grid(row=1, column=0, padx=10, pady=4, sticky="w")
        self.entry_obs_host = ctk.CTkEntry(self.content_frame, placeholder_text="localhost", font=label_font, width=140)
        self.entry_obs_host.grid(row=1, column=1, padx=10, pady=4, sticky="we")

        ctk.CTkLabel(self.content_frame, text="OBS Port:", font=label_font).grid(row=1, column=2, padx=10, pady=4, sticky="w")
        self.entry_obs_port = ctk.CTkEntry(self.content_frame, placeholder_text="4455", font=label_font, width=140)
        self.entry_obs_port.grid(row=1, column=3, padx=10, pady=4, sticky="we")

        ctk.CTkLabel(self.content_frame, text="OBS Password:", font=label_font).grid(row=2, column=0, padx=10, pady=4, sticky="w")
        self.entry_obs_password = ctk.CTkEntry(self.content_frame, placeholder_text="Optional password", show="*", font=label_font, width=140)
        self.entry_obs_password.grid(row=2, column=1, padx=10, pady=4, sticky="we")

        ctk.CTkLabel(self.content_frame, text="OBS Profile:", font=label_font).grid(row=2, column=2, padx=10, pady=4, sticky="w")
        self.entry_obs_profile = ctk.CTkEntry(self.content_frame, placeholder_text="e.g.: Scrims", font=label_font, width=140)
        self.entry_obs_profile.grid(row=2, column=3, padx=10, pady=4, sticky="we")

        ctk.CTkLabel(self.content_frame, text="Scene Collection:", font=label_font).grid(row=3, column=0, padx=10, pady=4, sticky="w")
        self.entry_obs_scene_collection = ctk.CTkEntry(self.content_frame, placeholder_text="e.g.: Scrims Layout", font=label_font, width=140)
        self.entry_obs_scene_collection.grid(row=3, column=1, padx=10, pady=4, sticky="we")

        ctk.CTkLabel(self.content_frame, text="Active Scene:", font=label_font).grid(row=3, column=2, padx=10, pady=4, sticky="w")
        self.entry_obs_scene = ctk.CTkEntry(self.content_frame, placeholder_text="e.g.: InGame", font=label_font, width=140)
        self.entry_obs_scene.grid(row=3, column=3, padx=10, pady=4, sticky="we")

        self.check_obs_schedule = ctk.CTkSwitch(
            self.content_frame,
            text="Schedule Stream by Time",
            font=label_font,
            command=self._on_toggle_obs_schedule,
        )
        self.check_obs_schedule.grid(row=4, column=0, columnspan=4, padx=10, pady=6, sticky="w")

        # --- Start time pickers (12h + AM/PM) ---
        start_time_frame = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        start_time_frame.grid(row=5, column=0, columnspan=2, padx=10, pady=(2, 8), sticky="w")

        ctk.CTkLabel(start_time_frame, text="Stream Start:", font=label_font).pack(side="left", padx=(0, 8))
        self.combo_start_hour = ctk.CTkComboBox(
            start_time_frame, values=[f"{h:02d}" for h in range(1, 13)], width=64, font=label_font, dropdown_font=label_font, command=self._on_start_time_changed
        )
        self.combo_start_hour.pack(side="left", padx=(0, 2))
        ctk.CTkLabel(start_time_frame, text=":", font=label_font).pack(side="left", padx=(0, 2))
        self.combo_start_min = ctk.CTkComboBox(
            start_time_frame, values=[f"{m:02d}" for m in range(0, 60, 5)], width=64, font=label_font, dropdown_font=label_font, command=self._on_start_time_changed
        )
        self.combo_start_min.pack(side="left", padx=(0, 4))
        self.combo_start_ampm = ctk.CTkComboBox(
            start_time_frame, values=["AM", "PM"], width=64, font=label_font, dropdown_font=label_font, command=self._on_start_time_changed
        )
        self.combo_start_ampm.pack(side="left")

        # --- Stop time pickers (12h + AM/PM) ---
        stop_time_frame = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        stop_time_frame.grid(row=5, column=2, columnspan=2, padx=10, pady=(2, 8), sticky="w")

        ctk.CTkLabel(stop_time_frame, text="Stream Stop:", font=label_font).pack(side="left", padx=(0, 8))
        self.combo_stop_hour = ctk.CTkComboBox(
            stop_time_frame, values=[f"{h:02d}" for h in range(1, 13)], width=64, font=label_font, dropdown_font=label_font, command=self._on_stop_time_changed
        )
        self.combo_stop_hour.pack(side="left", padx=(0, 2))
        ctk.CTkLabel(stop_time_frame, text=":", font=label_font).pack(side="left", padx=(0, 2))
        self.combo_stop_min = ctk.CTkComboBox(
            stop_time_frame, values=[f"{m:02d}" for m in range(0, 60, 5)], width=64, font=label_font, dropdown_font=label_font, command=self._on_stop_time_changed
        )
        self.combo_stop_min.pack(side="left", padx=(0, 4))
        self.combo_stop_ampm = ctk.CTkComboBox(
            stop_time_frame, values=["AM", "PM"], width=64, font=label_font, dropdown_font=label_font, command=self._on_stop_time_changed
        )
        self.combo_stop_ampm.pack(side="left")

        self._obs_connection_widgets = [
            self.entry_obs_host,
            self.entry_obs_port,
            self.entry_obs_password,
            self.entry_obs_profile,
            self.entry_obs_scene_collection,
            self.entry_obs_scene,
            self.check_obs_auto_start,
            self.check_obs_auto_stop,
            self.check_obs_schedule,
        ]
        self._schedule_picker_widgets = [
            self.combo_start_hour,
            self.combo_start_min,
            self.combo_start_ampm,
            self.combo_stop_hour,
            self.combo_stop_min,
            self.combo_stop_ampm,
        ]

    @staticmethod
    def _to_24h(hour_str: str, min_str: str, ampm: str) -> str:
        """Converts 12h picker values to HH:MM (24h) string."""
        try:
            h, m = int(hour_str), int(min_str)
            if ampm == "AM":
                h = 0 if h == 12 else h
            else:
                h = 12 if h == 12 else h + 12
            return f"{h:02d}:{m:02d}"
        except Exception:
            return "10:00"

    @staticmethod
    def _from_24h(hhmm: str, default_h: int = 10, default_m: int = 0):
        """Converts HH:MM (24h) string to (hour_str, min_str, ampm). Returns defaults on error."""
        try:
            if not hhmm:
                h, m = default_h, default_m
            else:
                parts = str(hhmm).split(":")
                h, m = int(parts[0]), int(parts[1])
            ampm = "AM" if h < 12 else "PM"
            h12 = h % 12 or 12
            m5 = min(round(m / 5) * 5, 55)
            return f"{h12:02d}", f"{m5:02d}", ampm
        except Exception:
            ampm = "AM" if default_h < 12 else "PM"
            h12 = default_h % 12 or 12
            return f"{h12:02d}", f"{default_m:02d}", ampm

    @staticmethod
    def _set_combo_value(combo, value):
        """Safely updates a CTkComboBox value even if the widget is currently disabled."""
        prev_state = combo.cget("state")
        if prev_state == "disabled":
            combo.configure(state="normal")
            combo.set(value)
            combo.configure(state="disabled")
        else:
            combo.set(value)

    @staticmethod
    def _calculate_stop_time_from_start(start_h_str: str, start_m_str: str, start_ampm: str, offset_hours: int = 6):
        """Calculates stop time tuple (h12_str, m_str, ampm) given start time and an offset in hours."""
        try:
            h = int(start_h_str)
            m = int(start_m_str)
            if start_ampm == "AM":
                h24 = 0 if h == 12 else h
            else:
                h24 = 12 if h == 12 else h + 12

            stop_h24 = (h24 + offset_hours) % 24
            stop_ampm = "AM" if stop_h24 < 12 else "PM"
            stop_h12 = stop_h24 % 12 or 12
            return f"{stop_h12:02d}", f"{m:02d}", stop_ampm
        except Exception:
            return "04", "00", "PM"

    def _on_start_time_changed(self, _choice=None):
        """Automatically updates stop time to start time + 6 hours when start time changes."""
        sh = self.combo_start_hour.get()
        sm = self.combo_start_min.get()
        sampm = self.combo_start_ampm.get()

        eh, em, eampm = self._calculate_stop_time_from_start(sh, sm, sampm, offset_hours=6)
        self._set_combo_value(self.combo_stop_hour, eh)
        self._set_combo_value(self.combo_stop_min, em)
        self._set_combo_value(self.combo_stop_ampm, eampm)
        self._notify_change()

    def _on_stop_time_changed(self, _choice=None):
        """Validates stop time so it cannot be less than start hour / enforces minimum duration logic."""
        start_24 = self._to_24h(self.combo_start_hour.get(), self.combo_start_min.get(), self.combo_start_ampm.get())
        stop_24 = self._to_24h(self.combo_stop_hour.get(), self.combo_stop_min.get(), self.combo_stop_ampm.get())

        try:
            sh, sm = map(int, start_24.split(":"))
            eh, em = map(int, stop_24.split(":"))

            start_total_mins = sh * 60 + sm
            stop_total_mins = eh * 60 + em

            # If stop time is earlier than or equal to start time on the same schedule
            if stop_total_mins <= start_total_mins:
                eh_str, em_str, eampm_str = self._calculate_stop_time_from_start(
                    self.combo_start_hour.get(), self.combo_start_min.get(), self.combo_start_ampm.get(), offset_hours=6
                )
                self._set_combo_value(self.combo_stop_hour, eh_str)
                self._set_combo_value(self.combo_stop_min, em_str)
                self._set_combo_value(self.combo_stop_ampm, eampm_str)
        except Exception as e:
            logging.debug(f"Error validating stop time: {e}")

        self._notify_change()

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
        self._notify_change()

    def _notify_change(self):
        if self._on_config_changed:
            self._on_config_changed(self.get_config())

    def set_enabled(self, enabled: bool) -> None:
        if not enabled:
            self.check_obs_enabled.configure(state="disabled")
            for w in self._obs_connection_widgets + self._schedule_picker_widgets:
                w.configure(state="disabled")
        else:
            self.check_obs_enabled.configure(state="normal")
            self._on_toggle_obs_enabled()

    def load_config(self, config: dict) -> None:
        """Loads OBS settings into form widgets."""
        text_entries = [
            ("obs_host", self.entry_obs_host),
            ("obs_port", self.entry_obs_port),
            ("obs_password", self.entry_obs_password),
            ("obs_profile", self.entry_obs_profile),
            ("obs_scene_collection", self.entry_obs_scene_collection),
            ("obs_scene", self.entry_obs_scene),
        ]

        for key, widget in text_entries:
            widget.delete(0, "end")
            val = config.get(key, "")
            if val:
                widget.insert(0, str(val))

        checkboxes = [
            ("obs_enabled", self.check_obs_enabled),
            ("obs_auto_start", self.check_obs_auto_start),
            ("obs_auto_stop", self.check_obs_auto_stop),
            ("obs_schedule_enabled", self.check_obs_schedule),
        ]

        for key, widget in checkboxes:
            if config.get(key, 0):
                widget.select()
            else:
                widget.deselect()

        sh, sm, sampm = self._from_24h(str(config.get("obs_schedule_start_time", "10:00")), default_h=10, default_m=0)
        self._set_combo_value(self.combo_start_hour, sh)
        self._set_combo_value(self.combo_start_min, sm)
        self._set_combo_value(self.combo_start_ampm, sampm)

        eh, em, eampm = self._from_24h(str(config.get("obs_schedule_stop_time", "16:00")), default_h=16, default_m=0)
        self._set_combo_value(self.combo_stop_hour, eh)
        self._set_combo_value(self.combo_stop_min, em)
        self._set_combo_value(self.combo_stop_ampm, eampm)

        self._on_toggle_obs_enabled()

    def get_config(self) -> dict:
        """Returns the current OBS configuration as a dictionary."""
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
