import asyncio
import logging
import time
import threading
import re

# --- Workaround for lcu_driver in MainThread ---
# lcu_driver requires an event loop to exist when instantiating Connector.
try:
    asyncio.get_event_loop()
except RuntimeError:
    asyncio.set_event_loop(asyncio.new_event_loop())

from lcu_driver import Connector

# --- Base Configuration ---
TEAM_CHAOS = 200
TEAM_ORDER = 100

logger = logging.getLogger("Hexgate")
connector = Connector()

# --- Dynamic Configuration ---
BOT_CONFIG = {
    "lobby_name": "SCRIM_TEST",
    "passwords": [],
    "camera_delay": 3.0,
    "invite_only": False
}

# Global State Variables
is_searching = False
bot_active = False
last_switch_attempt = 0
status_callback = None
connector_thread_started = False
lcu_connection = None

# Frozen game detection
_game_time_last_value = 0.0
_game_time_last_changed_at = 0.0
GAME_FREEZE_TIMEOUT = 300  # 5 minutes: fallback only, primary detection is via Reconnect phase
_was_in_progress = False  # Tracks if we were spectating a live game

# Verbose Logging state variables
_previous_phase = "None"
_last_game_time_log_at = 0.0
_frozen_warnings_issued = set()
_players_logged_for_current_game = False

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

def build_lobby_pattern(name):
    """Build a regex that tolerates inconsistent spacing in lobby names.
    e.g. 'EST' matches 'EST', 'E ST', 'ES T', 'E S T', etc."""
    chars = list(name.strip())
    # Escape each char individually; turn spaces into \s+ (must have at least one space)
    parts = [re.escape(c) if c != ' ' else r'\s+' for c in chars]
    # Allow optional whitespace between every character
    flexible = r'\s*'.join(parts)
    # Use lookarounds instead of \b to handle punctuation correctly
    return re.compile(r'(?<!\w)' + flexible + r'(?!\w)', re.IGNORECASE)

class DummyEvent:
    def __init__(self, data):
        self.data = data

def update_gui_status(status_text):
    if status_callback:
        status_callback(status_text)
    logger.info(f"STATUS: {status_text}")

async def get_current_game_time():
    """Fetches the current game time from the Live Client Data API (port 2999).
    Returns the game time in seconds, or None if the game process is unreachable."""
    import requests
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    loop = asyncio.get_event_loop()
    def _fetch():
        try:
            res = requests.get("https://127.0.0.1:2999/liveclientdata/gamestats", verify=False, timeout=2)
            if res.status_code == 200:
                return res.json().get("gameTime", None)
        except Exception:
            pass
        return None
    return await loop.run_in_executor(None, _fetch)

async def get_current_all_players():
    """Fetches the allplayers list from the Live Client Data API."""
    import requests
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    loop = asyncio.get_event_loop()
    def _fetch():
        try:
            res = requests.get("https://127.0.0.1:2999/liveclientdata/allplayers", verify=False, timeout=2)
            if res.status_code == 200:
                return res.json()
        except Exception:
            pass
        return None
    return await loop.run_in_executor(None, _fetch)

async def try_join_lobby_with_passwords(connection, game_id, best_game=None):
    """Attempts to join a lobby using the configured list of passwords."""
    passwords_to_try = BOT_CONFIG["passwords"]
    
    party_id = best_game.get("partyId") if best_game else None

    if not passwords_to_try:
        # Attempt without password
        logger.info(f"Attempting to join without password...")
        # First try normal join
        res = await connection.request("post", f"/lol-lobby/v1/custom-games/{game_id}/join")
        if res.status in [200, 204]: return True
        
        # If ID is 0, try joining by partyId just in case
        if game_id == 0 and party_id:
            logger.info(f"ID is 0. Trying to join via partyId: {party_id} without password")
            res_party = await connection.request("post", f"/lol-lobby/v2/party/{party_id}/join")
            if res_party.status in [200, 204]: return True
            
        logger.warning(f"Error joining without password. Status: {res.status}")
        return False
        
    for pwd in passwords_to_try:
        logger.info(f"Attempting to join with password: '{pwd}'...")
        
        if game_id == 0 and party_id:
            # Party join with lobbyPassword
            res_party = await connection.request("post", f"/lol-lobby/v2/party/{party_id}/join", json={"lobbyPassword": pwd, "team": "SPECTATOR"})
            if res_party.status in [200, 204]:
                logger.info(f"Success joining via partyId! Correct password: '{pwd}'")
                return True
            logger.warning(f"Failed party join with password '{pwd}'. Status: {res_party.status}")

        await asyncio.sleep(1) # Small pause between attempts
        
    return False

