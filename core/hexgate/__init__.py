"""
Hexgate Spectator Automation Package.

Public API:
    start_bot(callback, config_data)  — start the bot
    stop_bot()                        — stop the bot
    BOT_CONFIG                        — current configuration dict

Note: lcu_driver patching is applied explicitly inside engine.py, immediately
before the Connector is instantiated. It is NOT triggered on package import.
"""

from .config import BOT_CONFIG
from .engine import start_bot, stop_bot

__all__ = [
    "start_bot",
    "stop_bot",
    "BOT_CONFIG"
]
