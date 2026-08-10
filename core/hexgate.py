import asyncio
import logging
import time
import threading

# --- Workaround para lcu_driver en MainThread ---
try:
    asyncio.get_event_loop()
except RuntimeError:
    asyncio.set_event_loop(asyncio.new_event_loop())

from lcu_driver import Connector

# --- Configuración Base ---
TEAM_CHAOS = 200
TEAM_ORDER = 100

logger = logging.getLogger("Hexgate")
connector = Connector()

# --- Configuración Dinámica ---
BOT_CONFIG = {
    "lobby_name": "SCRIM_TEST",
    "passwords": [],
    "camera_delay": 3.0,
    "invite_only": False
}

# Variables Globales de Estado
is_searching = False
bot_active = False
last_switch_attempt = 0
status_callback = None
connector_thread_started = False

GAMEFLOW_PHASES = {
    "None": "Esperando...",
    "Lobby": "En Lobby",
    "Matchmaking": "Buscando partida",
    "ReadyCheck": "Aceptando partida",
    "ChampSelect": "Selección de Campeones",
    "GameStart": "Juego Iniciando",
    "InProgress": "Partida en Curso",
    "WaitingForStats": "Esperando Estadísticas",
    "EndOfGame": "Fin de Partida",
    "Reconnect": "Reconectando",
}

def update_gui_status(status_text):
    if status_callback:
        status_callback(status_text)
    logger.info(f"ESTADO: {status_text}")

async def try_join_lobby_with_passwords(connection, game_id):
    """Intenta unirse a un lobby con la lista de contraseñas configuradas."""
    passwords_to_try = BOT_CONFIG["passwords"]
    
    if not passwords_to_try:
        # Intento sin contraseña
        logger.info("Intentando unirse sin contraseña...")
        res = await connection.request("post", f"/lol-lobby/v1/custom-games/{game_id}/join")
        if res.status in [200, 204]:
            return True
        logger.warning(f"Error al unirse sin contraseña. Status: {res.status}")
        return False
        
    for pwd in passwords_to_try:
        logger.info(f"Intentando unirse con contraseña: '{pwd}'...")
        payload = {"password": pwd}
        res = await connection.request("post", f"/lol-lobby/v1/custom-games/{game_id}/join", data=payload)
        
        if res.status in [200, 204]:
            logger.info(f"¡Éxito! Contraseña correcta: '{pwd}'")
            return True
            
        logger.warning(f"Fallo con contraseña '{pwd}'. Status: {res.status}")
        await asyncio.sleep(1) # Pequeña pausa entre intentos
        
    return False

async def search_and_join_loop(connection):
    global is_searching, bot_active
    while True:
        try:
            # Solo buscamos si el modo Invite Only está apagado
            if bot_active and is_searching and not BOT_CONFIG["invite_only"]:
                res = await connection.request("get", "/lol-lobby/v1/custom-games")
                if res.status == 200:
                    games = await res.json()
                    target_name = BOT_CONFIG["lobby_name"]
                    target_game = next((g for g in games if g.get("lobbyName") == target_name), None)

                    if target_game:
                        game_id = target_game["id"]
                        logger.info(f"Lobby encontrado: {target_name} (ID: {game_id}). Intentando unirnos...")
                        
                        success = await try_join_lobby_with_passwords(connection, game_id)
                        if success:
                            update_gui_status("Unido al Lobby")
                            is_searching = False
                        else:
                            logger.error("No se pudo entrar al lobby con ninguna de las contraseñas.")
                            # Esperar un poco más antes de reintentar si fallaron todas las pass
                            await asyncio.sleep(5)
            await asyncio.sleep(5)
        except Exception as e:
            logger.error(f"Error en el loop de búsqueda: {e}")
            await asyncio.sleep(5)

@connector.ready
async def connect(connection):
    logger.info("Conectado al cliente de League of Legends.")
    update_gui_status("Conectado a LCU")
    summoner = await connection.request("get", "/lol-summoner/v1/current-summoner")
    if summoner.status == 200:
        data = await summoner.json()
        logger.info(f"Bienvenido, {data['displayName']}")
    asyncio.create_task(search_and_join_loop(connection))

@connector.close
async def disconnect(_):
    logger.info("Conexión con el cliente cerrada. Esperando reinicio...")
    update_gui_status("Esperando cliente LCU...")

@connector.ws.register("/lol-lobby/v2/received-invitations", event_types=("CREATE",))
async def auto_accept_invite(connection, event):
    global is_searching, bot_active
    if not bot_active: return
    for invitation in event.data:
        invitation_id = invitation["invitationId"]
        logger.info(f"Invitación recibida. Aceptando...")
        await connection.request("post", f"/lol-lobby/v2/received-invitations/{invitation_id}/accept")
        is_searching = False
        update_gui_status("Invitación Aceptada")

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
            
            update_gui_status("Moviendo a Espectador...")
            last_switch_attempt = current_time
            res = await connection.request("post", "/lol-lobby/v1/lobby/custom/switch-teams")
            if res.status in [200, 204]:
                logger.info("Moviendo a Espectador Exitoso.")
                update_gui_status("En Lobby (Espectador)")

@connector.ws.register("/lol-gameflow/v1/gameflow-phase", event_types=("UPDATE",))
async def gameflow_handler(connection, event):
    global is_searching, bot_active
    if not bot_active: return

    phase = event.data
    phase_name = GAMEFLOW_PHASES.get(phase, phase)
    update_gui_status(phase_name)

    if phase == "InProgress":
        from core.game_automation import trigger_camera_automation
        trigger_camera_automation(delay=BOT_CONFIG["camera_delay"])

    if phase in ["EndOfGame", "WaitingForStats"]:
        logger.info("Juego terminado (o Remake/Abandono). Iniciando limpieza...")
        await asyncio.sleep(5)
        await connection.request("post", "/lol-end-of-game/v1/state/dismiss-stats")
        await connection.request("post", "/lol-lobby/v2/lobby/quit")
        is_searching = True
        
        if BOT_CONFIG["invite_only"]:
            update_gui_status("Esperando invitación...")
        else:
            update_gui_status(f"Buscando '{BOT_CONFIG['lobby_name']}'...")

    elif phase == "None":
        if not is_searching:
            is_searching = True
            if BOT_CONFIG["invite_only"]:
                update_gui_status("Esperando invitación...")
            else:
                update_gui_status(f"Buscando '{BOT_CONFIG['lobby_name']}'...")


# --- Control API para la GUI ---
def start_bot(callback, config_data):
    global bot_active, is_searching, status_callback, connector_thread_started, BOT_CONFIG
    
    BOT_CONFIG.update(config_data)
    
    bot_active = True
    is_searching = True
    status_callback = callback
    
    if BOT_CONFIG["invite_only"]:
        update_gui_status("Iniciando. Esperando invitaciones...")
    else:
        update_gui_status(f"Iniciando. Buscando '{BOT_CONFIG['lobby_name']}'...")
    
    if not connector_thread_started:
        connector_thread_started = True
        threading.Thread(target=connector.start, daemon=True).start()

def stop_bot():
    global bot_active, is_searching
    bot_active = False
    is_searching = False
    update_gui_status("Bot Detenido.")
