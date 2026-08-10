import asyncio
import logging
import time
import threading

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

async def try_join_lobby_with_passwords(connection, game_id):
    """Attempts to join a lobby using the configured list of passwords."""
    passwords_to_try = BOT_CONFIG["passwords"]
    
    if not passwords_to_try:
        # Attempt without password
        logger.info("Attempting to join without password...")
        res = await connection.request("post", f"/lol-lobby/v1/custom-games/{game_id}/join")
        if res.status in [200, 204]:
            return True
        logger.warning(f"Error joining without password. Status: {res.status}")
        return False
        
    for pwd in passwords_to_try:
        logger.info(f"Attempting to join with password: '{pwd}'...")
        payload = {"password": pwd}
        res = await connection.request("post", f"/lol-lobby/v1/custom-games/{game_id}/join", data=payload)
        
        if res.status in [200, 204]:
            logger.info(f"Success! Correct password: '{pwd}'")
            return True
            
        logger.warning(f"Failed with password '{pwd}'. Status: {res.status}")
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
            if bot_active and is_searching and not BOT_CONFIG["invite_only"]:
                logger.debug(f"Searching for lobby '{BOT_CONFIG['lobby_name']}'...")
                res = await connection.request("get", "/lol-lobby/v1/custom-games")
                if res.status == 200:
                    games = await res.json()
                    target_name = BOT_CONFIG["lobby_name"]
                    target_game = next((g for g in games if g.get("lobbyName") == target_name), None)

                    if target_game:
                        game_id = target_game["id"]
                        logger.info(f"Lobby found: {target_name} (ID: {game_id}). Attempting to join...")
                        
                        success = await try_join_lobby_with_passwords(connection, game_id)
                        if success:
                            update_gui_status("Joined Lobby")
                            is_searching = False
                        else:
                            logger.error("Could not enter the lobby with any of the passwords.")
                            # Wait a bit longer before retrying if all passwords failed
                            await asyncio.sleep(5)
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

    if is_searching:
        is_searching = False

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

    if phase == "InProgress":
        is_searching = False
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