_last_lobby_check_msg = ""

async def search_and_join_loop(connection):
    global is_searching, bot_active, _last_lobby_check_msg
    was_active = bot_active
    while True:
        try:
            # Sync state if bot was just activated
            if bot_active and not was_active:
                logger.info("Bot activated, syncing state...")
                await sync_state(connection)
            was_active = bot_active

            # We only search if Invite Only mode is disabled
            if bot_active and not BOT_CONFIG["invite_only"]:
                # Determine our current gameflow phase
                phase_res = await connection.request("get", "/lol-gameflow/v1/gameflow-phase")
                current_phase = await phase_res.json() if phase_res.status == 200 else "None"
                
                # --- Frozen game detection ---
                # When InProgress, check if the game time has stopped advancing.
                # This happens when all players leave a custom game: the process
                # stays alive but the clock freezes indefinitely.
                if current_phase == "InProgress":
                    global _game_time_last_value, _game_time_last_changed_at
                    global _last_game_time_log_at, _frozen_warnings_issued, _players_logged_for_current_game
                    game_time = await get_current_game_time()
                    now = time.time()

                    if game_time is not None:
                        if not _players_logged_for_current_game and game_time > 1.0:
                            players = await get_current_all_players()
                            if players:
                                names = [f"{p.get('summonerName', 'Unknown')} ({p.get('championName', 'Unknown')})" for p in players]
                                logger.info(f"[SPECTATE] Connected players ({len(names)}): {', '.join(names)}")
                            _players_logged_for_current_game = True

                        if game_time != _game_time_last_value:
                            # Clock is still moving — update tracking variables
                            _game_time_last_value = game_time
                            _game_time_last_changed_at = now
                            _frozen_warnings_issued.clear()
                            
                            # Periodic logging every 30s
                            if now - _last_game_time_log_at >= 30:
                                logger.info(f"[SPECTATE] Game running. Current gameTime: {game_time:.1f}s")
                                _last_game_time_log_at = now
                        else:
                            # Clock has not moved since last check
                            frozen_for = now - _game_time_last_changed_at
                            
                            if frozen_for >= 15 and 15 not in _frozen_warnings_issued:
                                logger.warning(f"[WARN] [SPECTATE] Game time stalled at {game_time:.1f}s for 15s...")
                                _frozen_warnings_issued.add(15)
                            elif frozen_for >= 45 and 45 not in _frozen_warnings_issued:
                                logger.warning(f"[WARN] [SPECTATE] Game time stalled at {game_time:.1f}s for 45s...")
                                _frozen_warnings_issued.add(45)
                            elif frozen_for >= 90 and 90 not in _frozen_warnings_issued:
                                logger.warning(f"[WARN] [SPECTATE] Game time stalled at {game_time:.1f}s for 90s...")
                                _frozen_warnings_issued.add(90)

                            if _game_time_last_changed_at > 0 and frozen_for >= GAME_FREEZE_TIMEOUT:
                                logger.warning(f"[SPECTATE] Game time frozen for {frozen_for:.0f}s. Assuming all players left. Forcing cleanup...")
                                await _cleanup_game_process(connection, f"Game frozen for {frozen_for:.0f}s")
                    else:
                        # API unreachable — game process probably already died
                        if _game_time_last_changed_at > 0:
                            frozen_for = time.time() - _game_time_last_changed_at
                            if frozen_for >= GAME_FREEZE_TIMEOUT:
                                logger.warning("Game API unreachable for too long. Forcing cleanup...")
                                await _cleanup_game_process(connection, "Game API unreachable")

                # We only want to search if we are in "None" (waiting) OR "Lobby" (to check for better remakes)
                if current_phase in ["None", "Lobby"]:
                    # Force the LCU to refresh its cached custom-games list so we
                    # can detect newly-created lobbies without the user manually
                    # hitting refresh in the client UI.
                    await connection.request("post", "/lol-lobby/v1/custom-games/refresh")
                    await asyncio.sleep(0.5)  # Short wait for the client to populate the refreshed list
                    res = await connection.request("get", "/lol-lobby/v1/custom-games")
                    if res.status == 200:
                        games = await res.json()
                        target_names = [name.strip() for name in BOT_CONFIG["lobby_name"].split(",") if name.strip()]
                        target_patterns = [build_lobby_pattern(tn) for tn in target_names]
                        
                        # Get current lobby state if we are in one
                        current_party_id = None
                        current_count = 0
                        
                        if current_phase == "Lobby":
                            current_lobby_res = await connection.request("get", "/lol-lobby/v2/lobby")
                            if current_lobby_res.status == 200:
                                current_lobby_data = await current_lobby_res.json()
                                current_party_id = current_lobby_data.get("partyId")
                                current_count = len(current_lobby_data.get("members", []))
                                
                        valid_games = []
                        ignored_words = BOT_CONFIG.get("ignored_words", [])
                        
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
                                
                        if current_phase == "Lobby" and current_party_id:
                            # Periodic spectator check
                            local_member = current_lobby_data.get("localMember")
                            if local_member and not local_member.get("isSpectator"):
                                logger.info("Lobby check: Bot is currently in a player slot. Attempting to move to spectators...")
                                res = await connection.request("post", "/lol-lobby/v2/lobby/team/SPECTATOR")
                                if res.status in [200, 204]:
                                    logger.info("Move to Spectator Successful.")
                                    update_gui_status("In Lobby (Spectator)")
                                else:
                                    logger.warning(f"Failed to move to Spectator. Status: {res.status}. Will retry next check.")
                            
                            if valid_games:
                                valid_games.sort(key=lambda x: x["score"], reverse=True)
                                best_game = valid_games[0]["game"]
                                best_count = valid_games[0]["score"]
                                
                                # Note: To compare the names we need to extract current_name
                                current_name = current_lobby_data.get("gameConfig", {}).get("customLobbyName", "") if current_lobby_data else ""
                                if best_game.get("lobbyName") != current_name and best_count > current_count:
                                    msg = f"Lobby check: Current lobby has {current_count} players. Found better remake lobby '{best_game['lobbyName']}' with {best_count} players. Switching..."
                                    logger.info(msg)
                                    _last_lobby_check_msg = msg
                                    update_gui_status("Switching to better lobby...")
                                    await connection.request("delete", "/lol-lobby/v2/lobby")
                                    await asyncio.sleep(2) # Wait for client to process quit
                                else:
                                    msg = f"Lobby check: Current lobby has {current_count} players. Best other lobby '{best_game['lobbyName']}' has {best_count} players. Staying here."
                                    if msg != _last_lobby_check_msg:
                                        logger.info(msg)
                                        _last_lobby_check_msg = msg
                            else:
                                msg = f"Lobby check: Current lobby has {current_count} players. No other matching lobbies found."
                                if msg != _last_lobby_check_msg:
                                    logger.info(msg)
                                    _last_lobby_check_msg = msg
                                
                        elif current_phase == "None":
                            if valid_games:
                                # Sort by score (players) descending
                                valid_games.sort(key=lambda x: x["score"], reverse=True)
                                joined = False
                                
                                for vg in valid_games:
                                    best_game = vg["game"]
                                    game_id = best_game.get("id", 0)
                                    
                                    logger.info(f"Lobby found: {best_game.get('lobbyName')} (ID: {game_id}). Attempting to join...")
                                        
                                    success = await try_join_lobby_with_passwords(connection, game_id, best_game)
                                    if success:
                                        update_gui_status("Joined Lobby")
                                        is_searching = False
                                        joined = True
                                        break
                                    else:
                                        logger.warning(f"Could not enter lobby '{best_game.get('lobbyName')}' with any of the passwords. Trying next matching lobby if available...")
                                
                                if not joined:
                                    logger.error("Could not enter ANY of the matching lobbies.")
                                    await asyncio.sleep(5)
                            else:
                                logger.debug(f"Searching for lobby '{BOT_CONFIG['lobby_name']}'...")
                                
            await asyncio.sleep(5)
        except Exception as e:
            logger.error(f"Error in search loop: {e}")
            await asyncio.sleep(5)

