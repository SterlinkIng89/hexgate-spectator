"""
Global state management for Hexgate Spectator Bot.
Only shared, high-level state lives here.
Module-local tracking (watchdog, lobby dedup) lives in their respective modules.
"""

import logging

logger = logging.getLogger("Hexgate")


class BotState:
    def __init__(self):
        # Bot lifecycle
        self.is_searching: bool = False
        self.bot_active: bool = False
        self.connector_thread_started: bool = False
        self.status_callback = None
        self.lcu_connection = None

        # Gameflow: WebSocket is the single source of truth for current phase
        self.current_phase: str = "None"

        # Lobby spectator slot cooldown
        self.last_switch_attempt: float = 0.0

        # InProgress tracking for Reconnect detection
        self.was_in_progress: bool = False

    def reset_game_tracking(self):
        """Resets in-game tracking. Called on game start (InProgress)."""
        self.was_in_progress = False

    def update_gui_status(self, status_text: str):
        """Pushes a status update to the GUI and logs it."""
        if self.status_callback:
            try:
                self.status_callback(status_text)
            except Exception as e:
                logger.error(f"Error calling status callback: {e}")
        logger.info(f"STATUS: {status_text}")


# Singleton — shared state only
bot_state = BotState()
