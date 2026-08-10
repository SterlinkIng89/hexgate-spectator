# Scrim Auto Spectator (LoL)

Tool created to automate the process of joining lobbies, managing remakes and exiting matches for scrims in League of Legends.

## What this project uses

- Python
- CustomTkinter (GUI)
- lcu-driver (League client connection)
- Requests (local game API / Live Client Data)
- pydirectinput + pyautogui (camera and keyboard automation)
- threading + asyncio (parallel tasks)
- logging + config.json (logs and persistent settings)

## Main features

- Automatic custom lobby search by name.
- Join attempts with multiple passwords.
- Invite Only mode (waits for invites without searching).
- Automatic invite acceptance.
- Automatic switch to spectator mode in lobby.
- Match start detection and automatic camera trigger.
- Automatic zoom adjustment for spectating.
- Automatic loop of joining lobbies, remaking, exiting and searching again.
- Visual interface with real-time status and logs.

## Logs & Configuration

The application automatically saves user configuration and execution logs in the Windows AppData directory:

- **Log file**: `%APPDATA%\HexgateSpectator\hexgate.log`
- **Config file**: `%APPDATA%\HexgateSpectator\config.json`
