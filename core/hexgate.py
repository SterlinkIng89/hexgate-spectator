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

class DummyEvent:
    def __init__(self, data):
        self.data = data

def update_gui_status(status_text):
    if status_callback:
        status_callback(status_text)
    logger.info(f"STATUS: {status_text}")

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
            # Party join with lobbyPassword (from Needlework schema)
            res_party = await connection.request("post", f"/lol-lobby/v2/party/{party_id}/join", json={"lobbyPassword": pwd, "team": "spectator"})
            if res_party.status in [200, 204]:
                logger.info(f"Success joining via partyId! Correct password: '{pwd}'")
                return True
            logger.warning(f"Failed party join with password '{pwd}'. Status: {res_party.status}")

        await asyncio.sleep(1) # Small pause between attempts
        
    return False

async def search_and_join_loop(connection):
    global is_searching, bot_active
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
                
                # We only want to search if we are in "None" (waiting) OR "Lobby" (to check for better remakes)
                if current_phase in ["None", "Lobby"]:
                    res = await connection.request("get", "/lol-lobby/v1/custom-games")
                    if res.status == 200:
                        games = await res.json()
                        target_name = BOT_CONFIG["lobby_name"]
                        target_pattern = re.compile(r'\b' + re.escape(target_name) + r'\b', re.IGNORECASE)
                        
                        # Get current lobby state if we are in one
                        current_party_id = None
                        current_count = 0
                        
                        if current_phase == "Lobby":
                            current_lobby_res = await connection.request("get", "/lol-lobby/v2/lobby")
                            if current_lobby_res.status == 200:
                                current_lobby_data = await current_lobby_res.json()
                                current_party_id = current_lobby_data.get("partyId")
                                current_count = len(current_lobby_data.get("members", []))
                                
                        best_game = None
                        best_count = current_count
                        
                        for g in games:
                            lobby_name = g.get("lobbyName", "")
                            if target_pattern.search(lobby_name):
                                # Skip our own lobby to avoid leaving and rejoining
                                if current_party_id and g.get("partyId") == current_party_id:
                                    continue
                                    
                                total_slots = g.get("filledPlayerSlots", 0) + g.get("filledSpectatorSlots", 0)
                                
                                # If we find a lobby with MORE players than our current one (or we are not in one)
                                if current_phase == "None" and best_game is None:
                                    best_game = g
                                    best_count = total_slots
                                elif total_slots > best_count:
                                    best_game = g
                                    best_count = total_slots
                                    
                        if current_phase == "Lobby" and current_party_id:
                            # Note: To compare the names we need to extract current_name
                            current_name = current_lobby_data.get("gameConfig", {}).get("customLobbyName", "") if current_lobby_data else ""
                            if best_game and best_game.get("lobbyName") != current_name and best_count > current_count:
                                logger.info(f"Lobby check: Current lobby has {current_count} players. Found better remake lobby '{best_game['lobbyName']}' with {best_count} players. Switching...")
                                update_gui_status("Switching to better lobby...")
                                await connection.request("post", "/lol-lobby/v2/lobby/quit")
                                await asyncio.sleep(2) # Wait for client to process quit
                            else:
                                if best_game:
                                    logger.info(f"Lobby check: Current lobby has {current_count} players. Best other lobby '{best_game['lobbyName']}' has {best_count} players. Staying here.")
                                else:
                                    logger.info(f"Lobby check: Current lobby has {current_count} players. No other matching lobbies found.")
                        elif best_game:
                            game_id = best_game["id"]
                            
                            # DEBUG: print the whole best_game object to see what ID field is available
                            logger.info(f"Lobby raw data: {best_game}")
                            logger.info(f"Lobby found: {target_name} (ID: {game_id}). Attempting to join...")
                                
                            success = await try_join_lobby_with_passwords(connection, game_id, best_game)
                            if success:
                                update_gui_status("Joined Lobby")
                                is_searching = False
                            else:
                                logger.error("Could not enter the lobby with any of the passwords.")
                                await asyncio.sleep(5)
                        else:
                            if current_phase == "None":
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

    local_member = next((m for m in lobby_data.get("members", []) if m.get("isLocalMember")), None)
    if local_member:
        team_id = local_member.get("teamId")
        if team_id in [TEAM_ORDER, TEAM_CHAOS]:
            current_time = time.time()
            if current_time - last_switch_attempt < 2: return
            
            update_gui_status("Moving to Spectator...")
            last_switch_attempt = current_time
            res = await connection.request("post", "/lol-lobby/v1/lobby/custom/switch-teams")
            if res.status in [200, 204]:
                logger.info("Move to Spectator Successful.")
                update_gui_status("In Lobby (Spectator)")

@connector.ws.register("/lol-gameflow/v1/gameflow-phase", event_types=("UPDATE",))
async def gameflow_handler(connection, event):
    global is_searching, bot_active
    if not bot_active: return

    phase = event.data
    
    if phase != "None":
        phase_name = GAMEFLOW_PHASES.get(phase, phase)
        update_gui_status(phase_name)

    if phase in ["ChampSelect", "InProgress"]:
        is_searching = False
        
    if phase == "InProgress":
        from core.game_automation import trigger_camera_automation
        trigger_camera_automation(delay=BOT_CONFIG["camera_delay"])

    if phase in ["EndOfGame", "WaitingForStats"]:
        logger.info("Game over (or Remake/Dodge). Starting cleanup...")
        
        # Forcefully close the game client if it's stuck on the Victory/Defeat screen
        import subprocess
        try:
            subprocess.run(["taskkill", "/F", "/IM", "League of Legends.exe"], capture_output=True)
            logger.info("Closed the game client process.")
        except Exception as e:
            logger.error(f"Failed to close game client: {e}")
            
        await asyncio.sleep(5)
        await connection.request("post", "/lol-end-of-game/v1/state/dismiss-stats")
        await connection.request("post", "/lol-lobby/v2/lobby/quit")
        is_searching = True
        
        if BOT_CONFIG["invite_only"]:
            update_gui_status("Waiting for invitation...")
        else:
            update_gui_status(f"Searching '{BOT_CONFIG['lobby_name']}'...")

    elif phase == "None":
        is_searching = True
        if BOT_CONFIG["invite_only"]:
            update_gui_status("Waiting for invitation...")
        else:
            update_gui_status(f"Searching '{BOT_CONFIG['lobby_name']}'...")


# --- Control API for GUI ---
def start_bot(callback, config_data):
    global bot_active, is_searching, status_callback, connector_thread_started, BOT_CONFIG
    
    BOT_CONFIG.update(config_data)
    
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
    update_gui_status("Bot Stopped.")