async def sync_state(connection):
    logger.info("Syncing current state...")
    phase_res = await connection.request("get", "/lol-gameflow/v1/gameflow-phase")
    if phase_res.status == 200:
        current_phase = await phase_res.json()
        logger.info(f"Initial phase detected: {current_phase}")
        
        if current_phase != "None" and bot_active:
            await gameflow_handler(connection, DummyEvent(current_phase))
            
        if current_phase in ["Lobby", "ChampSelect"] and bot_active:
            lobby_res = await connection.request("get", "/lol-lobby/v2/lobby")
            if lobby_res.status == 200:
                lobby_data = await lobby_res.json()
                await handle_lobby_update(connection, DummyEvent(lobby_data))
        
        # If phase is None, ensure GUI reflects that we are searching/waiting
        if current_phase == "None" and bot_active:
            await gameflow_handler(connection, DummyEvent("None"))

@connector.ready
async def connect(connection):
    global lcu_connection
    lcu_connection = connection
    
    logger.info("Connected to League of Legends client.")
    update_gui_status("Connected to LCU")
    
    summoner = await connection.request("get", "/lol-summoner/v1/current-summoner")
    if summoner.status == 200:
        data = await summoner.json()
        logger.info(f"Welcome, {data['displayName']}")
        
    await sync_state(connection)
    asyncio.create_task(search_and_join_loop(connection))

