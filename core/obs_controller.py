import logging
import threading
import time

logger = logging.getLogger(__name__)

class OBSController:
    """
    Thread-safe controller for OBS Studio via obs-websocket v5 protocol (obsws-python).
    Handles connecting, streaming control, scene/profile/collection switching,
    and graceful error recovery when OBS is offline.
    """
    def __init__(self):
        self._client = None
        self._lock = threading.Lock()
        self.host = "localhost"
        self.port = 4455
        self.password = ""
        self.enabled = False
        self.profile = ""
        self.scene_collection = ""
        self.scene = ""
        self.auto_start = True
        self.auto_stop = True

    def configure(self, config_dict: dict):
        """Updates connection parameters and preferences from dictionary."""
        with self._lock:
            self.enabled = bool(config_dict.get("obs_enabled", False))
            self.host = config_dict.get("obs_host", "localhost") or "localhost"
            try:
                self.port = int(config_dict.get("obs_port", 4455))
            except (ValueError, TypeError):
                self.port = 4455
            self.password = config_dict.get("obs_password", "") or ""
            self.profile = config_dict.get("obs_profile", "").strip()
            self.scene_collection = config_dict.get("obs_scene_collection", "").strip()
            self.scene = config_dict.get("obs_scene", "").strip()
            self.auto_start = bool(config_dict.get("obs_auto_start", True))
            self.auto_stop = bool(config_dict.get("obs_auto_stop", True))

    @property
    def is_connected(self) -> bool:
        with self._lock:
            return self._client is not None

    def connect(self) -> bool:
        """Attempts to establish a connection to OBS WebSocket server."""
        if not self.enabled:
            return False

        with self._lock:
            if self._client is not None:
                return True
            try:
                import obsws_python as obs
                logger.info(f"[OBS] Connecting to OBS at {self.host}:{self.port}...")
                client = obs.ReqClient(host=self.host, port=self.port, password=self.password, timeout=3)
                version = client.get_version()
                logger.info(f"[OBS] Connected successfully to OBS Studio {version.obs_version} (WebSocket v{version.obs_web_socket_version})")
                self._client = client
                return True
            except Exception as e:
                logger.warning(f"[OBS] Could not connect to OBS ({self.host}:{self.port}): {e}")
                self._client = None
                return False

    def disconnect(self):
        """Closes the connection to OBS Studio."""
        with self._lock:
            if self._client is not None:
                try:
                    self._client.disconnect()
                except Exception:
                    pass
                self._client = None
                logger.info("[OBS] Disconnected from OBS.")

    def _ensure_connected(self) -> bool:
        if self._client is None:
            return self.connect()
        return True

    def get_stream_status(self) -> dict:
        """Returns dictionary with current stream state."""
        with self._lock:
            if not self._ensure_connected():
                return {"active": False, "timecode": "", "reconnecting": False, "connected": False}
            try:
                status = self._client.get_stream_status()
                return {
                    "active": getattr(status, "output_active", False),
                    "timecode": getattr(status, "output_timecode", ""),
                    "reconnecting": getattr(status, "output_reconnecting", False),
                    "connected": True
                }
            except Exception as e:
                logger.warning(f"[OBS] Error checking stream status: {e}")
                self._client = None
                return {"active": False, "timecode": "", "reconnecting": False, "connected": False}

    def set_profile(self, profile_name: str) -> bool:
        """Switches the current OBS Profile."""
        if not profile_name:
            return True
        with self._lock:
            if not self._ensure_connected():
                return False
            try:
                logger.info(f"[OBS] Switching profile to: \"{profile_name}\"")
                self._client.set_current_profile(profile_name)
                return True
            except Exception as e:
                logger.error(f"[OBS] Failed to switch profile to \"{profile_name}\": {e}")
                return False

    def set_scene_collection(self, collection_name: str) -> bool:
        """Switches the current OBS Scene Collection."""
        if not collection_name:
            return True
        with self._lock:
            if not self._ensure_connected():
                return False
            try:
                logger.info(f"[OBS] Switching scene collection to: \"{collection_name}\"")
                self._client.set_current_scene_collection(collection_name)
                return True
            except Exception as e:
                logger.error(f"[OBS] Failed to switch scene collection to \"{collection_name}\": {e}")
                return False

    def set_scene(self, scene_name: str) -> bool:
        """Switches the active program scene."""
        if not scene_name:
            return True
        with self._lock:
            if not self._ensure_connected():
                return False
            try:
                logger.info(f"[OBS] Switching program scene to: \"{scene_name}\"")
                self._client.set_current_program_scene(scene_name)
                return True
            except Exception as e:
                logger.error(f"[OBS] Failed to switch program scene to \"{scene_name}\": {e}")
                return False

    def start_stream(self) -> bool:
        """Starts streaming in OBS if not already running."""
        if not self.enabled:
            return False
        with self._lock:
            if not self._ensure_connected():
                logger.warning("[OBS] Cannot start stream: not connected to OBS.")
                return False
            try:
                status = self._client.get_stream_status()
                if getattr(status, "output_active", False):
                    logger.info("[OBS] Stream is already active.")
                    return True
                logger.info("[OBS] Starting stream...")
                self._client.start_stream()
                logger.info("[OBS] Stream started successfully.")
                return True
            except Exception as e:
                logger.error(f"[OBS] Failed to start stream: {e}")
                return False

    def stop_stream(self) -> bool:
        """Stops streaming in OBS if currently running."""
        if not self.enabled:
            return False
        with self._lock:
            if not self._ensure_connected():
                return False
            try:
                status = self._client.get_stream_status()
                if not getattr(status, "output_active", False):
                    logger.info("[OBS] Stream is already stopped.")
                    return True
                logger.info("[OBS] Stopping stream...")
                self._client.stop_stream()
                logger.info("[OBS] Stream stopped successfully.")
                return True
            except Exception as e:
                logger.error(f"[OBS] Failed to stop stream: {e}")
                return False

    def on_game_start(self):
        """
        Triggered when match enters InProgress phase.
        Applies profile, scene collection, scene (if configured), and starts the stream.
        Runs asynchronously in a daemon thread.
        """
        if not self.enabled or not self.auto_start:
            return

        def _worker():
            time.sleep(1.0) # Small pause for game window to stabilize
            if not self._ensure_connected():
                return

            if self.profile:
                self.set_profile(self.profile)
                time.sleep(0.5)

            if self.scene_collection:
                self.set_scene_collection(self.scene_collection)
                time.sleep(0.5)

            if self.scene:
                self.set_scene(self.scene)
                time.sleep(0.2)

            self.start_stream()

        threading.Thread(target=_worker, daemon=True).start()

    def on_game_end(self):
        """
        Triggered when match cleanup runs (EndOfGame, Remake, Terminated, etc.).
        Stops the stream if auto_stop is enabled.
        Runs asynchronously in a daemon thread.
        """
        if not self.enabled or not self.auto_stop:
            return

        def _worker():
            self.stop_stream()

        threading.Thread(target=_worker, daemon=True).start()

# Global singleton instance
obs_controller = OBSController()
