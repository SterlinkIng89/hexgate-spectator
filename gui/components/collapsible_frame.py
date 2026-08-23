import customtkinter as ctk

class CollapsibleFrame(ctk.CTkFrame):
    def __init__(self, master, title: str, **kwargs):
        super().__init__(master, **kwargs)
        self.title_text = title
        self.is_collapsed = False

        self.header_btn = ctk.CTkButton(
            self,
            text=f"▼  {self.title_text}",
            anchor="w",
            fg_color="transparent",
            hover_color="#2b2b2b",
            text_color="#ffffff",
            font=ctk.CTkFont(family="Roboto", size=14, weight="bold"),
            height=28,
            command=self.toggle,
        )
        self.header_btn.pack(fill="x", padx=8, pady=(6, 4))

        self.content_frame = ctk.CTkFrame(self, fg_color="transparent")
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