@connector.close
async def disconnect(_):
    global lcu_connection
    lcu_connection = None
    logger.info("Connection with the client closed. Waiting for restart...")
    update_gui_status("Waiting for LCU client...")

@connector.ws.register("/lol-lobby/v2/received-invitations", event_types=("CREATE",))
async def auto_accept_invite(connection, event):
    global is_searching, bot_active
    if not bot_active: return
    for invitation in event.data:
        invitation_id = invitation["invitationId"]
        logger.info(f"Invitation received. Accepting...")
        await connection.request("post", f"/lol-lobby/v2/received-invitations/{invitation_id}/accept")
        is_searching = False
        update_gui_status("Invitation Accepted")

@connector.ws.register("/lol-lobby/v2/lobby", event_types=("CREATE", "UPDATE"))
async def handle_lobby_update(connection, event):
    global last_switch_attempt, is_searching, bot_active
    if not bot_active: return

    lobby_data = event.data
    if not lobby_data: return

    local_member = lobby_data.get("localMember")
    if local_member:
        # If we accidentally joined a player slot, force switch to Spectator
        if not local_member.get("isSpectator"):
            current_time = time.time()
            if current_time - last_switch_attempt < 2: return
            
            update_gui_status("Moving to Spectator...")
            last_switch_attempt = current_time
            res = await connection.request("post", "/lol-lobby/v2/lobby/team/SPECTATOR")
            if res.status in [200, 204]:
                logger.info("Move to Spectator Successful.")
                update_gui_status("In Lobby (Spectator)")
            else:
                logger.warning(f"Failed to move to Spectator. Status: {res.status}")

@connector.ws.register("/lol-gameflow/v1/gameflow-phase", event_types=("UPDATE",))
async def gameflow_handler(connection, event):
    global is_searching, bot_active, _previous_phase
    if not bot_active: return

    phase = event.data
    
    phase_changed = (phase != _previous_phase)
    if phase_changed:
        logger.info(f"[GAMEFLOW] Phase changed: {_previous_phase} -> {phase}")
        _previous_phase = phase

    if phase != "None":
        phase_name = GAMEFLOW_PHASES.get(phase, phase)
        update_gui_status(phase_name)

    if phase in ["ChampSelect", "InProgress"]:
        is_searching = False
        
    if phase == "InProgress" and phase_changed:
        global _game_time_last_value, _game_time_last_changed_at, _was_in_progress
        global _last_game_time_log_at, _frozen_warnings_issued, _players_logged_for_current_game
        # Mark that we are now spectating a live game
        _was_in_progress = True
        # Reset freeze tracking for this new game
        _game_time_last_value = 0.0
        _game_time_last_changed_at = 0.0
        _last_game_time_log_at = 0.0
        _frozen_warnings_issued.clear()
        _players_logged_for_current_game = False
        from core.game_automation import trigger_camera_automation
        trigger_camera_automation(delay=BOT_CONFIG["camera_delay"])
        from core.obs_controller import obs_controller
        obs_controller.on_game_start()

    if phase == "Reconnect" and phase_changed and _was_in_progress:
        # The LCU emits "Reconnect" when the game server closes the session.
        # In a custom game, this happens when all players leave (remake/abandonment).
        # A normal in-game pause keeps the phase at "InProgress", so this is a
        # reliable signal that the game ended unexpectedly.
        logger.info("Reconnect phase detected after InProgress. All players likely left. Cleaning up...")
        await _cleanup_game_process(connection, "Game abandoned (Reconnect)")
        return

    if phase in ["EndOfGame", "WaitingForStats"] and phase_changed:
        logger.info(f"[GAMEFLOW] Game over (or Remake/Dodge). Phase is {phase}. Starting cleanup...")
        await _cleanup_game_process(connection, f"Game ended ({phase})")

    elif phase == "None" and phase_changed:
        is_searching = True
        if BOT_CONFIG["invite_only"]:
            update_gui_status("Waiting for invitation...")
        else:
            update_gui_status(f"Searching '{BOT_CONFIG['lobby_name']}'...")


