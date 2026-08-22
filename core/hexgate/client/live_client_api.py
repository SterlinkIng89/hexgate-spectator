"""
Asynchronous client for League of Legends Live Client Data API (port 2999).
"""

import asyncio
from typing import Optional, List, Dict, Any
import requests
import urllib3

# Suppress self-signed certificate warnings for local game server
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

LIVE_CLIENT_BASE_URL = "https://127.0.0.1:2999/liveclientdata"


async def get_current_game_time() -> Optional[float]:
    """
    Fetches the current game time in seconds from Live Client Data API.
    Returns None if the game process is unreachable or loading screen is active.
    """
    loop = asyncio.get_event_loop()

    def _fetch():
        try:
            res = requests.get(
                f"{LIVE_CLIENT_BASE_URL}/gamestats",
                verify=False,
                timeout=0.5
            )
            if res.status_code == 200:
                return res.json().get("gameTime", None)
        except Exception:
            pass
        return None

    return await loop.run_in_executor(None, _fetch)


async def get_current_all_players() -> Optional[List[Dict[str, Any]]]:
    """
    Fetches the list of all connected players in the live game.
    Returns None if unreachable.
    """
    loop = asyncio.get_event_loop()

    def _fetch():
        try:
            res = requests.get(
                f"{LIVE_CLIENT_BASE_URL}/allplayers",
                verify=False,
                timeout=2.0
            )
            if res.status_code == 200:
                return res.json()
        except Exception:
            pass
        return None

    return await loop.run_in_executor(None, _fetch)
