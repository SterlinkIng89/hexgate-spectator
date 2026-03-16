import asyncio
import logging
import time
from lcu_driver import Connector

# --- Configuración ---
# Identificadores de equipos en LCU (Custom Games)
TEAM_CHAOS = 200
TEAM_ORDER = 100
TARGET_LOBBY_NAME = "SCRIM_TEST"  # Nombre del lobby a buscar

# Configuración de Logging
logging.basicConfig(
    level=logging.INFO,
    format="[Hexgate] %(asctime)s - %(levelname)s - %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# Inicializar conector LCU
connector = Connector()

# Variables Globales
is_searching = True  # Control del loop de búsqueda
last_switch_attempt = 0

# --- Estados del Juego ---
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


# --- Loop de Búsqueda Activa ---
async def search_and_join_loop(connection):
    """
    Loop infinito que busca lobbies activos con el nombre específico y se une a ellos.
    Solo busca si no estamos ya en un juego o lobby (is_searching=True).
    """
    global is_searching
    logger.info(f"Iniciando loop de búsqueda para lobbies: '{TARGET_LOBBY_NAME}'")

    while True:
        try:
            # Solo buscar si la bandera está activa
            if is_searching:
                # 1. Obtener lista de custom games
                res = await connection.request("get", "/lol-lobby/v1/custom-games")
                if res.status == 200:
                    games = await res.json()

                    # 2. Filtrar por nombre
                    target_game = next(
                        (g for g in games if g.get("lobbyName") == TARGET_LOBBY_NAME),
                        None,
                    )

                    if target_game:
                        game_id = target_game["id"]
                        logger.info(
                            f"Lobby encontrado: {TARGET_LOBBY_NAME} (ID: {game_id}). Intentando unirnos..."
                        )

                        # 3. Unirse al lobby (sin password por ahora)
                        join_res = await connection.request(
                            "post", f"/lol-lobby/v1/custom-games/{game_id}/join"
                        )

                        if join_res.status in [200, 204]:
                            logger.info("Unido exitosamente al lobby.")
                            is_searching = False  # Dejar de buscar al entrar
                        else:
                            logger.error(
                                f"Error al unirse al lobby. Status: {join_res.status}"
                            )

            # Esperar antes de la próxima iteración (5 segundos)
            await asyncio.sleep(5)

        except Exception as e:
            logger.error(f"Error en el loop de búsqueda: {e}")
            await asyncio.sleep(5)


# --- Eventos LCU ---


@connector.ready
async def connect(connection):
    """Se ejecuta cuando el script se conecta exitosamente al cliente LCU."""
    logger.info("Conectado al cliente de League of Legends.")

    # Obtener información del invocador
    summoner = await connection.request("get", "/lol-summoner/v1/current-summoner")
    if summoner.status == 200:
        data = await summoner.json()
        logger.info(f"Bienvenido, {data['displayName']}")
    else:
        logger.warning("No se pudo obtener información del invocador.")

    # Iniciar la tarea en segundo plano para buscar lobbies
    asyncio.create_task(search_and_join_loop(connection))


@connector.close
async def disconnect(_):
    logger.info("Conexión con el cliente cerrada. Esperando reinicio...")


# 1. Auto-Aceptar Invitaciones
@connector.ws.register("/lol-lobby/v2/received-invitations", event_types=("CREATE",))
async def auto_accept_invite(connection, event):
    """
    Escucha nuevas invitaciones y las acepta automáticamente.
    """
    global is_searching
    for invitation in event.data:
        invitation_id = invitation["invitationId"]
        logger.info(f"Invitación recibida (ID: {invitation_id}). Aceptando...")

        # Aceptar invitación
        await connection.request(
            "post", f"/lol-lobby/v2/received-invitations/{invitation_id}/accept"
        )
        is_searching = False  # Dejar de buscar si aceptamos una invitación


# 2. Auto-Espectador (Priority) & Monitoreo de Lobby
@connector.ws.register("/lol-lobby/v2/lobby", event_types=("CREATE", "UPDATE"))
async def handle_lobby_update(connection, event):
    """
    Monitorea el estado del lobby. Si detecta que estamos en un equipo de jugadores (100/200),
    intenta movernos a Espectador.
    """
    global last_switch_attempt, is_searching

    lobby_data = event.data
    if not lobby_data:
        return

    # Si entramos a un lobby, asegurarnos de que la busqueda se detenga
    # (por si entramos manualmente o por invitación sin que el evento invite lo capturara antes)
    if is_searching:
        is_searching = False

    # Buscar nuestro miembro local en la lista de miembros
    local_member = next(
        (m for m in lobby_data.get("members", []) if m.get("isLocalMember")), None
    )

    if local_member:
        team_id = local_member.get("teamId")

        # Si estamos en Equipo 1 (100) o Equipo 2 (200), intentar cambiar
        if team_id in [TEAM_ORDER, TEAM_CHAOS]:
            current_time = time.time()
            if current_time - last_switch_attempt < 2:  # Rate limit: 2 segundos
                return

            logger.info(
                f"Detectado en equipo de juego (TeamId: {team_id}). Intentando mover a Espectador..."
            )

            # Intentar cambiar de equipo.
            last_switch_attempt = current_time
            res = await connection.request(
                "post", "/lol-lobby/v1/lobby/custom/switch-teams"
            )

            if res.status != 204 and res.status != 200:
                logger.error(
                    f"Fallo al intentar cambiar de equipo. Status: {res.status}"
                )
            else:
                logger.info("Solicitud de cambio de equipo enviada.")


# 3. Monitoreo de Gameflow y Limpieza
@connector.ws.register("/lol-gameflow/v1/gameflow-phase", event_types=("UPDATE",))
async def gameflow_handler(connection, event):
    """
    Monitorea el cambio de fases del juego.
    """
    global is_searching
    phase = event.data
    phase_name = GAMEFLOW_PHASES.get(phase, phase)
    logger.info(f"Cambio de Fase: {phase_name}")

    # Si estamos en EndOfGame, preparar salida
    if phase == "EndOfGame":
        logger.info("Juego terminado. Iniciando limpieza...")

        # Esperar 10 segundos
        await asyncio.sleep(10)

        logger.info("Saliendo del lobby...")
        await connection.request("post", "/lol-lobby/v2/lobby/quit")

        # Reactivar búsqueda para la próxima partida
        is_searching = True
        logger.info(f"Búsqueda reactivada. Buscando '{TARGET_LOBBY_NAME}'...")

    # Si volvemos a 'None' (fuera de juego/lobby), asegurarnos de que busque
    elif phase == "None":
        if not is_searching:
            is_searching = True
            logger.info("Fase None detectada. Reactivando búsqueda.")


# Ejecutar el script
if __name__ == "__main__":
    logger.info("Iniciando Hexgate - Scrim Auto Spectator...")
    logger.info(f"Buscando lobbies llamados: '{TARGET_LOBBY_NAME}'")
    logger.info("Presiona Ctrl+C para detener.")
    connector.start()
