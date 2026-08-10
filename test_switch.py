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
            print(f"Current isSpectator: {lm.get('isSpectator')}")
            for t in ["Observer", "Spectator", "SPEC", "500"]:
                res = await connection.request("post", f"/lol-lobby/v2/lobby/team/{t}")
                print(f"Switch status with {t}: {res.status} {await res.text()}")
                await asyncio.sleep(1)
            
            lobby2 = await connection.request('get', '/lol-lobby/v2/lobby')
            data2 = await lobby2.json()
            print(f"New isSpectator: {data2.get('localMember', {}).get('isSpectator')}")
    else:
        print("Not in a lobby")
    sys.exit(0)

connector.start()
