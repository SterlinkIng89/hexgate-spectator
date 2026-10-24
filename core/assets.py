"""Local asset resolution and brand asset loading utilities.

Provides centralized helpers to locate and load repository media, application
icons, and UI emblems across both standard source checkouts and PyInstaller bundles.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional, Tuple
from PIL import Image
import customtkinter as ctk


def get_assets_dir() -> Path:
    """Returns the root assets directory path.

    Handles PyInstaller bundled builds via sys._MEIPASS as well as
    standard development repository layouts.
    """
    if hasattr(sys, "_MEIPASS"):
        bundle_dir = Path(getattr(sys, "_MEIPASS"))
        bundled_assets = bundle_dir / "assets"
        if bundled_assets.is_dir():
            return bundled_assets
        return bundle_dir

    # Standard repo layout: <project_root>/assets
    return Path(__file__).resolve().parent.parent / "assets"


def get_asset_path(relative_path: str) -> Optional[Path]:
    """Resolves a relative asset path to an existing absolute Path.

    Args:
        relative_path: Sub-path relative to the assets directory (e.g. 'branding/hexgate_logo.png').

    Returns:
        Path object if the asset file exists on disk, None otherwise.
    """
    target = get_assets_dir() / relative_path
    if target.is_file():
        return target
    return None


def get_icon_path() -> Optional[str]:
    """Returns the absolute string path to the application .ico file, or None."""
    path = get_asset_path("branding/hexgate_icon.ico")
    return str(path) if path else None


def get_logo_image(size: Tuple[int, int] = (28, 28)) -> Optional[ctk.CTkImage]:
    """Loads the application emblem as a CTkImage for CustomTkinter UI display.

    Args:
        size: Tuple of (width, height) in pixels.

    Returns:
        ctk.CTkImage if the branding logo file exists and loads successfully, None otherwise.
    """
    path = get_asset_path("branding/hexgate_logo.png")
    if not path:
        return None

    try:
        pil_img = Image.open(path)
        return ctk.CTkImage(light_image=pil_img, dark_image=pil_img, size=size)
    except Exception:
        return None
