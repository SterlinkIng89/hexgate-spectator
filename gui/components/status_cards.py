import customtkinter as ctk
from gui.fonts import get_label_font, get_status_font, get_sub_font
from gui.components.surface_card import SurfaceCard

class StatusCards(ctk.CTkFrame):
    def __init__(self, master, **kwargs):
        kwargs.setdefault("fg_color", "transparent")
        super().__init__(master, **kwargs)

        label_font = get_label_font()
        status_font = get_status_font()
        sub_font = get_sub_font()

        self.columnconfigure(0, weight=1, uniform="status_cards")
        self.columnconfigure(1, weight=1, uniform="status_cards")

        # Left Card: LoL Bot Status
        self.bot_card = SurfaceCard(self)
        self.bot_card.grid(row=0, column=0, padx=(0, 5), sticky="nsew")

        self.bot_status_header = ctk.CTkFrame(self.bot_card, fg_color="transparent")
        self.bot_status_header.pack(pady=(8, 1))

        self.bot_status_dot = ctk.CTkLabel(self.bot_status_header, text="●", font=label_font, text_color="#e74c3c")
        self.bot_status_dot.pack(side="left", padx=(0, 6))

        self.bot_status_label = ctk.CTkLabel(self.bot_status_header, text="Bot: Stopped", font=status_font, text_color="#e74c3c")
        self.bot_status_label.pack(side="left")

        self.bot_detail_label = ctk.CTkLabel(self.bot_card, text="Spectator service offline", font=sub_font, text_color="#888888", anchor="center")
        self.bot_detail_label.pack(pady=(0, 8), padx=8, fill="x")

        # Right Card: OBS / Stream Status
        self.stream_card = SurfaceCard(self)
        self.stream_card.grid(row=0, column=1, padx=(5, 0), sticky="nsew")

        self.stream_status_header = ctk.CTkFrame(self.stream_card, fg_color="transparent")
        self.stream_status_header.pack(pady=(8, 1))

        self.stream_status_dot = ctk.CTkLabel(self.stream_status_header, text="●", font=label_font, text_color="#7f8c8d")
        self.stream_status_dot.pack(side="left", padx=(0, 6))

        self.stream_status_label = ctk.CTkLabel(self.stream_status_header, text="Stream: Ready", font=status_font, text_color="#7f8c8d")
        self.stream_status_label.pack(side="left")

        self.stream_detail_label = ctk.CTkLabel(self.stream_card, text="Start bot to begin monitoring", font=sub_font, text_color="#888888", anchor="center")
        self.stream_detail_label.pack(pady=(0, 8), padx=8, fill="x")

    def update_bot_status(self, color: str, title: str, detail: str) -> None:
        self.bot_status_dot.configure(text_color=color)
        self.bot_status_label.configure(text=f"Bot: {title}", text_color=color)
        self.bot_detail_label.configure(text=detail)

    def update_stream_status(self, color: str, label: str, detail: str) -> None:
        if self.stream_status_dot.cget("text_color") != color:
            self.stream_status_dot.configure(text_color=color)
        if self.stream_status_label.cget("text") != label or self.stream_status_label.cget("text_color") != color:
            self.stream_status_label.configure(text=label, text_color=color)
        if self.stream_detail_label.cget("text") != detail:
            self.stream_detail_label.configure(text=detail)
