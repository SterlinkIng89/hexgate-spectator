import asyncio
import json
import sys

try:
    asyncio.get_event_loop()
except RuntimeError:
    asyncio.set_event_loop(asyncio.new_event_loop())

from lcu_driver import Connector

connector = Connector()

@connector.ready
async def connect(connection):
    lobby = await connection.request('get', '/lol-lobby/v2/lobby')
    if lobby.status == 200:
        data = await lobby.json()
        lm = data.get('localMember')
        if lm:
            print(f"Spectator teamId: {lm.get('teamId')} isSpectator: {lm.get('isSpectator')} role: {lm.get('role')} team: {lm.get('team')}")
    else:
        print("Not in lobby")
    sys.exit(0)

connector.start()
