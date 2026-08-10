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
    if lobby.status != 200:
        print("Not in a lobby")
        sys.exit(0)
        
    data = await lobby.json()
    party_id = data.get('partyId')
    
    summoner = await connection.request('get', '/lol-summoner/v1/current-summoner')
    sum_data = await summoner.json()
    puuid = sum_data.get('puuid')
    
    print(f"Party ID: {party_id}")
    print(f"PUUID: {puuid}")
    
    # Try 1: PUT /lol-lobby/v1/parties/{partyId}/members/{puuid}/role
    print("Trying PUT role...")
    for role in ["SPECTATOR", "Observer", "Spectator", "SPEC", "500"]:
        res = await connection.request('put', f'/lol-lobby/v1/parties/{party_id}/members/{puuid}/role', json={"role": role})
        print(f"PUT role {role} -> {res.status}")
        if res.status != 404:
            print(await res.text())
            
    # Try 2: POST /lol-lobby/v2/lobby/team/{team}
    print("Trying POST team...")
    for team in ["SPECTATOR", "Observer", "Spectator", "SPEC", "500"]:
        res = await connection.request('post', f'/lol-lobby/v2/lobby/team/{team}')
        print(f"POST team {team} -> {res.status}")
        if res.status != 404:
            print(await res.text())
            
    # Try 3: /lol-lobby/v1/lobby/custom/switch-teams
    print("Trying switch-teams...")
    for team in ["SPECTATOR", "Observer", "Spectator", "SPEC", "500"]:
        res = await connection.request('post', f'/lol-lobby/v1/lobby/custom/switch-teams?team={team}')
        print(f"switch-teams {team} -> {res.status}")
        if res.status != 404:
            print(await res.text())
            
    sys.exit(0)

connector.start()
