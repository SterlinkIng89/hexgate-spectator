"""
Process termination, stats dismissal, and game cleanup routines.
"""

import asyncio
import subprocess
from core.obs_controller import obs_controller
from core.hexgate.config import BOT_CONFIG
from core.hexgate.state import bot_state, logger


async def cleanup_game_process(connection, reason: str):
    """
    Terminates the LoL game client process and resets the bot state back to searching.

    Triggered by:
    - EndOfGame / WaitingForStats (normal game conclusion)
    - Reconnect phase after InProgress (game abandoned / all players disconnected)
    - TERMINATED_IN_ERROR GSM event (server-side abort)
    - Frozen game time watchdog timeout
    """
    logger.info(f"[CLEANUP] Triggered by: {reason}. Killing game process...")
    bot_state.update_gui_status(f"{reason} — cleaning up...")

    obs_controller.on_game_end()
    bot_state.reset_game_tracking()

    try:
        res = subprocess.run(
            ["taskkill", "/F", "/IM", "League of Legends.exe"],
            capture_output=True,
            text=True
        )
        logger.info(
            f"[PROCESS] taskkill League of Legends.exe -> Exit {res.returncode}. "
            f"stdout: {res.stdout.strip()} stderr: {res.stderr.strip()}"
        )
    except Exception as e:
        logger.error(f"[PROCESS] Failed to close game client: {e}")

    await asyncio.sleep(3)

    if connection:
        try:
            await connection.request("post", "/lol-end-of-game/v1/state/dismiss-stats")
        except Exception as e:
            logger.debug(f"Dismiss stats error: {e}")

        try:
            await connection.request("post", "/lol-lobby/v2/lobby/quit")
        except Exception as e:
            logger.debug(f"Lobby quit error: {e}")

    bot_state.is_searching = True

    if BOT_CONFIG["invite_only"]:
        bot_state.update_gui_status("Waiting for invitation...")
    else:
        bot_state.update_gui_status(f"Searching '{BOT_CONFIG['lobby_name']}'...")
