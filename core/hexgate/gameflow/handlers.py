"""
WebSocket event handlers for Gameflow phases, invitations, lobby updates, and GSM events.

Design rule: each @connector.ws handler is a thin wrapper that delegates
to a pure async function. The pure functions can be called directly by
engine.py during initial state sync, without any fake event objects.
"""

import time
import json
from core.obs_controller import obs_controller
from core.youtube_manager import youtube_manager
from core.game_automation import trigger_camera_automation
from core.hexgate.config import BOT_CONFIG, GAMEFLOW_PHASES
from core.hexgate.state import bot_state, logger
from core.hexgate.gameflow.cleanup import cleanup_game_process
import core.hexgate.gameflow.watchdog as watchdog


# ---------------------------------------------------------------------------
# Pure business logic — callable without a WebSocket event
# ---------------------------------------------------------------------------

async def process_phase_change(connection, phase: str):
    """
    Handles a gameflow phase transition.
    Called by the WebSocket handler and directly by engine.sync_state().
    """
    phase_changed = (phase != bot_state.current_phase)
    if phase_changed:
        logger.info(f"[GAMEFLOW] Phase changed: {bot_state.current_phase} -> {phase}")
        bot_state.current_phase = phase

    if phase != "None":
        bot_state.update_gui_status(GAMEFLOW_PHASES.get(phase, phase))

    if phase in ["ChampSelect", "InProgress"]:
        bot_state.is_searching = False

    if phase == "InProgress" and phase_changed:
        bot_state.was_in_progress = True
        watchdog.reset()
        trigger_camera_automation(delay=BOT_CONFIG["camera_delay"])
        obs_controller.on_game_start()
        youtube_manager.transition_to_live_async()

    if phase == "Reconnect" and phase_changed and bot_state.was_in_progress:
        logger.info("Reconnect phase detected after InProgress. All players likely left. Cleaning up...")
        await cleanup_game_process(connection, "Game abandoned (Reconnect)")
        return

    if phase in ["EndOfGame", "WaitingForStats"] and phase_changed:
        logger.info(f"[GAMEFLOW] Game over (or Remake/Dodge). Phase is {phase}. Starting cleanup...")
        await cleanup_game_process(connection, f"Game ended ({phase})")

    elif phase == "None" and phase_changed:
        bot_state.is_searching = True
        if BOT_CONFIG["invite_only"]:
            bot_state.update_gui_status("Waiting for invitation...")
        else:
            bot_state.update_gui_status(f"Searching '{BOT_CONFIG['lobby_name']}'...")


async def process_lobby_update(connection, lobby_data: dict):
    """
    Ensures the bot stays in a spectator slot when joined to a lobby.
    Called by the WebSocket handler and directly by engine.sync_state().
    """
    if not lobby_data:
        return
    local_member = lobby_data.get("localMember")
    if not local_member or local_member.get("isSpectator"):
        return

    now = time.time()
    if now - bot_state.last_switch_attempt < 2:
        return

    bot_state.update_gui_status("Moving to Spectator...")
    bot_state.last_switch_attempt = now
    res = await connection.request("post", "/lol-lobby/v2/lobby/team/SPECTATOR")
    if res.status in [200, 204]:
        logger.info("Move to Spectator Successful.")
        bot_state.update_gui_status("In Lobby (Spectator)")
    else:
        logger.warning(f"Failed to move to Spectator. Status: {res.status}")


# ---------------------------------------------------------------------------
# WebSocket thin wrappers
# ---------------------------------------------------------------------------

def register_gameflow_events(connector):
    """Registers all WebSocket event listeners on the lcu_driver connector."""

    @connector.ws.register("/lol-lobby/v2/received-invitations", event_types=("CREATE",))
    async def _ws_auto_accept_invite(connection, event):
        if not bot_state.bot_active:
            return
        for invitation in event.data:
            invitation_id = invitation.get("invitationId")
            logger.info("Invitation received. Accepting...")
            await connection.request("post", f"/lol-lobby/v2/received-invitations/{invitation_id}/accept")
            bot_state.is_searching = False
            bot_state.update_gui_status("Invitation Accepted")

    @connector.ws.register("/lol-lobby/v2/lobby", event_types=("CREATE", "UPDATE"))
    async def _ws_handle_lobby_update(connection, event):
        if not bot_state.bot_active:
            return
        await process_lobby_update(connection, event.data)

    @connector.ws.register("/lol-gameflow/v1/gameflow-phase", event_types=("UPDATE",))
    async def _ws_gameflow_handler(connection, event):
        if not bot_state.bot_active:
            return
        await process_phase_change(connection, event.data)

    @connector.ws.register(
        "/riot-messaging-service/v1/message/lol-gsm-server/v1/gsm/game-update/TERMINATED_IN_ERROR",
        event_types=("CREATE", "UPDATE")
    )
    async def _ws_handle_gsm_terminated(connection, event):
        if not bot_state.bot_active:
            return
        data = event.data or {}
        payload_raw = data.get("payload", "{}")
        try:
            payload = json.loads(payload_raw) if isinstance(payload_raw, str) else payload_raw
        except Exception:
            payload = {}
        game_id = payload.get("id", "?")
        game_state = payload.get("gameState", "TERMINATED_IN_ERROR")
        logger.info(f"[GSM] Received {game_state} for game {game_id}. Forcing game process cleanup.")
        await cleanup_game_process(connection, f"GSM {game_state} (game {game_id})")
