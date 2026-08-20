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
        self.schedule_enabled = False
        self.schedule_start_time = ""
        self.schedule_stop_time = ""
        self._scheduler_running = False
        self._last_schedule_start_day = None
        self._last_schedule_stop_day = None

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
            self.schedule_enabled = bool(config_dict.get("obs_schedule_enabled", False))
            self.schedule_start_time = config_dict.get("obs_schedule_start_time", "").strip()
            self.schedule_stop_time = config_dict.get("obs_schedule_stop_time", "").strip()

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

    def is_current_time_in_range(self) -> bool:
        """Checks if the current local time falls within the configured start and stop times."""
        if not self.schedule_start_time or not self.schedule_stop_time:
            return True
        try:
            from datetime import datetime
            now = datetime.now().time()
            start = datetime.strptime(self.schedule_start_time, "%H:%M").time()
            stop = datetime.strptime(self.schedule_stop_time, "%H:%M").time()
            if start <= stop:
                return start <= now <= stop
            else:
                # Spans midnight (e.g. 22:00 -> 03:00)
                return now >= start or now <= stop
        except Exception as e:
            logger.warning(f"[OBS Schedule] Time parsing error: {e}")
            return True

    def start_scheduler(self):
        """Starts the background schedule monitor thread."""
        if self._scheduler_running:
            return
        self._scheduler_running = True

        def _schedule_loop():
            logger.info(f"[OBS Schedule] Scheduler active (Start: {self.schedule_start_time or 'Any'}, Stop: {self.schedule_stop_time or 'Any'}).")
            from datetime import datetime
            while self._scheduler_running:
                try:
                    if self.enabled and self.schedule_enabled:
                        now_dt = datetime.now()
                        now_str = now_dt.strftime("%H:%M")
                        today_str = now_dt.strftime("%Y-%m-%d")

                        # Check scheduled start
                        if self.schedule_start_time and now_str == self.schedule_start_time:
                            if self._last_schedule_start_day != today_str:
                                self._last_schedule_start_day = today_str
                                logger.info(f"[OBS Schedule] Scheduled start time reached ({now_str}). Starting stream...")
                                def _start_worker():
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
                                threading.Thread(target=_start_worker, daemon=True).start()

                        # Check scheduled stop
                        if self.schedule_stop_time and now_str == self.schedule_stop_time:
                            if self._last_schedule_stop_day != today_str:
                                self._last_schedule_stop_day = today_str
                                logger.info(f"[OBS Schedule] Scheduled stop time reached ({now_str}). Stopping stream...")
                                threading.Thread(target=self.stop_stream, daemon=True).start()

                except Exception as e:
                    logger.warning(f"[OBS Schedule] Loop error: {e}")

                time.sleep(10)

        threading.Thread(target=_schedule_loop, daemon=True).start()

    def stop_scheduler(self):
        """Stops the background schedule monitor loop."""
        self._scheduler_running = False

    def on_game_start(self):
        """
        Triggered when match enters InProgress phase.
        Applies profile, scene collection, scene (if configured), and starts the stream.
        Respects schedule window if schedule_enabled is True.
        Runs asynchronously in a daemon thread.
        """
        if not self.enabled or not self.auto_start:
            return

        if self.schedule_enabled and not self.is_current_time_in_range():
            logger.info(f"[OBS Schedule] Game started but current time is outside scheduled window ({self.schedule_start_time} - {self.schedule_stop_time}). Skipping stream start.")
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
