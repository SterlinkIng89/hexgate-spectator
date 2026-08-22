"""
Lobby search, spectator slot management, and join actions.

All functions here are atomic and stateless — they do one thing and return.
The main bot loop in engine.py orchestrates when to call each function.
"""

import asyncio
import logging
from typing import Optional, Dict, Any

from core.hexgate.config import BOT_CONFIG
from core.hexgate.state import bot_state
from core.hexgate.lobby.scanner import filter_and_rank_lobbies

logger = logging.getLogger("Hexgate")

# Dedup state is local to this module — doesn't belong in global BotState
_last_lobby_check_msg: str = ""


async def try_join_lobby_with_passwords(
    connection,
    game_id: int,
    best_game: Optional[Dict[str, Any]] = None
) -> bool:
    """
    Tries each configured password in sequence to join a custom lobby.
    Returns True on first success, False if all attempts fail.
    """
    passwords = BOT_CONFIG.get("passwords", [])
    party_id = best_game.get("partyId") if best_game else None

    if not passwords:
        logger.info("Attempting to join without password...")
        res = await connection.request("post", f"/lol-lobby/v1/custom-games/{game_id}/join")
        if res.status in [200, 204]:
            return True
        if game_id == 0 and party_id:
            logger.info(f"ID is 0. Trying to join via partyId: {party_id} without password")
            res_party = await connection.request("post", f"/lol-lobby/v2/party/{party_id}/join")
            if res_party.status in [200, 204]:
                return True
        logger.warning(f"Error joining without password. Status: {res.status}")
        return False

    for pwd in passwords:
        logger.info(f"Attempting to join with password: '{pwd}'...")
        if game_id == 0 and party_id:
            res_party = await connection.request(
                "post",
                f"/lol-lobby/v2/party/{party_id}/join",
                json={"lobbyPassword": pwd, "team": "SPECTATOR"}
            )
            if res_party.status in [200, 204]:
                logger.info(f"Success joining via partyId! Correct password: '{pwd}'")
                return True
            logger.warning(f"Failed party join with password '{pwd}'. Status: {res_party.status}")
        await asyncio.sleep(1)

    return False


async def ensure_spectator_slot(connection, lobby_data: dict) -> None:
    """
    Periodic check: if the bot ended up in a player slot, move it to spectators.
    Separated from the WebSocket reactive handler because the search loop
    also needs to call this every tick while in Lobby phase.
    """
    local_member = lobby_data.get("localMember") if lobby_data else None
    if not local_member or local_member.get("isSpectator"):
        return
    logger.info("Lobby check: Bot is currently in a player slot. Attempting to move to spectators...")
    res = await connection.request("post", "/lol-lobby/v2/lobby/team/SPECTATOR")
    if res.status in [200, 204]:
        logger.info("Move to Spectator Successful.")
        bot_state.update_gui_status("In Lobby (Spectator)")
    else:
        logger.warning(f"Failed to move to Spectator. Status: {res.status}. Will retry next check.")


async def search_and_join_lobbies(connection) -> None:
    """
    One tick of the lobby search: refreshes the custom game list, filters,
    and either joins a new lobby or evaluates whether to switch to a better remake.

    Reads current_phase from bot_state (set by the WebSocket handler).
    Does NOT contain a loop — engine.py drives the cadence.
    """
    global _last_lobby_check_msg

    current_phase = bot_state.current_phase

    # Only act when idle or already in a lobby evaluating remakes
    if current_phase not in ["None", "Lobby"]:
        return

    await connection.request("post", "/lol-lobby/v1/custom-games/refresh")
    await asyncio.sleep(0.5)

    res = await connection.request("get", "/lol-lobby/v1/custom-games")
    if res.status != 200:
        return

    games = await res.json()
    target_names = [n.strip() for n in BOT_CONFIG["lobby_name"].split(",") if n.strip()]
    ignored_words = BOT_CONFIG.get("ignored_words", [])

    current_party_id = None
    current_count = 0
    current_lobby_data = None

    if current_phase == "Lobby":
        lobby_res = await connection.request("get", "/lol-lobby/v2/lobby")
        if lobby_res.status == 200:
            current_lobby_data = await lobby_res.json()
            current_party_id = current_lobby_data.get("partyId")
            current_count = len(current_lobby_data.get("members", []))

    valid_games = filter_and_rank_lobbies(
        games=games,
        target_names=target_names,
        ignored_words=ignored_words,
        current_party_id=current_party_id
    )

    if current_phase == "Lobby" and current_party_id:
        await ensure_spectator_slot(connection, current_lobby_data)
        await _handle_lobby_phase(connection, current_lobby_data, valid_games, current_count)
    elif current_phase == "None":
        await _handle_none_phase(connection, valid_games)


async def _handle_lobby_phase(connection, current_lobby_data, valid_games, current_count) -> None:
    """Evaluates whether to switch to a better remake lobby or stay."""
    global _last_lobby_check_msg

    if valid_games:
        best_game = valid_games[0]["game"]
        best_count = valid_games[0]["score"]
        current_name = current_lobby_data.get("gameConfig", {}).get("customLobbyName", "") if current_lobby_data else ""

        if best_game.get("lobbyName") != current_name and best_count > current_count:
            msg = (
                f"Lobby check: Current lobby has {current_count} players. "
                f"Found better remake lobby '{best_game['lobbyName']}' with {best_count} players. Switching..."
            )
            logger.info(msg)
            _last_lobby_check_msg = msg
            bot_state.update_gui_status("Switching to better lobby...")
            await connection.request("delete", "/lol-lobby/v2/lobby")
            await asyncio.sleep(2)
        else:
            msg = (
                f"Lobby check: Current lobby has {current_count} players. "
                f"Best other lobby '{best_game['lobbyName']}' has {best_count} players. Staying here."
            )
            if msg != _last_lobby_check_msg:
                logger.info(msg)
                _last_lobby_check_msg = msg
    else:
        msg = f"Lobby check: Current lobby has {current_count} players. No other matching lobbies found."
        if msg != _last_lobby_check_msg:
            logger.info(msg)
            _last_lobby_check_msg = msg


async def _handle_none_phase(connection, valid_games) -> None:
    """Tries to join the best available lobby when the bot is idle."""
    if not valid_games:
        logger.debug(f"Searching for lobby '{BOT_CONFIG['lobby_name']}'...")
        return

    for vg in valid_games:
        best_game = vg["game"]
        game_id = best_game.get("id", 0)
        logger.info(f"Lobby found: {best_game.get('lobbyName')} (ID: {game_id}). Attempting to join...")

        if await try_join_lobby_with_passwords(connection, game_id, best_game):
            bot_state.update_gui_status("Joined Lobby")
            bot_state.is_searching = False
            return
        else:
            logger.warning(f"Could not enter lobby '{best_game.get('lobbyName')}' with any of the passwords. Trying next...")

    logger.error("Could not enter ANY of the matching lobbies.")
