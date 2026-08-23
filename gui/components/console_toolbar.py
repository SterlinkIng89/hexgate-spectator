import os
import sys
import logging
import subprocess
import customtkinter as ctk
from gui.fonts import get_section_font, get_sub_font

class ConsoleToolbar(ctk.CTkFrame):
    def __init__(self, master, get_log_text, logs_dir: str, title: str = "Logs", **kwargs):
        kwargs.setdefault("fg_color", "transparent")
        super().__init__(master, **kwargs)

        self._get_log_text = get_log_text
        self._logs_dir = logs_dir

        section_font = get_section_font()
        btn_font = get_sub_font()

        self.lbl_title = ctk.CTkLabel(self, text=title, font=section_font, text_color="#ffffff")
        self.lbl_title.pack(side="left")

        self.btn_copy = ctk.CTkButton(
            self,
            text="Copy Logs",
            width=80,
            height=26,
            font=btn_font,
            fg_color="transparent",
            border_width=1,
            border_color="#333333",
            hover_color="#2b2b2b",
            command=self._copy_logs,
        )
        self.btn_copy.pack(side="right", padx=(4, 0))

        self.btn_open_folder = ctk.CTkButton(
            self,
            text="Open Folder",
            width=90,
            height=26,
            font=btn_font,
            fg_color="transparent",
            border_width=1,
            border_color="#333333",
            hover_color="#2b2b2b",
            command=self._open_logs_folder,
        )
        self.btn_open_folder.pack(side="right", padx=(0, 4))

    def _copy_logs(self) -> None:
        try:
            text = self._get_log_text()
            self.clipboard_clear()
            self.clipboard_append(text)
            self.btn_copy.configure(text="Copied!")
            self.after(2000, lambda: self.btn_copy.configure(text="Copy Logs"))
        except Exception as e:
            logging.error(f"Failed to copy logs: {e}")

    def _open_logs_folder(self) -> None:
        try:
            if not os.path.exists(self._logs_dir):
                os.makedirs(self._logs_dir, exist_ok=True)
            if sys.platform == "win32":
                os.startfile(self._logs_dir)
            elif sys.platform == "darwin":
                subprocess.Popen(["open", self._logs_dir])
            else:
                subprocess.Popen(["xdg-open", self._logs_dir])
        except Exception as e:
            logging.error(f"Failed to open logs directory: {e}")
