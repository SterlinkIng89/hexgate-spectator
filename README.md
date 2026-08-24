# Hexgate Spectator

Automated scrim spectating, OBS Studio stream automation, YouTube Live broadcast management, and Discord alerts for League of Legends.

---

## Overview

**Hexgate Spectator** automates the end-to-end workflow of finding custom scrim lobbies, switching to spectator mode, managing game client processes across remakes and game starts, controlling OBS Studio streaming, orchestrating YouTube Live broadcasts, and sending Discord notifications.

---

## Key Features

### League of Legends Automation
- **Lobby Search & Filtering**: Automatic custom lobby search supporting multiple comma-separated lobby names with fuzzy match tolerance.
- **Multi-Password Joining**: Iterates through multiple pre-configured passwords until a successful join occurs.
- **Invite Handling**: Supports *Invite Only* mode and automatic invite acceptance.
- **Spectator Switch**: Automatically switches the client slot to spectator mode inside the lobby.
- **In-Game Camera Automation**: Automatically focuses and zooms the spectator camera upon game load with configurable automation delay.
- **Gameflow Lifecycle Watchdog**: Detects match completions, remakes, player AFK disconnects, and long in-game pauses, closing stuck processes and resuming lobby search cleanly.

### OBS Studio Stream Automation
- **WebSocket v5 Integration**: Automated connection, start, and stop controls via `obsws-python`.
- **Scheduled Streaming**: Configurable start time and duration with AM/PM selector and live countdown timer (supports time windows spanning midnight).
- **Profile & Scene Collection Discovery**: Automatically scans and populates available OBS Profiles and Scene Collections into dropdown selectors.
- **Active Match Safeguard**: Prevents abrupt stream cutoffs if a spectated match is still in progress when the scheduled duration expires.
- **Connection Health & Auto-Reconnect**: Actively pings OBS, detects stale or dropped sockets, and reconnects automatically with graceful offline warnings.
- **System Sleep Prevention**: Prevents Windows system sleep and idle display timeout while the bot is actively executing.

### YouTube Live Stream Automation
- **OAuth2 Broadcast Management**: Full integration with the YouTube Live Streaming API for automated broadcast creation, transition (testing -> live -> complete), and monitoring.
- **Live Channel Display**: Visual status badge showing the authenticated YouTube channel name directly in the UI.
- **Error Handling**: Graceful API quota and token expiration handling.

### Discord Webhook Notifications
- **Automated Alerts**: Dispatches rich embed notifications containing broadcast title, stream URL, and live thumbnail when a YouTube stream goes live.
- **Dedicated UI Controls**: Embedded toggle switch and webhook URL configuration within the YouTube panel.

### Modern Desktop Interface (CustomTkinter)
- **Header Status Cards**: Real-time status indicators for Bot and Stream state.
- **Collapsible Panels**: Collapsible sections for Bot Settings, OBS Integration, and YouTube Stream Management.
- **Enhanced Console**: Startup banner, per-session visual separators, and toolbar to copy logs or open the log folder.
- **Status Footer & Resource Monitor**: Live CPU percentage and RAM consumption monitor with active application version.

---

## Installation & Usage

### Option 1: Standalone Executable (Recommended)
Download the latest `HexgateSpectator.exe` from the [Releases](https://github.com/SterlinkIng89/hexgate-spectator/releases) page. No Python installation required.

### Option 2: Run from Source
1. Clone the repository:
   ```bash
   git clone https://github.com/SterlinkIng89/hexgate-spectator.git
   cd hexgate-spectator
   ```
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Run the application:
   ```bash
   python main.py
   ```

---

## Configuration & Integrations

### 1. OBS Studio Setup
1. In OBS Studio, open **Tools > WebSocket Server Settings**.
2. Enable the WebSocket server (default port: `4455`).
3. Set an optional server password or leave blank.
4. In Hexgate Spectator, open the **OBS Integration** panel, enable OBS, and enter the port and password.
5. Click the refresh button to automatically load your OBS Profiles and Scene Collections.

### 2. YouTube Live Stream Setup
1. In Google Cloud Console, create an OAuth2 Client ID with YouTube Data API v3 scope.
2. Download the client secret JSON file as `client_secret.json` or authenticate via the application prompt.
3. In Hexgate Spectator, enable **YouTube Stream Management** and configure your broadcast title, description, and privacy status.

### 3. Discord Webhook Setup
1. In your Discord server channel settings, navigate to **Integrations > Webhooks** and create a new webhook.
2. Copy the webhook URL and paste it into the **Discord Webhook URL** field in the YouTube panel.
3. Toggle **Send Discord Notification on Stream Start**.

---

## File Locations & Logs

Configuration and logs are stored in the user AppData directory:
- **Configuration**: `%APPDATA%\HexgateSpectator\config.json`
- **Execution Logs**: `%APPDATA%\HexgateSpectator\logs\`

---

## Building Standalone Executable

To compile `HexgateSpectator.exe` using PyInstaller:

```bash
pip install pyinstaller
python -m PyInstaller HexgateSpectator.spec --noconfirm
```

The output binary will be located in `dist/HexgateSpectator.exe`.

---

## Testing

Run the test suite using pytest:

```bash
python -m pytest tests/
```
