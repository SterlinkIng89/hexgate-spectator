import tkinter as tk
import customtkinter as ctk
from gui.fonts import get_small_font


class Tooltip:
    """
    Lightweight, flat-styled hover tooltip for CustomTkinter widgets.
    Displays informative hover text with clean dark mode styling without glow effects.
    """

    def __init__(self, widget: ctk.CTkBaseClass | tk.Widget, text: str, delay_ms: int = 150):
        self.widget = widget
        self.text = text
        self.delay_ms = delay_ms
        self._tip_window: tk.Toplevel | None = None
        self._after_id: str | None = None

        self.widget.bind("<Enter>", self._on_enter, add="+")
        self.widget.bind("<Leave>", self._on_leave, add="+")
        self.widget.bind("<ButtonPress>", self._on_leave, add="+")
        self.widget.bind("<Destroy>", self._on_destroy, add="+")

    def _on_enter(self, event=None):
        self._cancel_schedule()
        self._after_id = self.widget.after(self.delay_ms, self._show)

    def _on_leave(self, event=None):
        self._cancel_schedule()
        self._hide()

    def _on_destroy(self, event=None):
        self._cancel_schedule()
        self._hide()

    def _cancel_schedule(self):
        if self._after_id is not None:
            try:
                self.widget.after_cancel(self._after_id)
            except Exception:
                pass
            self._after_id = None

    def _show(self):
        if self._tip_window or not self.text:
            return

        try:
            # Determine popup placement relative to widget
            x = self.widget.winfo_rootx() + (self.widget.winfo_width() // 2)
            y = self.widget.winfo_rooty() + self.widget.winfo_height() + 4

            self._tip_window = tw = tk.Toplevel(self.widget)
            tw.wm_overrideredirect(True)
            tw.wm_attributes("-topmost", True)
            tw.wm_geometry(f"+{x}+{y}")

            frame = ctk.CTkFrame(
                tw,
                fg_color="#252525",
                border_color="#444444",
                border_width=1,
                corner_radius=6,
            )
            frame.pack(fill="both", expand=True)

            label = ctk.CTkLabel(
                frame,
                text=self.text,
                font=get_small_font(),
                text_color="#e0e0e0",
                justify="left",
                wraplength=280,
                padx=8,
                pady=6,
            )
            label.pack()
        except Exception:
            self._hide()

    def _hide(self):
        if self._tip_window:
            try:
                self._tip_window.destroy()
            except Exception:
                pass
            self._tip_window = None
