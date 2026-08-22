"""
Lobby scanning, pattern matching, and lobby ranking logic.
"""

import re
from typing import List, Dict, Any, Pattern


def build_lobby_pattern(name: str) -> Pattern:
    """
    Build a regex that tolerates inconsistent spacing in lobby names.
    e.g. 'EST' matches 'EST', 'E ST', 'ES T', 'E S T', etc.
    """
    chars = list(name.strip())
    # Escape each char individually; turn spaces into \s+ (must have at least one space)
    parts = [re.escape(c) if c != ' ' else r'\s+' for c in chars]
    # Allow optional whitespace between every character
    flexible = r'\s*'.join(parts)
    # Use lookarounds instead of \b to handle punctuation correctly
    return re.compile(r'(?<!\w)' + flexible + r'(?!\w)', re.IGNORECASE)


def filter_and_rank_lobbies(
    games: List[Dict[str, Any]],
    target_names: List[str],
    ignored_words: List[str],
    current_party_id: str = None
) -> List[Dict[str, Any]]:
    """
    Filters raw custom games matching target names and not containing ignored words.
    Returns ranked list sorted by total player slots descending.
    """
    target_patterns = [build_lobby_pattern(tn) for tn in target_names if tn.strip()]
    valid_games = []

    for g in games:
        lobby_name = g.get("lobbyName", "")

        # Filter out lobbies containing ignored words
        should_ignore = False
        for word in ignored_words:
            if word.strip() and word.strip().lower() in lobby_name.lower():
                should_ignore = True
                break

        if should_ignore:
            continue

        if any(p.search(lobby_name) for p in target_patterns):
            # Skip our own lobby to avoid leaving and rejoining
            if current_party_id and g.get("partyId") == current_party_id:
                continue

            total_slots = g.get("filledPlayerSlots", 0) + g.get("filledSpectatorSlots", 0)
            valid_games.append({"game": g, "score": total_slots})

    # Sort descending by player count
    valid_games.sort(key=lambda x: x["score"], reverse=True)
    return valid_games
