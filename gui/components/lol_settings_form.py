import customtkinter as ctk
from gui.components.collapsible_frame import CollapsibleFrame
from gui.fonts import get_label_font


class LolSettingsForm(CollapsibleFrame):
    def __init__(self, master, **kwargs):
        kwargs.setdefault("title", "League Client Settings")
        kwargs.setdefault("border_width", 1)
        kwargs.setdefault("border_color", "#333333")
        super().__init__(master, **kwargs)

        label_font = get_label_font()

        self.content_frame.columnconfigure(0, weight=1)
        self.content_frame.columnconfigure(1, weight=1)
        self.content_frame.columnconfigure(2, weight=1)
        self.content_frame.columnconfigure(3, weight=1)

        ctk.CTkLabel(self.content_frame, text="Lobby Name(s):", font=label_font).grid(row=0, column=0, padx=10, pady=4, sticky="w")
        self.entry_lobby = ctk.CTkEntry(self.content_frame, placeholder_text="e.g.: est, vks", font=label_font, width=140)
        self.entry_lobby.grid(row=0, column=1, padx=10, pady=4, sticky="we")

        ctk.CTkLabel(self.content_frame, text="Passwords:", font=label_font).grid(row=0, column=2, padx=10, pady=4, sticky="w")
        self.entry_passwords = ctk.CTkEntry(self.content_frame, placeholder_text="e.g.: 123, test", font=label_font, width=140)
        self.entry_passwords.grid(row=0, column=3, padx=10, pady=4, sticky="we")

        ctk.CTkLabel(self.content_frame, text="Camera Delay (s):", font=label_font).grid(row=1, column=0, padx=10, pady=4, sticky="w")
        self.entry_delay = ctk.CTkEntry(self.content_frame, font=label_font, width=140)
        self.entry_delay.grid(row=1, column=1, padx=10, pady=4, sticky="we")

        ctk.CTkLabel(self.content_frame, text="Ignored Words:", font=label_font).grid(row=1, column=2, padx=10, pady=4, sticky="w")
        self.entry_ignored = ctk.CTkEntry(self.content_frame, placeholder_text="e.g.: Academy, AC", font=label_font, width=140)
        self.entry_ignored.grid(row=1, column=3, padx=10, pady=4, sticky="we")

        self.check_invite_only = ctk.CTkSwitch(self.content_frame, text="Invite Only Mode (Don't search)", font=label_font)
        self.check_invite_only.grid(row=2, column=0, columnspan=4, padx=10, pady=6, sticky="w")

        self._widgets = [
            self.entry_lobby,
            self.entry_passwords,
            self.entry_delay,
            self.entry_ignored,
            self.check_invite_only,
        ]

    def set_enabled(self, enabled: bool) -> None:
        state = "normal" if enabled else "disabled"
        for w in self._widgets:
            w.configure(state=state)

    def load_config(self, config: dict) -> None:
        self.entry_lobby.delete(0, "end")
        val = config.get("lobby_name", "")
        if val:
            self.entry_lobby.insert(0, str(val))

        self.entry_passwords.delete(0, "end")
        val = config.get("passwords", "")
        if val:
            self.entry_passwords.insert(0, str(val))

        self.entry_delay.delete(0, "end")
        self.entry_delay.insert(0, str(config.get("camera_delay", "3")))

        self.entry_ignored.delete(0, "end")
        val = config.get("ignored_words", "")
        if val:
            self.entry_ignored.insert(0, str(val))

        if config.get("invite_only", 0):
            self.check_invite_only.select()
        else:
            self.check_invite_only.deselect()

    def get_config(self) -> dict:
        return {
            "lobby_name": self.entry_lobby.get().strip(),
            "passwords": self.entry_passwords.get().strip(),
            "camera_delay": self.entry_delay.get().strip(),
            "ignored_words": self.entry_ignored.get().strip(),
            "invite_only": self.check_invite_only.get(),
        }

    def get_runtime_config(self) -> dict:
        passwords_raw = self.entry_passwords.get()
        passwords = [p.strip() for p in passwords_raw.split(",")] if passwords_raw else []
        ignored_raw = self.entry_ignored.get()
        ignored = [w.strip() for w in ignored_raw.split(",")] if ignored_raw else []
        try:
            cam_delay = float(self.entry_delay.get())
        except ValueError:
            cam_delay = 3.0

        return {
            "lobby_name": self.entry_lobby.get().strip(),
            "passwords": passwords,
            "camera_delay": cam_delay,
            "ignored_words": ignored,
            "invite_only": self.check_invite_only.get() == 1,
        }
