"""Console startup banner and system info rendering module.

Provides a stylized ASCII art banner and application metadata overview
inspired by modern developer terminals (Docker Desktop, etc.).
"""

import customtkinter as ctk

# ASCII Artwork & Branding — replace these lines to update the logo/icon (Issue #32)
ASCII_ICON = [
    " ",
    " ",
    " ",
    " ",
    " ",
    " ",
]

ASCII_TITLE = [
    "    ██╗  ██╗███████╗██╗  ██╗ ██████╗  █████╗ ████████╗███████╗",
    "    ██║  ██║██╔════╝╚██╗██╔╝██╔════╝ ██╔══██╗╚══██╔══╝██╔════╝",
    "    ███████║█████╗   ╚███╔╝ ██║  ███╗███████║   ██║   █████╗  ",
    "    ██╔══██║██╔══╝   ██╔██╗ ██║   ██║██╔══██║   ██║   ██╔══╝  ",
    "    ██║  ██║███████╗██╔╝ ██╗╚██████╔╝██║  ██║   ██║   ███████╗",
    "    ╚═╝  ╚═╝╚══════╝╚═╝  ╚═╝ ╚═════╝ ╚═╝  ╚═╝   ╚═╝   ╚══════╝",
]

ASCII_SUBTITLE = "                     S P E C T A T O R"

# Atomic palette — change a color here to update all roles that share it.
_PALETTE = {
    "blue":     "#3498db",
    "cyan":     "#5dade2",
    "green":    "#2ecc71",
    "white":    "#ffffff",
    "muted":    "#888888",
    "offwhite": "#e0e0e0",
    "dim":      "#555555",
}

# Role → color mapping. Keys become tag names prefixed with "banner_".
BANNER_THEME = {
    "icon":       _PALETTE["cyan"],
    "logo":       _PALETTE["blue"],
    "subtitle":   _PALETTE["cyan"],
    "section":    _PALETTE["white"],
    "check":      _PALETTE["green"],
    "label":      _PALETTE["muted"],
    "value":      _PALETTE["offwhite"],
    "tip_bullet": _PALETTE["blue"],
    "dim":        _PALETTE["dim"],
}


def _setup_tags(tk_textbox) -> None:
    for role, color in BANNER_THEME.items():
        tk_textbox.tag_config(f"banner_{role}", foreground=color)


def render_startup_banner(
    textbox: ctk.CTkTextbox,
    version: str = "1.0.0",
    client_status: str = "Ready (LCU auto-detect)",
    obs_status: str = "Configured (WebSocket)",
) -> None:
    """Renders the ASCII banner, system status, and tips into the console textbox."""
    tk_text = textbox._textbox  # Direct access to the underlying Tk Text widget
    _setup_tags(tk_text)

    prev_state = textbox.cget("state")
    if prev_state == "disabled":
        textbox.configure(state="normal")

    for icon_line, title_line in zip(ASCII_ICON, ASCII_TITLE):
        tk_text.insert("end", icon_line, "banner_icon")
        tk_text.insert("end", title_line + "\n", "banner_logo")
    tk_text.insert("end", ASCII_SUBTITLE + "\n\n", "banner_subtitle")

    tk_text.insert("end", "  System Status:\n", "banner_section")
    tk_text.insert("end", "  ✓ ", "banner_check")
    tk_text.insert("end", "LoL Client:       ", "banner_label")
    tk_text.insert("end", f"{client_status}\n", "banner_value")
    tk_text.insert("end", "  ✓ ", "banner_check")
    tk_text.insert("end", "OBS Integration:  ", "banner_label")
    tk_text.insert("end", f"{obs_status}\n", "banner_value")
    tk_text.insert("end", "  ✓ ", "banner_check")
    tk_text.insert("end", "Mode:             ", "banner_label")
    tk_text.insert("end", "Auto Spectator\n\n", "banner_value")

    tk_text.insert("end", "  Quick Tips:\n", "banner_section")
    tk_text.insert("end", "  › ", "banner_tip_bullet")
    tk_text.insert("end", "Click 'Start Bot' to begin monitoring and spectating.\n", "banner_value")
    tk_text.insert("end", "  › ", "banner_tip_bullet")
    tk_text.insert("end", "Configure lobby names and passwords in settings above.\n\n", "banner_value")

    tk_text.insert("end", f"{' ' * 54}Version: {version}\n", "banner_dim")
    tk_text.insert("end", "─" * 70 + "\n\n", "banner_dim")

    if prev_state == "disabled":
        textbox.configure(state="disabled")


