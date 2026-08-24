import customtkinter as ctk

class SurfaceCard(ctk.CTkFrame):
    """
    Standardized container surface for all Hexgate UI panels.
    Enforces a consistent dark background, border width, border color, and corner radius.
    """
    def __init__(self, master, **kwargs):
        kwargs.setdefault("fg_color", "#1e1e1e")
        kwargs.setdefault("border_width", 1)
        kwargs.setdefault("border_color", "#333333")
        kwargs.setdefault("corner_radius", 8)
        super().__init__(master, **kwargs)
