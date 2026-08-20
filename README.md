# Scrim Auto Spectator (LoL)

Tool created to automate the process of joining lobbies, managing remakes and exiting matches for scrims in League of Legends.

## What this project uses

- Python
- CustomTkinter
- lcu-driver
- Requests
- pydirectinput + pyautogui
- obsws-python (OBS WebSocket v5)
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
- **OBS Studio integration via WebSocket v5**:
  - Auto-start stream when match begins (`InProgress`).
  - Auto-stop stream on game end, remake or cleanup.
  - Automatic OBS Profile, Scene Collection, and Scene switching.
  - Resilient connection handling (no crash if OBS is offline).
- Visual interface with real-time status and logs.

## OBS Studio Setup

1. In OBS Studio, navigate to **Tools > WebSocket Server Settings**.
2. Enable the WebSocket server (default port: `4455`).
3. Set an optional server password or leave empty.
4. In Hexgate Spectator UI, enable **Enable OBS Integration** and enter the port and password if configured.

### YouTube Stream Disconnection Tip

If YouTube frequently disconnects or expires OAuth tokens in OBS:
- In YouTube Studio ("Go Live"), create or copy a **Reusable Stream Key** (from the "Stream" tab, NOT a date-scheduled "Event").
- In OBS Studio, go to **Settings > Stream > Service: YouTube - RTMPS** and choose **Use Stream Key (advanced)** instead of "Connect Account".
- Paste the reusable stream key. This key will not expire periodically.

## Logs & Configuration

The application automatically saves user configuration and execution logs in the Windows AppData directory:

- **Logs folder**: `%APPDATA%\HexgateSpectator\logs\`
- **Config file**: `%APPDATA%\HexgateSpectator\config.json`
