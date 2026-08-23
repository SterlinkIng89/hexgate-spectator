import logging
import customtkinter as ctk
import psutil
from gui.fonts import get_small_font

class StatusFooter(ctk.CTkFrame):
    def __init__(self, master, version: str = "1.0.0", refresh_ms: int = 1000, **kwargs):
        kwargs.setdefault("fg_color", "#161616")
        kwargs.setdefault("border_width", 1)
        kwargs.setdefault("border_color", "#2a2a2a")
        kwargs.setdefault("corner_radius", 0)
        kwargs.setdefault("height", 28)
        super().__init__(master, **kwargs)
        self.pack_propagate(False)

        self._refresh_ms = refresh_ms
        self._process = psutil.Process()
        self._process.cpu_percent()  # First call initializes the counter; discard result.
        self._cpu_count = psutil.cpu_count() or 1

        font = get_small_font()

        self.ram_label = ctk.CTkLabel(self, text="RAM: — MB", font=font, text_color="#888888")
        self.ram_label.pack(side="left", padx=(12, 12), pady=4)

        self.cpu_label = ctk.CTkLabel(self, text="CPU: —%", font=font, text_color="#888888")
        self.cpu_label.pack(side="left", padx=(0, 12), pady=4)

        self.version_label = ctk.CTkLabel(self, text=f"v{version}", font=font, text_color="#555555")
        self.version_label.pack(side="right", padx=(0, 12), pady=4)

        self.after(200, self._update_metrics)

    def _update_metrics(self) -> None:
        try:
            ram_mb = self._process.memory_info().rss / (1024 * 1024)
            cpu_pct = self._process.cpu_percent() / self._cpu_count

            ram_text = f"RAM: {ram_mb:.0f} MB"
            cpu_text = f"CPU: {cpu_pct:.1f}%"

            if self.ram_label.cget("text") != ram_text:
                self.ram_label.configure(text=ram_text)
            if self.cpu_label.cget("text") != cpu_text:
                self.cpu_label.configure(text=cpu_text)
        except Exception as e:
            logging.error(f"Failed to update metrics: {e}")
            return  # Process no longer accessible; stop polling.

        self.after(self._refresh_ms, self._update_metrics)
