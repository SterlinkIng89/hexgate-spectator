import os
import sys
import logging
import customtkinter as ctk

_fonts_initialized = False

# Font Family Identifiers
FONT_FAMILY_HEADING = "Montserrat"
FONT_FAMILY_UI = "Inter"
FONT_FAMILY_CONSOLE = "Consolas"


def get_fonts_dir() -> str:
    """Returns the absolute path to the bundled fonts directory."""
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        base_dir = getattr(sys, "_MEIPASS")
    else:
        base_dir = os.path.dirname(os.path.abspath(__file__))

    fonts_dir = os.path.join(base_dir, "assets", "fonts")
    if not os.path.exists(fonts_dir):
        # Alternative fallback in root
        alt_dir = os.path.join(base_dir, "gui", "assets", "fonts")
        if os.path.exists(alt_dir):
            return alt_dir
    return fonts_dir


def init_fonts() -> None:
    """Discovers and registers custom font assets into the application runtime."""
    global _fonts_initialized
    if _fonts_initialized:
        return

    fonts_dir = get_fonts_dir()
    if not os.path.exists(fonts_dir):
        logging.warning(f"Fonts directory not found at: {fonts_dir}. Using system fallbacks.")
        _fonts_initialized = True
        return

    font_files = [
        "Montserrat.ttf",
        "Inter.ttf",
    ]

    for fname in font_files:
        font_path = os.path.join(fonts_dir, fname)
        if os.path.exists(font_path):
            try:
                success = ctk.FontManager.load_font(font_path)
                if not success:
                    logging.warning(f"FontManager failed to load: {font_path}")
            except Exception as e:
                logging.warning(f"Error loading custom font {fname}: {e}")
        else:
            logging.debug(f"Custom font file {fname} not found in {fonts_dir}")

    _fonts_initialized = True


# --- CTkFont Factory Helpers ---

def get_title_font() -> ctk.CTkFont:
    """Font for main window title / accent headers (Montserrat 22pt Bold)."""
    return ctk.CTkFont(family=FONT_FAMILY_HEADING, size=22, weight="bold")


def get_section_font() -> ctk.CTkFont:
    """Font for section headers and collapsible frame headers (Montserrat 14pt Bold)."""
    return ctk.CTkFont(family=FONT_FAMILY_HEADING, size=14, weight="bold")


def get_status_font() -> ctk.CTkFont:
    """Font for status card indicators and service labels (Inter 15pt Bold)."""
    return ctk.CTkFont(family=FONT_FAMILY_UI, size=15, weight="bold")


def get_button_font() -> ctk.CTkFont:
    """Font for primary action buttons (Inter 15pt Bold)."""
    return ctk.CTkFont(family=FONT_FAMILY_UI, size=15, weight="bold")


def get_label_font() -> ctk.CTkFont:
    """Font for form labels, entries, switches, and dropdowns (Inter 13pt Regular)."""
    return ctk.CTkFont(family=FONT_FAMILY_UI, size=13)


def get_sub_font() -> ctk.CTkFont:
    """Font for secondary labels, subheaders, and helper descriptions (Inter 12pt Regular)."""
    return ctk.CTkFont(family=FONT_FAMILY_UI, size=12)


def get_small_font() -> ctk.CTkFont:
    """Font for footer metrics, small action buttons, and fine print (Inter 11pt Regular)."""
    return ctk.CTkFont(family=FONT_FAMILY_UI, size=11)


def get_console_font() -> ctk.CTkFont:
    """Monospaced font for log console and ASCII art banner (Consolas 12pt)."""
    return ctk.CTkFont(family=FONT_FAMILY_CONSOLE, size=12)
