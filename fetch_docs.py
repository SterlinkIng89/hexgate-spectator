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
    print("Connected to LCU")
    res = await connection.request('get', '/swagger/v2/swagger.json')
    if res.status == 200:
        data = await res.json()
        with open('lcu_swagger.json', 'w') as f:
            json.dump(data, f, indent=2)
        print("Successfully saved lcu_swagger.json")
    else:
        print(f"Failed. Status: {res.status}")
    sys.exit(0)

connector.start()
