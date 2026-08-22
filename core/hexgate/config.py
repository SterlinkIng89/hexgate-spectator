"""
Configuration and constants for Hexgate Spectator.
"""

TEAM_CHAOS = 200
TEAM_ORDER = 100
GAME_FREEZE_TIMEOUT = 300  # 5 minutes fallback freeze timeout

# Dynamic configuration modified at runtime by the GUI
BOT_CONFIG = {
    "lobby_name": "SCRIM_TEST",
    "passwords": [],
    "camera_delay": 3.0,
    "invite_only": False,
    "ignored_words": []
}

GAMEFLOW_PHASES = {
    "None": "Waiting...",
    "Lobby": "In Lobby",
    "Matchmaking": "Finding Match",
    "ReadyCheck": "Accepting Match",
    "ChampSelect": "Champion Select",
    "GameStart": "Game Starting",
    "InProgress": "Game In Progress",
    "WaitingForStats": "Waiting for Stats",
    "EndOfGame": "End of Game",
    "Reconnect": "Reconnecting",
}