async def _cleanup_game_process(connection, reason: str):
    """Kill the LoL game process and reset the bot back to searching state.
    
    This is the shared cleanup path triggered by:
    - EndOfGame / WaitingForStats (normal game end)
    - Reconnect phase after InProgress (all players left mid-game)
    - TERMINATED_IN_ERROR GSM event (server-side game termination, e.g. AFK chaos)
    - Frozen game time fallback (5-minute timeout)
    """
    global is_searching, _was_in_progress
    global _game_time_last_value, _game_time_last_changed_at
    global _last_game_time_log_at, _frozen_warnings_issued, _players_logged_for_current_game

    logger.info(f"[CLEANUP] Triggered by: {reason}. Killing game process...")
    update_gui_status(f"{reason} — cleaning up...")

    from core.obs_controller import obs_controller
    obs_controller.on_game_end()

    _was_in_progress = False
    _game_time_last_value = 0.0
    _game_time_last_changed_at = 0.0
    _last_game_time_log_at = 0.0
    _frozen_warnings_issued.clear()
    _players_logged_for_current_game = False

    import subprocess
    try:
        res = subprocess.run(["taskkill", "/F", "/IM", "League of Legends.exe"], capture_output=True, text=True)
        logger.info(f"[PROCESS] taskkill League of Legends.exe -> Exit {res.returncode}. stdout: {res.stdout.strip()} stderr: {res.stderr.strip()}")
    except Exception as e:
        logger.error(f"[PROCESS] Failed to close game client: {e}")

    await asyncio.sleep(3)
    await connection.request("post", "/lol-end-of-game/v1/state/dismiss-stats")
    await connection.request("post", "/lol-lobby/v2/lobby/quit")
    is_searching = True

    if BOT_CONFIG["invite_only"]:
        update_gui_status("Waiting for invitation...")
    else:
        update_gui_status(f"Searching '{BOT_CONFIG['lobby_name']}'...")


@connector.ws.register("/riot-messaging-service/v1/message/lol-gsm-server/v1/gsm/game-update/TERMINATED_IN_ERROR", event_types=("CREATE", "UPDATE"))
async def handle_gsm_terminated_in_error(connection, event):
    """Handles the GSM TERMINATED_IN_ERROR event.
    
    This event fires when the game server terminates the session abnormally,
    for example when players go AFK and the game cannot continue. The LoL
    process may stay alive even though the session is dead, so we must kill
    it explicitly here — otherwise the bot stays stuck on 'InProgress' and
    never returns to searching.
    """
    global bot_active, _was_in_progress
    if not bot_active:
        return

    data = event.data or {}
    # The payload is a JSON string nested inside the outer data dict
    import json
    payload_raw = data.get("payload", "{}")
    try:
        payload = json.loads(payload_raw) if isinstance(payload_raw, str) else payload_raw
    except Exception:
        payload = {}

    game_id = payload.get("id", "?")
    game_state = payload.get("gameState", "TERMINATED_IN_ERROR")
    logger.info(f"[GSM] Received {game_state} for game {game_id}. Forcing game process cleanup.")

    await _cleanup_game_process(connection, f"GSM {game_state} (game {game_id})")


# --- Control API for GUI ---
def start_bot(callback, config_data):
    global bot_active, is_searching, status_callback, connector_thread_started, BOT_CONFIG
    
    BOT_CONFIG.update(config_data)
    
    from core.obs_controller import obs_controller
    obs_controller.configure(config_data)
    if obs_controller.enabled:
        threading.Thread(target=obs_controller.connect, daemon=True).start()
        if obs_controller.schedule_enabled:
            obs_controller.start_scheduler()

    bot_active = True
    is_searching = True
    status_callback = callback
    
    if BOT_CONFIG["invite_only"]:
        update_gui_status("Starting. Waiting for invitations...")
    else:
        update_gui_status(f"Starting. Searching '{BOT_CONFIG['lobby_name']}'...")
    
    if not connector_thread_started:
        connector_thread_started = True
        threading.Thread(target=connector.start, daemon=True).start()

def stop_bot():
    global bot_active, is_searching
    bot_active = False
    is_searching = False
    
    from core.obs_controller import obs_controller
    obs_controller.stop_scheduler()
    obs_controller.on_game_end()
    obs_controller.disconnect()
    
    update_gui_status("Bot Stopped.")
