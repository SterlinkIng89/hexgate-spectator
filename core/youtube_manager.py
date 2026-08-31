import os
import sys
import shutil
import json
import time
import logging
import threading
from datetime import datetime, timezone
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

from core.discord_notifier import send_discord_notification_async

logger = logging.getLogger(__name__)

SCOPES = ['https://www.googleapis.com/auth/youtube']
APPDATA_DIR = os.path.join(os.getenv('APPDATA', os.path.expanduser('~')), 'HexgateSpectator')

VALID_PRIVACY_STATUSES = frozenset({"public", "unlisted", "private"})
DEFAULT_PRIVACY = "unlisted"

class YouTubeManager:
    """
    Manages YouTube Data API v3 authentication, live stream creation,
    broadcast lifecycle (live/complete), stream URL retrieval, and Discord live notifications.
    """
    def __init__(self):
        self.client_secret_file = os.path.join(APPDATA_DIR, 'client_secret.json')
        self.token_file = os.path.join(APPDATA_DIR, 'yt_token.json')
        self.channel_cache_file = os.path.join(APPDATA_DIR, 'yt_channel.json')
        self.credentials = None
        self.youtube = None
        self.channel_name = None
        self.active_broadcast_id = None
        self.active_stream_url = None
        self.active_stream_title = None
        self.enabled = False
        self.stream_title_template = "EST vs INTZ - {date}"
        self.privacy = DEFAULT_PRIVACY
        self.discord_webhook_url = None
        self.discord_enabled = False
        self._notified_broadcast_ids = set()
        self._lock = threading.RLock()
        self._auth_in_progress = False
        self._creating_broadcast = False
        self._url_callback = None

    def _candidate_search_dirs(self) -> list[str]:
        """Returns directories where configuration and credentials might reside."""
        dirs = []
        try:
            dirs.append(os.path.dirname(os.path.abspath(sys.executable)))
        except Exception:
            pass
        try:
            dirs.append(os.getcwd())
        except Exception:
            pass
        try:
            dirs.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        except Exception:
            pass
        if hasattr(sys, '_MEIPASS'):
            dirs.append(getattr(sys, '_MEIPASS'))
        return dirs

    def _candidate_secret_paths(self) -> list[str]:
        """Returns candidate paths where client_secret.json might be located."""
        candidates = [self.client_secret_file]
        for directory in self._candidate_search_dirs():
            candidates.append(os.path.join(directory, 'client_secret.json'))
        return list(dict.fromkeys(candidates))

    def get_client_secret_path(self) -> str | None:
        """
        Locates client_secret.json from candidate paths.
        If found outside AppData, automatically copies it to AppData for persistence across builds.
        """
        for path in self._candidate_secret_paths():
            if os.path.isfile(path):
                if os.path.abspath(path) != os.path.abspath(self.client_secret_file):
                    try:
                        os.makedirs(os.path.dirname(os.path.abspath(self.client_secret_file)), exist_ok=True)
                        shutil.copy2(path, self.client_secret_file)
                        logger.info(f"[YouTube] Migrated client_secret.json to {self.client_secret_file}")
                        return self.client_secret_file
                    except Exception as e:
                        logger.debug(f"[YouTube] Could not migrate secret to AppData: {e}")
                        return path
                return self.client_secret_file
        return None

    def _candidate_token_paths(self) -> list[str]:
        """Returns candidate paths where yt_token.json might be located."""
        candidates = [self.token_file]
        for directory in self._candidate_search_dirs():
            candidates.append(os.path.join(directory, 'yt_token.json'))
        return list(dict.fromkeys(candidates))

    def get_token_path(self) -> str | None:
        """
        Locates yt_token.json from candidate paths.
        If found outside AppData, automatically copies it to AppData.
        """
        for path in self._candidate_token_paths():
            if os.path.isfile(path):
                if os.path.abspath(path) != os.path.abspath(self.token_file):
                    try:
                        os.makedirs(os.path.dirname(os.path.abspath(self.token_file)), exist_ok=True)
                        shutil.copy2(path, self.token_file)
                        logger.info(f"[YouTube] Migrated yt_token.json to {self.token_file}")
                        return self.token_file
                    except Exception as e:
                        logger.debug(f"[YouTube] Could not migrate token to AppData: {e}")
                        return path
                return self.token_file
        return None

    def is_configured(self) -> bool:
        """Returns True if a valid client_secret.json is discovered."""
        return bool(self.get_client_secret_path())

    def is_authenticated(self) -> bool:
        """Returns True if we have valid or refreshable credentials."""
        with self._lock:
            if not self.credentials:
                self._load_credentials()
            return bool(self.credentials and self.credentials.valid)

    def _read_channel_cache(self) -> str | None:
        """Reads cached channel name from disk if available."""
        if os.path.exists(self.channel_cache_file):
            try:
                with open(self.channel_cache_file, 'r', encoding='utf-8') as cf:
                    return json.load(cf).get('channel_name')
            except Exception as e:
                logger.debug(f"[YouTube] Error reading channel cache: {e}")
        return None

    def _save_channel_cache(self, channel_name: str):
        """Persists channel name to cache file on disk."""
        try:
            os.makedirs(os.path.dirname(os.path.abspath(self.channel_cache_file)), exist_ok=True)
            with open(self.channel_cache_file, 'w', encoding='utf-8') as cf:
                json.dump({"channel_name": channel_name}, cf)
        except Exception as e:
            logger.warning(f"[YouTube] Failed to write channel cache: {e}")

    def _build_youtube_client(self):
        """Initializes the Google API YouTube v3 client safely."""
        if not self.credentials or not self.credentials.valid:
            return
        try:
            self.youtube = build('youtube', 'v3', credentials=self.credentials, static_discovery=False)
        except TypeError:
            try:
                self.youtube = build('youtube', 'v3', credentials=self.credentials)
            except Exception as e:
                logger.warning(f"[YouTube] API client build error: {e}")
        except Exception as e:
            logger.warning(f"[YouTube] API client build error: {e}")

    def _load_credentials(self):
        """Loads saved OAuth credentials from token file if present and loads/resolves channel name."""
        token_path = self.get_token_path() or self.token_file
        if os.path.exists(token_path):
            try:
                self.credentials = Credentials.from_authorized_user_file(token_path, SCOPES)
                if self.credentials and self.credentials.expired and self.credentials.refresh_token:
                    try:
                        self.credentials.refresh(Request())
                        os.makedirs(os.path.dirname(os.path.abspath(self.token_file)), exist_ok=True)
                        with open(self.token_file, 'w', encoding='utf-8') as token:
                            token.write(self.credentials.to_json())
                    except Exception as e:
                        logger.warning(f"[YouTube] Token refresh error: {e}")
                        self.credentials = None
                
                if self.credentials and self.credentials.valid:
                    self.channel_name = self._read_channel_cache()

                    if not self.youtube:
                        self._build_youtube_client()

                    if not self.channel_name and self.youtube:
                        self._fetch_channel_name()
            except Exception as e:
                logger.error(f"[YouTube] Error loading token file: {e}")
                self.credentials = None

    def authenticate(self, force_interactive=False, on_completed=None) -> bool:
        """
        Authenticates with YouTube API.
        If force_interactive is True, triggers browser login flow.
        Optional on_completed(success, channel_name_or_error) callback.
        """
        with self._lock:
            if self._auth_in_progress:
                return False
            self._auth_in_progress = True

        def _auth_worker():
            success = False
            result_msg = ""
            try:
                if force_interactive:
                    secret_path = self.get_client_secret_path()
                    if not secret_path:
                        result_msg = "client_secret.json not found"
                        logger.warning(f"[YouTube] {result_msg}")
                        return

                    logger.info("[YouTube] Launching OAuth browser authentication...")
                    flow = InstalledAppFlow.from_client_secrets_file(secret_path, SCOPES)
                    self.credentials = flow.run_local_server(port=0, prompt="consent")
                    os.makedirs(os.path.dirname(os.path.abspath(self.token_file)), exist_ok=True)
                    with open(self.token_file, 'w', encoding='utf-8') as token:
                        token.write(self.credentials.to_json())
                else:
                    self._load_credentials()

                if self.credentials and self.credentials.valid:
                    if not self.youtube:
                        self._build_youtube_client()
                    if not self.channel_name:
                        self.channel_name = self._read_channel_cache()
                    if not self.channel_name and self.youtube:
                        self._fetch_channel_name()
                    success = True
                    result_msg = self.channel_name or "Connected"
                else:
                    result_msg = "Not authenticated"

            except Exception as e:
                logger.error(f"[YouTube] Authentication failed: {e}")
                result_msg = str(e)
            finally:
                with self._lock:
                    self._auth_in_progress = False
                if on_completed:
                    on_completed(success, result_msg)

        if force_interactive:
            t = threading.Thread(target=_auth_worker, daemon=True, name="YouTubeAuthWorker")
            t.start()
            return True
        else:
            _auth_worker()
            return self.is_authenticated()


    def _fetch_channel_name(self):
        """Fetches and caches the channel title for the authenticated user."""
        if not self.youtube:
            return
        try:
            request = self.youtube.channels().list(part="snippet", mine=True)
            response = request.execute()
            items = response.get('items', [])
            snippet = items[0].get('snippet', {}) if items else {}
            self.channel_name = snippet.get('title') or snippet.get('customUrl') or "YouTube Channel"
            logger.info(f"[YouTube] Authenticated as channel: {self.channel_name}")
            self._save_channel_cache(self.channel_name)
        except Exception as e:
            logger.error(f"[YouTube] Failed to fetch channel title: {e}")
            if not self.channel_name:
                self.channel_name = "YouTube Channel"

    def logout(self):
        """Clears stored credentials, cached metadata, and resets state."""
        with self._lock:
            self.credentials = None
            self.youtube = None
            self.channel_name = None
            self.active_broadcast_id = None
            self.active_stream_url = None
            self.active_stream_title = None
            self.discord_webhook_url = None
            self.discord_enabled = False
            self._notified_broadcast_ids.clear()
            for filepath in [self.token_file, self.channel_cache_file]:
                if os.path.exists(filepath):
                    try:
                        os.remove(filepath)
                        logger.info(f"[YouTube] Removed {filepath}.")
                    except Exception as e:
                        logger.warning(f"[YouTube] Failed to remove {filepath}: {e}")

    @staticmethod
    def format_title(title_template: str) -> str:
        """
        Formats a stream title replacing placeholders like {date} and {time}.
        Example: 'EST vs INTZ - {date}' -> 'EST vs INTZ - 24/08/2026'
        """
        now = datetime.now()
        date_str = now.strftime("%d/%m/%Y")
        time_str = now.strftime("%H:%M")
        
        formatted = title_template.replace("{date}", date_str).replace("{time}", time_str)
        return formatted.strip() or f"Live Stream - {date_str}"

    def _get_or_create_stream(self) -> str:
        """
        Retrieves an existing reusable liveStream or creates a default one.
        Returns the streamId.
        """
        if not self.youtube:
            raise RuntimeError("YouTube API not initialized.")

        try:
            streams_response = self.youtube.liveStreams().list(part="id,snippet,cdn", mine=True).execute()
            items = streams_response.get("items", [])
            if items:
                return items[0]["id"]
        except Exception as e:
            logger.warning(f"[YouTube] Could not list existing streams: {e}")

        insert_response = self.youtube.liveStreams().insert(
            part="snippet,cdn",
            body={
                "snippet": {
                    "title": "Hexgate Spectator Ingestion Stream"
                },
                "cdn": {
                    "frameRate": "variable",
                    "ingestionType": "rtmp",
                    "resolution": "variable"
                }
            }
        ).execute()
        return insert_response["id"]

    def create_broadcast(self, title_template: str, privacy: str = "unlisted") -> tuple[str, str]:
        """
        Creates a new YouTube Live Broadcast, binds it to an ingestion stream without monitor preview,
        and returns (broadcast_id, watch_url).
        """
        with self._lock:
            if not self.youtube or not self.is_authenticated():
                if not self.authenticate():
                    raise RuntimeError("YouTube account is not authenticated.")

            formatted_title = self.format_title(title_template)
            now_iso = datetime.now(timezone.utc).isoformat()

            privacy_clean = privacy.lower().strip() if privacy else DEFAULT_PRIVACY
            if privacy_clean not in VALID_PRIVACY_STATUSES:
                logger.warning(f"[YouTube] Invalid privacy status '{privacy}', falling back to '{DEFAULT_PRIVACY}'.")
                privacy_clean = DEFAULT_PRIVACY

            logger.info(f"[YouTube] Creating broadcast: '{formatted_title}' ({privacy_clean})...")

            broadcast_body = {
                "snippet": {
                    "title": formatted_title,
                    "scheduledStartTime": now_iso,
                    "description": "Stream automatically managed by Hexgate Spectator."
                },
                "status": {
                    "privacyStatus": privacy_clean,
                    "selfDeclaredMadeForKids": False
                },
                "contentDetails": {
                    "enableAutoStart": False,
                    "enableAutoStop": False,
                    "monitorStream": {"enableMonitorStream": False},
                    "latencyPreference": "low",
                    "recordFromStart": True,
                    "enableDvr": True,
                    "enableEmbed": True
                }
            }

            broadcast_res = self.youtube.liveBroadcasts().insert(
                part="snippet,status,contentDetails",
                body=broadcast_body
            ).execute()

            broadcast_id = broadcast_res["id"]
            watch_url = f"https://www.youtube.com/watch?v={broadcast_id}"

            # Bind to stream ingestion
            try:
                stream_id = self._get_or_create_stream()
                self.youtube.liveBroadcasts().bind(
                    part="id,contentDetails",
                    id=broadcast_id,
                    streamId=stream_id
                ).execute()
                logger.info(f"[YouTube] Broadcast {broadcast_id} bound to stream {stream_id}")
            except Exception as e:
                logger.warning(f"[YouTube] Failed to bind broadcast to stream: {e}")

            self.active_broadcast_id = broadcast_id
            self.active_stream_url = watch_url
            self.active_stream_title = formatted_title

            logger.info(f"[YouTube] Broadcast created successfully! Link: {watch_url}")
            return broadcast_id, watch_url

    def create_broadcast_async(self, title_template: str, privacy: str = "unlisted", on_success=None, on_error=None):
        """Non-blocking call to create a broadcast and invoke a callback."""
        def _worker():
            try:
                _, watch_url = self.create_broadcast(title_template=title_template, privacy=privacy)
                if on_success:
                    on_success(watch_url)
            except Exception as e:
                logger.error(f"[YouTube] Failed to initialize stream broadcast: {e}")
                if on_error:
                    on_error(e)
        threading.Thread(target=_worker, daemon=True, name="YouTubeCreateWorker").start()

    def configure(self, config_dict: dict):
        """Updates YouTube and Discord integration settings from dictionary."""
        with self._lock:
            if "yt_enabled" in config_dict:
                self.enabled = bool(config_dict.get("yt_enabled"))
            if "yt_stream_title" in config_dict:
                self.stream_title_template = config_dict.get("yt_stream_title", "EST vs INTZ - {date}") or "EST vs INTZ - {date}"
            if "yt_privacy" in config_dict:
                self.privacy = config_dict.get("yt_privacy", DEFAULT_PRIVACY) or DEFAULT_PRIVACY
            if "discord_webhook_url" in config_dict:
                self.discord_webhook_url = (config_dict.get("discord_webhook_url", "") or "").strip()
            if "discord_enabled" in config_dict:
                self.discord_enabled = bool(config_dict.get("discord_enabled", False))

    def set_url_callback(self, callback):
        """Registers a callback(url: str) invoked whenever the active stream URL updates."""
        with self._lock:
            self._url_callback = callback
            if self.active_stream_url and callback:
                try:
                    callback(self.active_stream_url)
                except Exception as e:
                    logger.warning(f"[YouTube] Initial URL callback error: {e}")

    def _notify_url_changed(self, url: str):
        """Thread-safely dispatches URL update to registered callback."""
        with self._lock:
            cb = self._url_callback
        if cb:
            try:
                cb(url)
            except Exception as e:
                logger.warning(f"[YouTube] Stream URL callback error: {e}")

    def find_active_broadcast(self) -> tuple[str, str] | None:
        """
        Queries YouTube Data API to locate an existing active or upcoming broadcast on the channel.
        Returns (broadcast_id, watch_url) if found, else None.
        """
        with self._lock:
            if not self.youtube or not self.is_authenticated():
                return None

            for status_filter in ["active", "upcoming"]:
                try:
                    req = self.youtube.liveBroadcasts().list(
                        part="id,snippet,status",
                        broadcastStatus=status_filter,
                        mine=True
                    )
                    res = req.execute()
                    items = res.get("items", [])
                    if items:
                        broadcast = items[0]
                        bid = broadcast["id"]
                        title = broadcast.get("snippet", {}).get("title", "Live Stream")
                        watch_url = f"https://www.youtube.com/watch?v={bid}"
                        self.active_broadcast_id = bid
                        self.active_stream_url = watch_url
                        self.active_stream_title = title
                        logger.info(f"[YouTube] Discovered {status_filter} broadcast '{title}' ({bid}): {watch_url}")
                        self._notify_url_changed(watch_url)
                        return bid, watch_url
                except Exception as e:
                    logger.debug(f"[YouTube] Error checking {status_filter} broadcasts: {e}")

            return None

    def on_stream_start(self):
        """
        Triggered when OBS starts streaming.
        Ensures active broadcast exists, receives/updates the watch link, and transitions to LIVE.
        """
        if not self.is_authenticated():
            if not self.authenticate(force_interactive=False):
                logger.warning("[YouTube] OBS stream started, but YouTube account is not connected. Broadcast link cannot be retrieved.")
                return

        with self._lock:
            if self.active_broadcast_id:
                logger.info(f"[YouTube] OBS stream started with existing broadcast {self.active_broadcast_id}. Transitioning to LIVE...")
                self.transition_to_live_async(self.active_broadcast_id)
                return

            if self._creating_broadcast:
                logger.debug("[YouTube] Broadcast resolution already in progress on stream start.")
                return
            self._creating_broadcast = True

        try:
            # 1. First check if an active/upcoming broadcast already exists on YouTube
            found = self.find_active_broadcast()
            if found:
                bid, _ = found
                self.transition_to_live_async(bid)
                return

            # 2. If no broadcast exists and auto-create is enabled, create a new one
            if self.enabled:
                logger.info(f"[YouTube] Stream started. Auto-creating live broadcast ('{self.stream_title_template}', {self.privacy})...")
                bid, watch_url = self.create_broadcast(
                    title_template=self.stream_title_template,
                    privacy=self.privacy
                )
                self._notify_url_changed(watch_url)
                self.transition_to_live_async(bid)
            else:
                logger.info("[YouTube] OBS stream started, but Auto-create stream is disabled and no active broadcast was found.")
        except Exception as e:
            logger.error(f"[YouTube] Failed to manage broadcast on stream start: {e}")
        finally:
            with self._lock:
                self._creating_broadcast = False

    def on_stream_start_async(self):
        """Non-blocking call to handle stream start broadcast resolution and transition."""
        threading.Thread(target=self.on_stream_start, daemon=True, name="YTStreamStartWorker").start()

    def configure_discord(self, webhook_url: str, enabled: bool = True):
        """Configures Discord webhook notification settings for live broadcast transitions."""
        with self._lock:
            self.discord_webhook_url = (webhook_url or "").strip()
            self.discord_enabled = bool(enabled)

    def _send_discord_notification_if_needed(self, broadcast_id: str):
        """Dispatches Discord webhook notification once when the broadcast goes live."""
        with self._lock:
            if not self.discord_enabled or not self.discord_webhook_url:
                return
            if not broadcast_id or broadcast_id in self._notified_broadcast_ids:
                return

            watch_url = self.active_stream_url or f"https://www.youtube.com/watch?v={broadcast_id}"
            stream_title = self.active_stream_title or "Live Stream"
            self._notified_broadcast_ids.add(broadcast_id)

        logger.info(f"[YouTube] Triggering Discord webhook notification for live stream: {stream_title}")
        send_discord_notification_async(self.discord_webhook_url, stream_title, watch_url)

    def transition_to_live(self, broadcast_id: str = None, max_retries: int = 15, retry_interval: float = 2.0) -> bool:
        """
        Transitions broadcast to 'live'.
        Polls until YouTube receives stream ingestion data, then performs transition.
        Runs safely in background or calling thread.
        """
        with self._lock:
            bid = broadcast_id or self.active_broadcast_id
            if not self.youtube or not bid:
                return False

        for attempt in range(1, max_retries + 1):
            try:
                # Check current broadcast status
                bc = self.youtube.liveBroadcasts().list(part="status", id=bid).execute()
                items = bc.get("items", [])
                if not items:
                    logger.warning(f"[YouTube] Broadcast {bid} not found.")
                    return False

                status = items[0]["status"].get("lifeCycleStatus", "")
                if status in ["live", "liveStarting"]:
                    logger.info(f"[YouTube] Broadcast {bid} is already {status.upper()}.")
                    self._send_discord_notification_if_needed(bid)
                    return True
                elif status == "complete":
                    logger.warning(f"[YouTube] Broadcast {bid} is already COMPLETE.")
                    return False

                logger.info(f"[YouTube] Transitioning broadcast {bid} to LIVE (attempt {attempt}/{max_retries})...")
                res = self.youtube.liveBroadcasts().transition(
                    broadcastStatus="live",
                    id=bid,
                    part="status"
                ).execute()
                new_status = res.get("status", {}).get("lifeCycleStatus", "live")
                logger.info(f"[YouTube] Broadcast {bid} is now {new_status.upper()}!")
                self._send_discord_notification_if_needed(bid)
                return True

            except Exception as e:
                err_str = str(e)
                if "invalidTransition" in err_str or "redundantTransition" in err_str:
                    logger.debug(f"[YouTube] Transition waiting for RTMP stream data: {e}")
                else:
                    logger.warning(f"[YouTube] Transition attempt {attempt} error: {e}")
                time.sleep(retry_interval)
                
        logger.error(f"[YouTube] Failed to transition broadcast {bid} to LIVE after {max_retries} attempts! The RTMP stream may not be reaching YouTube.")
        return False

    def transition_to_live_async(self, broadcast_id: str = None):
        """Non-blocking call to transition the stream to live."""
        threading.Thread(target=self.transition_to_live, args=(broadcast_id,), daemon=True, name="YTLiveWorker").start()

    def complete_broadcast(self, broadcast_id: str = None) -> bool:
        """Transitions active broadcast to complete (ended)."""
        with self._lock:
            bid = broadcast_id or self.active_broadcast_id
            if not self.youtube or not bid:
                return False
            try:
                logger.info(f"[YouTube] Completing broadcast {bid}...")
                self.youtube.liveBroadcasts().transition(
                    broadcastStatus="complete",
                    id=bid,
                    part="status"
                ).execute()
                logger.info(f"[YouTube] Broadcast {bid} completed.")
                self.active_broadcast_id = None
                self.active_stream_url = None
                self.active_stream_title = None
                self._notify_url_changed("")
                return True
            except Exception as e:
                logger.debug(f"[YouTube] Error completing broadcast {bid}: {e}")
                self.active_broadcast_id = None
                self.active_stream_url = None
                self.active_stream_title = None
                self._notify_url_changed("")
                return False

    def complete_broadcast_async(self, broadcast_id: str = None):
        """Non-blocking call to complete the stream."""
        threading.Thread(target=self.complete_broadcast, args=(broadcast_id,), daemon=True, name="YTCompleteWorker").start()

# Singleton instance
youtube_manager = YouTubeManager()
