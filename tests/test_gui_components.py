import pytest
import customtkinter as ctk
from gui.components.status_cards import StatusCards
from gui.components.youtube_panel import YouTubePanel
from gui.components.collapsible_frame import CollapsibleFrame
from gui.components.console_toolbar import ConsoleToolbar
from gui.components.status_footer import StatusFooter
from gui.components.lol_settings_form import LolSettingsForm
from gui.components.obs_settings_form import ObsSettingsForm

SURFACE_COLOR = "#1e1e1e"
BORDER_COLOR = "#333333"

@pytest.fixture(scope="module")
def tk_root():
    root = ctk.CTk()
    yield root
    root.destroy()

def test_status_cards_style(tk_root):
    comp = StatusCards(tk_root)
    assert comp.cget("fg_color") == "transparent"
    assert comp.bot_card.cget("fg_color") == SURFACE_COLOR
    assert comp.bot_card.cget("border_color") == BORDER_COLOR
    assert comp.bot_card.cget("border_width") == 1
    assert comp.stream_card.cget("fg_color") == SURFACE_COLOR
    assert comp.stream_card.cget("border_color") == BORDER_COLOR
    assert comp.stream_card.cget("border_width") == 1

def test_status_footer_style(tk_root):
    comp = StatusFooter(tk_root, version="1.0")
    assert comp.cget("fg_color") == SURFACE_COLOR

def test_youtube_panel_style(tk_root):
    comp = YouTubePanel(tk_root)
    assert comp.cget("fg_color") == SURFACE_COLOR
    assert comp.cget("border_color") == BORDER_COLOR
    assert comp.cget("border_width") == 1

def test_collapsible_frame_style(tk_root):
    comp = CollapsibleFrame(tk_root, title="Test")
    assert comp.cget("fg_color") == SURFACE_COLOR
    assert comp.cget("border_color") == BORDER_COLOR
    assert comp.cget("border_width") == 1

def test_settings_forms_style(tk_root):
    comp1 = LolSettingsForm(tk_root)
    assert comp1.cget("fg_color") == SURFACE_COLOR
    assert comp1.cget("border_color") == BORDER_COLOR
    assert comp1.cget("border_width") == 1
    
    comp2 = ObsSettingsForm(tk_root)
    assert comp2.cget("fg_color") == SURFACE_COLOR
    assert comp2.cget("border_color") == BORDER_COLOR
    assert comp2.cget("border_width") == 1
