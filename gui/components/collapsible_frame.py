import customtkinter as ctk
from gui.fonts import get_section_font, get_small_font
from gui.components.surface_card import SurfaceCard

class CollapsibleFrame(SurfaceCard):
    def __init__(self, master, title: str, collapsed: bool = False, **kwargs):
        super().__init__(master, **kwargs)
        self.title_text = title
        self.is_collapsed = collapsed
        self._summary_text = ""

        self.header_frame = ctk.CTkFrame(self, fg_color="transparent", height=28)
        self.header_frame.pack(fill="x", padx=8, pady=(6, 4))

        self.summary_label = ctk.CTkLabel(
            self.header_frame,
            text="",
            font=get_small_font(),
            text_color="#888888",
            anchor="e",
            cursor="hand2",
        )
        self.summary_label.pack(side="right", padx=(8, 4))
        self.summary_label.bind("<Button-1>", lambda _: self.toggle())

        arrow = "▶" if self.is_collapsed else "▼"
        self.header_btn = ctk.CTkButton(
            self.header_frame,
            text=f"{arrow}  {self.title_text}",
            anchor="w",
            fg_color="transparent",
            hover_color="#2b2b2b",
            text_color="#ffffff",
            font=get_section_font(),
            height=28,
            command=self.toggle,
        )
        self.header_btn.pack(side="left", fill="x", expand=True)

        self.content_frame = ctk.CTkFrame(self, fg_color="transparent")
        if not self.is_collapsed:
            self.content_frame.pack(fill="both", expand=True, padx=4, pady=(0, 6))

    def set_summary(self, text: str) -> None:
        self._summary_text = text
        if self.is_collapsed:
            self.summary_label.configure(text=text)
        else:
            self.summary_label.configure(text="")

    def toggle(self):
        if self.is_collapsed:
            self.content_frame.pack(fill="both", expand=True, padx=4, pady=(0, 6))
            self.header_btn.configure(text=f"▼  {self.title_text}")
            self.is_collapsed = False
            self.summary_label.configure(text="")
        else:
            self.content_frame.pack_forget()
            self.header_btn.configure(text=f"▶  {self.title_text}")
            self.is_collapsed = True
            self.summary_label.configure(text=self._summary_text)
