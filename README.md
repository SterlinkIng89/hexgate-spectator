# Scrim Auto Spectator (LoL)

Tool created to automate the process of joining lobbies, managing remakes and exiting matches for scrims in League of Legends.

## What this project uses

- Python
- CustomTkinter
- lcu-driver
- Requests
- pydirectinput + pyautogui
- threading + asyncio
- logging + config.json

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

- **Logs folder**: `%APPDATA%\HexgateSpectator\logs\`
- **Config file**: `%APPDATA%\HexgateSpectator\config.json`
