import logging
import threading
import time
from datetime import datetime

logger = logging.getLogger(__name__)

class OBSController:
    """
    Thread-safe controller for OBS Studio via obs-websocket v5 protocol (obsws-python).
    Handles connecting, streaming control, scene/profile/collection switching,
    and graceful error recovery when OBS is offline.
    """
    RECONNECT_COOLDOWN = 10.0  # Minimum seconds between connection retries when OBS is offline

    def __init__(self):
        self._client = None
        self._lock = threading.RLock()
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
        self._scheduler_thread = None
        self._stop_scheduler_event = threading.Event()
        self._last_schedule_start_day = None
        self._last_schedule_stop_day = None
        self._last_connect_attempt = 0.0

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

    def connect(self, force: bool = False) -> bool:
        """Attempts to establish a connection to OBS WebSocket server."""
        if not self.enabled:
            return False

        with self._lock:
            if self._client is not None:
                return True

            now = time.time()
            if not force and (now - self._last_connect_attempt) < self.RECONNECT_COOLDOWN:
                # Avoid hammering connection attempts within cooldown window
                return False

            self._last_connect_attempt = now
            t0 = time.perf_counter()
            try:
                import obsws_python as obs
                logger.info(f"[OBS] Connecting to OBS at {self.host}:{self.port}...")
                client = obs.ReqClient(host=self.host, port=self.port, password=self.password, timeout=3)
                version = client.get_version()
                elapsed_ms = (time.perf_counter() - t0) * 1000
                logger.info(
                    f"[OBS] Connected successfully to OBS Studio {version.obs_version} "
                    f"(WebSocket v{version.obs_web_socket_version}) in {elapsed_ms:.1f}ms"
                )
                self._client = client
                return True
            except Exception as e:
                elapsed_ms = (time.perf_counter() - t0) * 1000
                logger.warning(f"[OBS] Could not connect to OBS ({self.host}:{self.port}) in {elapsed_ms:.1f}ms: {e}")
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

    def _obs_call(self, log_label: str, method: str, *args) -> bool:
        """Acquires the RLock, ensures connection, then calls self._client.<method>(*args)."""
        with self._lock:
            if not self._ensure_connected():
                return False
            t0 = time.perf_counter()
            try:
                getattr(self._client, method)(*args)
                elapsed_ms = (time.perf_counter() - t0) * 1000
                logger.debug(f"[OBS] {method}{args} succeeded in {elapsed_ms:.1f}ms")
                return True
            except Exception as e:
                elapsed_ms = (time.perf_counter() - t0) * 1000
                logger.error(f"[OBS] {log_label} ({elapsed_ms:.1f}ms): {e}")
                return False

    def get_stream_status(self) -> dict:
        """Returns dictionary with current stream state."""
        with self._lock:
            if not self._ensure_connected():
                return {"active": False, "timecode": "", "reconnecting": False, "connected": False}
            t0 = time.perf_counter()
            try:
                status = self._client.get_stream_status()
                elapsed_ms = (time.perf_counter() - t0) * 1000
                logger.debug(f"[OBS] get_stream_status completed in {elapsed_ms:.1f}ms")
                return {
                    "active": getattr(status, "output_active", False),
                    "timecode": getattr(status, "output_timecode", ""),
                    "reconnecting": getattr(status, "output_reconnecting", False),
                    "connected": True
                }
            except Exception as e:
                elapsed_ms = (time.perf_counter() - t0) * 1000
                logger.warning(f"[OBS] Error checking stream status ({elapsed_ms:.1f}ms): {e}")
                self._client = None
                return {"active": False, "timecode": "", "reconnecting": False, "connected": False}

    def set_profile(self, name: str) -> bool:
        """Switches the current OBS Profile."""
        if not name:
            return True
        logger.info(f'[OBS] Switching profile to: "{name}"')
        return self._obs_call(f'Failed to switch profile to "{name}"', "set_current_profile", name)

    def set_scene_collection(self, name: str) -> bool:
        """Switches the current OBS Scene Collection."""
        if not name:
            return True
        logger.info(f'[OBS] Switching scene collection to: "{name}"')
        return self._obs_call(f'Failed to switch scene collection to "{name}"', "set_current_scene_collection", name)

    def set_scene(self, name: str) -> bool:
        """Switches the active program scene."""
        if not name:
            return True
        logger.info(f'[OBS] Switching program scene to: "{name}"')
        return self._obs_call(f'Failed to switch program scene to "{name}"', "set_current_program_scene", name)

    def start_stream(self) -> bool:
        """Starts streaming in OBS directly without redundant pre-flight query."""
        if not self.enabled:
            return False
        with self._lock:
            if not self._ensure_connected():
                logger.warning("[OBS] Cannot start stream: not connected to OBS.")
                return False
            t0 = time.perf_counter()
            try:
                logger.info("[OBS] Starting stream...")
                self._client.start_stream()
                elapsed_ms = (time.perf_counter() - t0) * 1000
                logger.info(f"[OBS] Stream started successfully in {elapsed_ms:.1f}ms.")
                return True
            except Exception as e:
                elapsed_ms = (time.perf_counter() - t0) * 1000
                err_str = str(e).lower()
                if "already active" in err_str or "output_running" in err_str:
                    logger.info(f"[OBS] Stream is already active ({elapsed_ms:.1f}ms).")
                    return True
                logger.error(f"[OBS] Failed to start stream ({elapsed_ms:.1f}ms): {e}")
                return False

    def stop_stream(self) -> bool:
        """Stops streaming in OBS directly without redundant pre-flight query."""
        if not self.enabled:
            return False
        with self._lock:
            if not self._ensure_connected():
                return False
            t0 = time.perf_counter()
            try:
                logger.info("[OBS] Stopping stream...")
                self._client.stop_stream()
                elapsed_ms = (time.perf_counter() - t0) * 1000
                logger.info(f"[OBS] Stream stopped successfully in {elapsed_ms:.1f}ms.")
                return True
            except Exception as e:
                elapsed_ms = (time.perf_counter() - t0) * 1000
                err_str = str(e).lower()
                if "not active" in err_str or "output_not_running" in err_str:
                    logger.info(f"[OBS] Stream is already stopped ({elapsed_ms:.1f}ms).")
                    return True
                logger.error(f"[OBS] Failed to stop stream ({elapsed_ms:.1f}ms): {e}")
                return False

    def _apply_scene_and_start(self):
        """
        Applies the configured profile, scene collection and scene in order,
        then starts the stream. Shared by on_game_start and the scheduler.
        """
        t0 = time.perf_counter()
        if self.profile:
            self.set_profile(self.profile)
        if self.scene_collection:
            self.set_scene_collection(self.scene_collection)
        if self.scene:
            self.set_scene(self.scene)
        self.start_stream()
        elapsed_ms = (time.perf_counter() - t0) * 1000
        logger.info(f"[OBS] _apply_scene_and_start completed in {elapsed_ms:.1f}ms")

    def is_current_time_in_range(self) -> bool:
        """Checks if the current local time falls within the configured start and stop times."""
        if not self.schedule_start_time or not self.schedule_stop_time:
            return True
        try:
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
        with self._lock:
            if self._scheduler_thread and self._scheduler_thread.is_alive():
                return
            self._stop_scheduler_event.clear()
            t = threading.Thread(target=self._schedule_loop, daemon=True, name="OBSScheduler")
            self._scheduler_thread = t
            t.start()

    def _schedule_loop(self):
        """Background loop that fires scheduled start/stop actions at the configured times."""
        logger.info(
            f"[OBS Schedule] Scheduler active "
            f"(Start: {self.schedule_start_time or 'Any'}, "
            f"Stop: {self.schedule_stop_time or 'Any'})."
        )
        while not self._stop_scheduler_event.is_set():
            try:
                if self.enabled and self.schedule_enabled:
                    now_dt = datetime.now()
                    now_str = now_dt.strftime("%H:%M")
                    today_str = now_dt.strftime("%Y-%m-%d")

                    if self.schedule_start_time and now_str == self.schedule_start_time:
                        if self._last_schedule_start_day != today_str:
                            self._last_schedule_start_day = today_str
                            logger.info(f"[OBS Schedule] Scheduled start time reached ({now_str}). Starting stream...")
                            threading.Thread(target=self._apply_scene_and_start, daemon=True).start()

                    if self.schedule_stop_time and now_str == self.schedule_stop_time:
                        if self._last_schedule_stop_day != today_str:
                            self._last_schedule_stop_day = today_str
                            logger.info(f"[OBS Schedule] Scheduled stop time reached ({now_str}). Stopping stream...")
                            threading.Thread(target=self.stop_stream, daemon=True).start()

            except Exception as e:
                logger.warning(f"[OBS Schedule] Loop error: {e}")

            self._stop_scheduler_event.wait(timeout=10)

        logger.info("[OBS Schedule] Scheduler thread stopped.")

    def stop_scheduler(self):
        """Stops the background schedule monitor loop cleanly."""
        self._stop_scheduler_event.set()

    def on_game_start(self):
        """
        Triggered when match enters InProgress phase.
        Applies profile/collection/scene and starts the stream.
        Respects schedule window if schedule_enabled is True.
        Runs asynchronously in a daemon thread.
        """
        if not self.enabled or not self.auto_start:
            return
        if self.schedule_enabled and not self.is_current_time_in_range():
            logger.info(
                f"[OBS Schedule] Game started outside scheduled window "
                f"({self.schedule_start_time} - {self.schedule_stop_time}). Skipping."
            )
            return

        def _worker():
            if self._ensure_connected():
                self._apply_scene_and_start()

        threading.Thread(target=_worker, daemon=True, name="OBSGameStartWorker").start()

    def on_game_end(self):
        """
        Triggered when match cleanup runs (EndOfGame, Remake, Terminated, etc.).
        Stops the stream if auto_stop is enabled.
        Runs asynchronously in a daemon thread.
        """
        if not self.enabled or not self.auto_stop:
            return
        threading.Thread(target=self.stop_stream, daemon=True, name="OBSGameEndWorker").start()


# Global singleton instance
obs_controller = OBSController()

