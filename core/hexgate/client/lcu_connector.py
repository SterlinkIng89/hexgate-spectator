"""
LCU Connector setup, lifecycle management, and WebSocket bridge.

The process_optimizer patch is applied here, immediately before the Connector
is instantiated, ensuring the patch is in place before lcu_driver does any
process scanning. This is explicit and deterministic, not a side-effect of import.
"""

import asyncio
from lcu_driver import Connector
from core.hexgate.patches.process_optimizer import apply as apply_process_patch
from core.hexgate.state import bot_state, logger

# Workaround: lcu_driver requires an event loop when Connector is created
try:
    asyncio.get_event_loop()
except RuntimeError:
    asyncio.set_event_loop(asyncio.new_event_loop())

# Apply the fast process scan patch before instantiating the connector
apply_process_patch()

connector = Connector()


def init_connector_events(sync_state_fn, search_loop_fn):
    """Registers connection lifecycle callbacks on the Connector instance."""

    @connector.ready
    async def connect(connection):
        bot_state.lcu_connection = connection
        logger.info("Connected to League of Legends client.")
        bot_state.update_gui_status("Connected to LCU")

        try:
            summoner = await connection.request("get", "/lol-summoner/v1/current-summoner")
            if summoner.status == 200:
                data = await summoner.json()
                logger.info(f"Welcome, {data.get('displayName', 'Summoner')}")
        except Exception as e:
            logger.debug(f"Could not retrieve summoner info: {e}")

        await sync_state_fn(connection)
        asyncio.create_task(search_loop_fn(connection))

    @connector.close
    async def disconnect(_):
        bot_state.lcu_connection = None
        logger.info("Connection with the client closed. Waiting for restart...")
        bot_state.update_gui_status("Waiting for LCU client...")
