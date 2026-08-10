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
    res = await connection.request('get', '/lol-lobby/v1/custom-games')
    if res.status == 200:
        games = await res.json()
        print(json.dumps(games, indent=2))
    else:
        print(f"Status: {res.status}")
    sys.exit(0)

connector.start()
