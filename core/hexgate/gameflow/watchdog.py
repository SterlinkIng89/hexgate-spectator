"""
Watchdog: detects frozen games when all players disconnect mid-scrim.

State is module-local — it belongs here, not in global BotState.
"""

import time
import logging
from core.hexgate.config import GAME_FREEZE_TIMEOUT

logger = logging.getLogger("Hexgate")

# --- Module-local freeze tracking ---
_game_time_last_value: float = 0.0
_game_time_last_changed_at: float = 0.0
_last_game_time_log_at: float = 0.0
_frozen_warnings_issued: set = set()
_players_logged: bool = False


def reset():
    """Reset all freeze tracking. Called when a new InProgress game begins."""
    global _game_time_last_value, _game_time_last_changed_at
    global _last_game_time_log_at, _frozen_warnings_issued, _players_logged
    _game_time_last_value = 0.0
    _game_time_last_changed_at = 0.0
    _last_game_time_log_at = 0.0
    _frozen_warnings_issued = set()
    _players_logged = False


async def check_game_freeze(connection, cleanup_fn):
    """
    Checks if the live game clock has stalled.
    Must be called periodically while current_phase == 'InProgress'.
    """
    global _game_time_last_value, _game_time_last_changed_at
    global _last_game_time_log_at, _frozen_warnings_issued, _players_logged

    from core.hexgate.client.live_client_api import get_current_game_time, get_current_all_players

    game_time = await get_current_game_time()
    now = time.time()

    if game_time is None:
        # API unreachable — may mean the process crashed
        if _game_time_last_changed_at > 0 and (now - _game_time_last_changed_at) >= GAME_FREEZE_TIMEOUT:
            logger.warning("Game API unreachable for too long. Forcing cleanup...")
            await cleanup_fn(connection, "Game API unreachable")
        return

    # Log player list once at game start
    if not _players_logged and game_time > 1.0:
        players = await get_current_all_players()
        if players:
            names = [
                f"{p.get('summonerName', 'Unknown')} ({p.get('championName', 'Unknown')})"
                for p in players
            ]
            logger.info(f"[SPECTATE] Connected players ({len(names)}): {', '.join(names)}")
        _players_logged = True

    if game_time != _game_time_last_value:
        # Clock advancing normally
        _game_time_last_value = game_time
        _game_time_last_changed_at = now
        _frozen_warnings_issued = set()
        if now - _last_game_time_log_at >= 30:
            logger.info(f"[SPECTATE] Game running. Current gameTime: {game_time:.1f}s")
            _last_game_time_log_at = now
        return

    # Clock has stalled
    frozen_for = now - _game_time_last_changed_at
    for threshold in (15, 45, 90, GAME_FREEZE_TIMEOUT):
        if frozen_for >= threshold and threshold not in _frozen_warnings_issued:
            if threshold == GAME_FREEZE_TIMEOUT:
                logger.warning(
                    f"[SPECTATE] Game time frozen for {frozen_for:.0f}s. "
                    "Game is likely paused. Waiting for unpause or manual exit..."
                )
            else:
                logger.warning(f"[WARN] [SPECTATE] Game time stalled at {game_time:.1f}s for {threshold}s...")
            _frozen_warnings_issued.add(threshold)
