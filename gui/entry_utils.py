from typing import Any
import customtkinter as ctk


def set_entry_text(entry: ctk.CTkEntry, text: Any) -> None:
    """
    Safely sets the text in a CTkEntry widget.

    If text is non-empty, it inserts the text and deactivates the placeholder.
    If text is empty or None, it clears the entry and immediately reactivates
    the placeholder text without requiring user interaction or focus events.
    """
    entry.delete(0, "end")
    if text is not None and str(text) != "":
        entry.insert(0, str(text))
    else:
        entry._activate_placeholder()
