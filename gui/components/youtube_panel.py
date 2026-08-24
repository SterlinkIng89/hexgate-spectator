import logging
import customtkinter as ctk
from core.youtube_manager import youtube_manager
from gui.fonts import get_label_font, get_status_font, get_sub_font, get_small_font

logger = logging.getLogger(__name__)

class YouTubePanel(ctk.CTkFrame):
    """
    Control card for YouTube Live Stream integration:
    - OAuth account status & connect/disconnect button.
    - Customizable stream title with {date} placeholder support.
    - Live watch URL indicator with one-click copy button.
    """
    def __init__(self, master, on_config_changed=None, **kwargs):
        kwargs.setdefault("fg_color", "#1e1e1e")
        kwargs.setdefault("border_width", 1)
        kwargs.setdefault("border_color", "#333333")
        kwargs.setdefault("corner_radius", 8)
        super().__init__(master, **kwargs)

        self._on_config_changed = on_config_changed
        self._current_stream_url = ""

        label_font = get_label_font()
        status_font = get_status_font()
        sub_font = get_sub_font()
        small_font = get_small_font()

        # Top row: Status & Auth Action
        self.header_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.header_frame.pack(fill="x", padx=12, pady=(10, 4))

        self.status_dot = ctk.CTkLabel(self.header_frame, text="●", font=label_font, text_color="#7f8c8d")
        self.status_dot.pack(side="left", padx=(0, 6))

        self.account_label = ctk.CTkLabel(
            self.header_frame,
            text="YouTube: Disconnected",
            font=status_font,
            text_color="#ffffff",
            anchor="w"
        )
        self.account_label.pack(side="left", fill="x", expand=True)

        self.check_yt_enabled = ctk.CTkSwitch(
            self.header_frame,
            text="Auto-create stream",
            font=sub_font,
            command=self._on_toggle_enabled
        )
        self.check_yt_enabled.pack(side="right", padx=(8, 0))

        self.btn_auth = ctk.CTkButton(
            self.header_frame,
            text="Link Account",
            font=small_font,
            width=105,
            height=28,
            command=self._toggle_auth
        )
        self.btn_auth.pack(side="right", padx=(8, 4))

        # Middle row: Stream Title Entry
        self.title_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.title_frame.pack(fill="x", padx=12, pady=(4, 6))

        self.lbl_title = ctk.CTkLabel(self.title_frame, text="Stream Title:", font=label_font, width=90, anchor="w")
        self.lbl_title.pack(side="left", padx=(0, 6))

        self.entry_stream_title = ctk.CTkEntry(
            self.title_frame,
            placeholder_text="e.g. EST vs INTZ - {date}",
            font=label_font
        )
        self.entry_stream_title.pack(side="left", fill="x", expand=True)
        self.entry_stream_title.insert(0, "EST vs INTZ - {date}")

        # Discord Webhook row
        self.discord_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.discord_frame.pack(fill="x", padx=12, pady=(0, 6))

        self.lbl_discord = ctk.CTkLabel(self.discord_frame, text="Discord:", font=label_font, width=90, anchor="w")
        self.lbl_discord.pack(side="left", padx=(0, 6))

        self.check_discord_enabled = ctk.CTkSwitch(
            self.discord_frame,
            text="Post link",
            font=sub_font,
            command=self._on_toggle_discord_enabled
        )
        self.check_discord_enabled.pack(side="right", padx=(8, 0))

        self.entry_discord_webhook = ctk.CTkEntry(
            self.discord_frame,
            placeholder_text="Optional: Webhook URL to auto-post stream link",
            font=label_font
        )
        self.entry_discord_webhook.pack(side="left", fill="x", expand=True)

        # Bottom row: Live Stream URL & Copy action (visible once created)
        self.link_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.link_frame.pack(fill="x", padx=12, pady=(0, 8))

        self.lbl_link_caption = ctk.CTkLabel(self.link_frame, text="Stream Link:", font=sub_font, text_color="#888888", width=90, anchor="w")
        self.lbl_link_caption.pack(side="left", padx=(0, 6))

        self.lbl_stream_url = ctk.CTkLabel(
            self.link_frame,
            text="No active broadcast",
            font=sub_font,
            text_color="#888888",
            anchor="w"
        )
        self.lbl_stream_url.pack(side="left", fill="x", expand=True)

        self.btn_copy_link = ctk.CTkButton(
            self.link_frame,
            text="Copy Link",
            font=small_font,
            width=85,
            height=24,
            state="disabled",
            command=self._copy_stream_url
        )
        self.btn_copy_link.pack(side="right")

        # Check existing credentials on startup
        self.refresh_auth_state()

    def refresh_auth_state(self):
        """Checks if YouTube token exists and updates UI labels and button text."""
        try:
            if youtube_manager.is_authenticated() or youtube_manager.authenticate(force_interactive=False):
                name = youtube_manager.channel_name or "Connected"
                self.status_dot.configure(text_color="#2ecc71")
                self.account_label.configure(text=f"YouTube: {name}", text_color="#2ecc71")
                self.btn_auth.configure(text="Disconnect", fg_color="#444444", hover_color="#555555")
            else:
                self.status_dot.configure(text_color="#7f8c8d")
                self.account_label.configure(text="YouTube: Disconnected", text_color="#ffffff")
                self.btn_auth.configure(text="Link Account", fg_color=["#3a7ebf", "#1f538d"], hover_color=["#325882", "#14375e"])
        except Exception as e:
            logger.debug(f"[YouTube UI] Auth refresh error: {e}")
            self.status_dot.configure(text_color="#e74c3c")
            self.account_label.configure(text="YouTube: Error", text_color="#e74c3c")

    def _toggle_auth(self):
        """Triggers login flow or logs out if already connected."""
        if youtube_manager.is_authenticated():
            youtube_manager.logout()
            self.refresh_auth_state()
            self.update_stream_url("")
            self._notify_change()
        else:
            if not youtube_manager.is_configured():
                self.status_dot.configure(text_color="#e74c3c")
                self.account_label.configure(text="YouTube: client_secret.json missing", text_color="#e74c3c")
                return

            self.btn_auth.configure(state="disabled", text="Connecting...")
            self.status_dot.configure(text_color="#f1c40f")
            self.account_label.configure(text="YouTube: Logging in...", text_color="#f1c40f")

            def on_done(success, msg):
                def _apply():
                    self.btn_auth.configure(state="normal")
                    self.refresh_auth_state()
                    self._notify_change()
                self.after(0, _apply)

            youtube_manager.authenticate(force_interactive=True, on_completed=on_done)

    def _on_toggle_enabled(self):
        is_on = self.check_yt_enabled.get() == 1
        state = "normal" if is_on else "disabled"
        self.entry_stream_title.configure(state=state)
        
        if not is_on:
            self.check_discord_enabled.configure(state="disabled")
            self.entry_discord_webhook.configure(state="disabled")
        else:
            self.check_discord_enabled.configure(state="normal")
            discord_on = self.check_discord_enabled.get() == 1
            self.entry_discord_webhook.configure(state="normal" if discord_on else "disabled")
            
        self._notify_change()

    def _on_toggle_discord_enabled(self):
        discord_on = self.check_discord_enabled.get() == 1 and self.check_yt_enabled.get() == 1
        self.entry_discord_webhook.configure(state="normal" if discord_on else "disabled")
        self._notify_change()

    def update_stream_url(self, url: str):
        """Displays the generated live stream URL and enables copy button."""
        self._current_stream_url = url.strip() if url else ""
        if self._current_stream_url:
            self.lbl_stream_url.configure(text=self._current_stream_url, text_color="#5dade2")
            self.btn_copy_link.configure(state="normal", text="Copy Link")
        else:
            self.lbl_stream_url.configure(text="No active broadcast", text_color="#888888")
            self.btn_copy_link.configure(state="disabled", text="Copy Link")

    def _copy_stream_url(self):
        """Copies stream URL to clipboard with quick visual confirmation."""
        if not self._current_stream_url:
            return
        try:
            self.clipboard_clear()
            self.clipboard_append(self._current_stream_url)
            self.btn_copy_link.configure(text="Copied!")
            self.after(1500, lambda: self.btn_copy_link.configure(text="Copy Link") if self._current_stream_url else None)
        except Exception as e:
            logger.error(f"[YouTube UI] Failed to copy to clipboard: {e}")

    def _notify_change(self):
        if self._on_config_changed:
            self._on_config_changed(self.get_config())

    def set_enabled(self, enabled: bool):
        """Enables/disables UI input controls during bot execution."""
        state = "normal" if enabled else "disabled"
        if enabled:
            is_on = self.check_yt_enabled.get() == 1
            self.entry_stream_title.configure(state="normal" if is_on else "disabled")
            self.check_yt_enabled.configure(state="normal")
            self.btn_auth.configure(state="normal")
            self.check_discord_enabled.configure(state="normal" if is_on else "disabled")
            discord_on = self.check_discord_enabled.get() == 1
            self.entry_discord_webhook.configure(state="normal" if (is_on and discord_on) else "disabled")
        else:
            self.entry_stream_title.configure(state="disabled")
            self.check_discord_enabled.configure(state="disabled")
            self.entry_discord_webhook.configure(state="disabled")
            self.check_yt_enabled.configure(state="disabled")
            self.btn_auth.configure(state="disabled")

    def load_config(self, config: dict):
        """Populates fields from saved configuration."""
        title = config.get("yt_stream_title", "EST vs INTZ - {date}")
        if title == "[EST vs INTZ - {date}]":
            title = "EST vs INTZ - {date}"
        self.entry_stream_title.delete(0, "end")
        self.entry_stream_title.insert(0, str(title))
        
        discord_webhook = config.get("discord_webhook_url", "")
        self.entry_discord_webhook.delete(0, "end")
        if discord_webhook:
            self.entry_discord_webhook.insert(0, str(discord_webhook))

        discord_enabled = config.get("discord_enabled", 1)
        if discord_enabled:
            self.check_discord_enabled.select()
        else:
            self.check_discord_enabled.deselect()

        yt_enabled = config.get("yt_enabled", 1)
        if yt_enabled:
            self.check_yt_enabled.select()
        else:
            self.check_yt_enabled.deselect()

        self._on_toggle_enabled()
        self.refresh_auth_state()

    def get_config(self) -> dict:
        """Returns current YouTube & Discord settings dictionary."""
        return {
            "yt_enabled": self.check_yt_enabled.get() == 1,
            "yt_stream_title": self.entry_stream_title.get().strip() or "EST vs INTZ - {date}",
            "discord_enabled": self.check_discord_enabled.get() == 1,
            "discord_webhook_url": self.entry_discord_webhook.get().strip()
        }
