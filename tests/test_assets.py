"""Unit tests for local media asset resolver module core/assets.py."""

from pathlib import Path
from unittest.mock import patch
import pytest
import customtkinter as ctk

from core.assets import (
    get_assets_dir,
    get_asset_path,
    get_icon_path,
    get_logo_image,
)


def test_get_assets_dir_default():
    assets_dir = get_assets_dir()
    assert isinstance(assets_dir, Path)
    assert assets_dir.name == "assets"
    assert assets_dir.is_dir()


def test_get_assets_dir_meipass(tmp_path, monkeypatch):
    bundle_assets = tmp_path / "assets"
    bundle_assets.mkdir()
    monkeypatch.setattr("sys._MEIPASS", str(tmp_path), raising=False)

    resolved = get_assets_dir()
    assert resolved == bundle_assets


def test_get_assets_dir_meipass_fallback_to_root(tmp_path, monkeypatch):
    # When assets subdirectory does not exist inside _MEIPASS
    monkeypatch.setattr("sys._MEIPASS", str(tmp_path), raising=False)

    resolved = get_assets_dir()
    assert resolved == tmp_path


def test_get_asset_path_existing():
    logo_path = get_asset_path("branding/hexgate_logo.png")
    assert logo_path is not None
    assert isinstance(logo_path, Path)
    assert logo_path.is_file()
    assert logo_path.name == "hexgate_logo.png"


def test_get_asset_path_missing():
    missing_path = get_asset_path("branding/non_existent_file_xyz.png")
    assert missing_path is None


def test_get_icon_path():
    icon_path = get_icon_path()
    assert icon_path is not None
    assert isinstance(icon_path, str)
    assert icon_path.endswith(".ico")
    assert Path(icon_path).is_file()


def test_get_logo_image():
    # In headless environments, CustomTkinter Image initialization requires Tk
    # We can safely test CTkImage instantiation or verify the fallback logic
    logo_img = get_logo_image(size=(32, 32))
    assert logo_img is not None
    assert isinstance(logo_img, ctk.CTkImage)
    assert logo_img._size == (32, 32)


def test_get_logo_image_missing(monkeypatch):
    with patch("core.assets.get_asset_path", return_value=None):
        assert get_logo_image() is None


def test_get_logo_image_corrupt_file(tmp_path, monkeypatch):
    corrupt_file = tmp_path / "corrupt.png"
    corrupt_file.write_text("not an image content")
    with patch("core.assets.get_asset_path", return_value=corrupt_file):
        assert get_logo_image() is None
