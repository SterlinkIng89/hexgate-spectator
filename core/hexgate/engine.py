"""
Hexgate Bot Engine — owns the bot lifecycle and the main orchestration loop.

Responsibilities:
- Apply lcu_driver patch before connector initialization
- Register all WebSocket event handlers
- start_bot / stop_bot control API for the GUI
- sync_state: reconcile client state on connect / reactivation
- main_bot_loop: single orchestration loop that drives lobby search and watchdog
"""

import asyncio
import threading
import logging

from core.obs_controller import obs_controller
from core.hexgate.config import BOT_CONFIG
from core.hexgate.state import bot_state
from core.hexgate.client.lcu_connector import connector, init_connector_events
from core.hexgate.gameflow.cleanup import cleanup_game_process
from core.hexgate.gameflow.watchdog import check_game_freeze
from core.hexgate.gameflow.handlers import register_gameflow_events, process_phase_change, process_lobby_update
from core.hexgate.lobby.actions import search_and_join_lobbies

logger = logging.getLogger("Hexgate")

# Register all WebSocket listeners once at import time
register_gameflow_events(connector)


# ---------------------------------------------------------------------------
# State sync — called on connect and on bot reactivation
# ---------------------------------------------------------------------------

async def sync_state(connection):
    """Reads the current LCU state and brings the bot up to date."""
    logger.info("Syncing current state...")
    try:
        phase_res = await connection.request("get", "/lol-gameflow/v1/gameflow-phase")
        if phase_res.status != 200:
            return
        current_phase = await phase_res.json()
        logger.info(f"Initial phase detected: {current_phase}")

        if bot_state.bot_active:
            await process_phase_change(connection, current_phase)

        if current_phase in ["Lobby", "ChampSelect"] and bot_state.bot_active:
            lobby_res = await connection.request("get", "/lol-lobby/v2/lobby")
            if lobby_res.status == 200:
                lobby_data = await lobby_res.json()
                await process_lobby_update(connection, lobby_data)
    except Exception as e:
        logger.error(f"Error syncing client state: {e}")


# ---------------------------------------------------------------------------
# Main orchestration loop — owned here, not in lobby or gameflow modules
# ---------------------------------------------------------------------------

async def main_bot_loop(connection):
    """
    Drives the bot's periodic work.
    Phase state is maintained by the WebSocket handler (single source of truth).
    This loop only reads bot_state.current_phase — no HTTP polling of gameflow.
    """
    was_active = bot_state.bot_active

    while True:
        try:
            if bot_state.bot_active and not was_active:
                logger.info("Bot activated, syncing state...")
                await sync_state(connection)
            was_active = bot_state.bot_active

            if bot_state.bot_active:
                phase = bot_state.current_phase

                if phase == "InProgress":
                    await check_game_freeze(connection, cleanup_game_process)
                elif phase in ["None", "Lobby"] and not BOT_CONFIG["invite_only"]:
                    await search_and_join_lobbies(connection)

            await asyncio.sleep(5)
        except Exception as e:
            logger.error(f"Error in main bot loop: {e}")
            await asyncio.sleep(5)


# Hook up connection lifecycle events
init_connector_events(
    sync_state_fn=sync_state,
    search_loop_fn=main_bot_loop
)


# ---------------------------------------------------------------------------
# Public control API — called by gui/app.py
# ---------------------------------------------------------------------------

def start_bot(callback, config_data: dict):
    """Configures and starts the bot with the provided GUI callback and settings."""
    BOT_CONFIG.update(config_data)

    obs_controller.configure(config_data)
    if obs_controller.enabled:
        threading.Thread(target=obs_controller.connect, daemon=True).start()
        if obs_controller.schedule_enabled:
            obs_controller.start_scheduler()

    bot_state.bot_active = True
    bot_state.is_searching = True
    bot_state.status_callback = callback

    if BOT_CONFIG["invite_only"]:
        bot_state.update_gui_status("Starting. Waiting for invitations...")
    else:
        bot_state.update_gui_status(f"Starting. Searching '{BOT_CONFIG['lobby_name']}'...")

    if not bot_state.connector_thread_started:
        bot_state.connector_thread_started = True
        threading.Thread(target=connector.start, daemon=True).start()


def stop_bot():
    """Gracefully stops the bot."""
    bot_state.bot_active = False
    bot_state.is_searching = False

    obs_controller.stop_scheduler()
    obs_controller.on_game_end()
    obs_controller.disconnect()

    bot_state.update_gui_status("Bot Stopped.")
