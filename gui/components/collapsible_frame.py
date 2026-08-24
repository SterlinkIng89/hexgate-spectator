import customtkinter as ctk
from gui.fonts import get_section_font
from gui.components.surface_card import SurfaceCard

class CollapsibleFrame(SurfaceCard):
    def __init__(self, master, title: str, collapsed: bool = False, **kwargs):
        super().__init__(master, **kwargs)
        self.title_text = title
        self.is_collapsed = collapsed

        arrow = "▶" if self.is_collapsed else "▼"
        self.header_btn = ctk.CTkButton(
            self,
            text=f"{arrow}  {self.title_text}",
            anchor="w",
            fg_color="transparent",
            hover_color="#2b2b2b",
            text_color="#ffffff",
            font=get_section_font(),
            height=28,
            command=self.toggle,
        )
        self.header_btn.pack(fill="x", padx=8, pady=(6, 4))

        self.content_frame = ctk.CTkFrame(self, fg_color="transparent")
        if not self.is_collapsed:
            self.content_frame.pack(fill="both", expand=True, padx=4, pady=(0, 6))

    def toggle(self):
        if self.is_collapsed:
            self.content_frame.pack(fill="both", expand=True, padx=4, pady=(0, 6))
            self.header_btn.configure(text=f"▼  {self.title_text}")
            self.is_collapsed = False
        else:
            self.content_frame.pack_forget()
            self.header_btn.configure(text=f"▶  {self.title_text}")
            self.is_collapsed = True
