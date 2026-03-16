from lcu_driver import Connector


connector = Connector()


@connector.ready
async def connect(connection):
    lobbies = await connection.request("get", "/lol-lobby/v1/custom-games")
    print(await lobbies.json())


@connector.close
async def disconnect(connection):
    print("Finished task")


connector.start()
