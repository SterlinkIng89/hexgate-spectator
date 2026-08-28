import logging
import threading
import time
from datetime import datetime, timedelta
from core.youtube_manager import youtube_manager
from core.power import shutdown_system

# Silence third-party traceback dumps when OBS is offline
def silence_external_loggers():
    """Suppresses verbose internal tracebacks from third-party libraries (obsws-python, websocket)."""
    for name in ("obsws_python", "obsws_python.baseclient", "obsws_python.reqs", "websocket"):
        logging.getLogger(name).setLevel(logging.CRITICAL)

silence_external_loggers()

def _is_obs_unreachable_error(e: Exception) -> bool:
    """Returns True if the exception indicates OBS is closed, refusing connections, or unreachable."""
    err_msg = str(e).lower()
    return (
        isinstance(e, (ConnectionRefusedError, TimeoutError, ConnectionError, OSError))
        or "10061" in err_msg
        or "10054" in err_msg
        or "10053" in err_msg
        or "refused" in err_msg
        or "timed out" in err_msg
        or "closed" in err_msg
        or "not connected" in err_msg
        or "broken pipe" in err_msg
        or "connection reset" in err_msg
        or "connection abort" in err_msg
    )

logger = logging.getLogger(__name__)

class OBSController:
    """
    Thread-safe controller for OBS Studio via obs-websocket v5 protocol (obsws-python).
    Handles connecting, streaming control, scene/profile/collection switching,
    and graceful error recovery when OBS is offline.
    """
    RECONNECT_COOLDOWN = 10.0  # Minimum seconds between connection retries when OBS is offline
    START_RETRY_COOLDOWN = 10.0  # Minimum seconds between scheduled stream start retries

    def __init__(self):
        self._client = None
        self._lock = threading.RLock()
        self.host = "localhost"
        self.port = 4455
        self.password = ""
        self.enabled = False
        self.profile = ""
        self.scene_collection = ""
        self.auto_start = True
        self.auto_stop = True
        self.schedule_enabled = True
        self.schedule_start_time = "10:00"
        self.schedule_stop_time = "16:00"
        self.shutdown_enabled = False
        self.shutdown_delay = 60
        self._pending_stop_after_game = False
        self._scheduler_thread = None
        self._stop_scheduler_event = threading.Event()
        self._last_connect_attempt = 0.0
        self._last_start_attempt = 0.0
        self._is_starting = False
        self.stream_started_at = None
        self.stream_stopped_at = None
        self.cached_status = {"active": False, "timecode": "", "reconnecting": False, "connected": False}

    def configure(self, config_dict: dict):
        """Updates connection parameters and preferences from dictionary."""
        with self._lock:
            self.enabled = bool(config_dict.get("obs_enabled", False))
            self.host = config_dict.get("obs_host", "localhost") or "localhost"
            try:
                port_val = config_dict.get("obs_port", 4455)
                self.port = int(port_val) if port_val else 4455
            except (ValueError, TypeError):
                self.port = 4455
            self.password = config_dict.get("obs_password", "") or ""
            self.profile = config_dict.get("obs_profile", "").strip()
            self.scene_collection = config_dict.get("obs_scene_collection", "").strip()
            self.auto_start = bool(config_dict.get("obs_auto_start", True))
            self.auto_stop = bool(config_dict.get("obs_auto_stop", True))
            self.schedule_enabled = bool(config_dict.get("obs_schedule_enabled", True))
            self.schedule_start_time = config_dict.get("obs_schedule_start_time", "10:00").strip() or "10:00"
            self.schedule_stop_time = config_dict.get("obs_schedule_stop_time", "16:00").strip() or "16:00"
            self.shutdown_enabled = bool(
                config_dict.get("obs_shutdown_enabled", False) or config_dict.get("shutdown_enabled", False)
            )
            try:
                delay_val = config_dict.get("obs_shutdown_delay", config_dict.get("shutdown_delay", 60))
                self.shutdown_delay = max(0, int(delay_val)) if delay_val is not None else 60
            except (ValueError, TypeError):
                self.shutdown_delay = 60

    @property
    def is_connected(self) -> bool:
        with self._lock:
            return self._client is not None

    def health_check(self) -> bool:
        """Verifies whether the current OBS client connection is responsive."""
        with self._lock:
            if self._client is None:
                return False
            try:
                self._client.get_version()
                return True
            except Exception:
                return False

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
                silence_external_loggers()

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
                if _is_obs_unreachable_error(e):
                    logger.warning(
                        f"[OBS] OBS Studio is not open or unreachable at {self.host}:{self.port} ({elapsed_ms:.1f}ms). "
                        f"Please ensure OBS is running with WebSocket server enabled."
                    )
                else:
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

    def _ensure_connected(self, check_health: bool = True) -> bool:
        """
        Ensures active connection to OBS WebSocket server.
        If check_health is True and a client exists, pings OBS via get_version()
        to detect stale/closed sockets, reconnecting immediately if unhealthy.
        """
        with self._lock:
            if self._client is None:
                return self.connect()

            if check_health:
                try:
                    self._client.get_version()
                    return True
                except Exception as e:
                    logger.warning(f"[OBS] Stale or dead connection detected ({e}). Reconnecting...")
                    self.disconnect()
                    return self.connect(force=True)

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
                if _is_obs_unreachable_error(e):
                    self.disconnect()
                return False

    def _mark_stream_started(self):
        """Thread-safe helper to record stream start timestamp and update cache atomically."""
        if not self.stream_started_at:
            self.stream_started_at = datetime.now()
        self.cached_status = {**self.cached_status, "active": True}

    def _mark_stream_stopped(self):
        """Thread-safe helper to record stream stop timestamp and update cache atomically."""
        self.stream_stopped_at = datetime.now()
        self.stream_started_at = None
        self.cached_status = {**self.cached_status, "active": False}

    def get_stream_status(self) -> dict:
        """Returns dictionary with current stream state and updates cached status."""
        with self._lock:
            if not self._ensure_connected(check_health=False):
                res = {"active": False, "timecode": "", "reconnecting": False, "connected": False}
                self.cached_status = res
                return res
            t0 = time.perf_counter()
            try:
                status = self._client.get_stream_status()
                elapsed_ms = (time.perf_counter() - t0) * 1000
                logger.debug(f"[OBS] get_stream_status completed in {elapsed_ms:.1f}ms")
                is_active = getattr(status, "output_active", False)
                is_reconnecting = getattr(status, "output_reconnecting", False)
                timecode = getattr(status, "output_timecode", "")
                
                if is_active:
                    was_reconnecting = self.cached_status.get("reconnecting", False)
                    if is_reconnecting and not was_reconnecting:
                        logger.warning(f"[OBS] Stream is active but entered RECONNECTING state! Timecode: {timecode}")
                    elif not is_reconnecting and was_reconnecting:
                        logger.info(f"[OBS] Stream reconnected successfully. Timecode: {timecode}")
                    elif self.cached_status.get("timecode") != timecode and timecode:
                        logger.debug(f"[OBS] Stream active. Timecode: {timecode}")

                res = {
                    "active": is_active,
                    "timecode": timecode,
                    "reconnecting": is_reconnecting,
                    "connected": True
                }
                if is_active:
                    self._mark_stream_started()
                elif self.cached_status.get("active", False):
                    self._mark_stream_stopped()
                self.cached_status = res
                return res
            except Exception as e:
                elapsed_ms = (time.perf_counter() - t0) * 1000
                logger.warning(f"[OBS] Error checking stream status ({elapsed_ms:.1f}ms): {e}")
                self.disconnect()
                res = {"active": False, "timecode": "", "reconnecting": False, "connected": False}
                self.cached_status = res
                return res

    def get_profiles(self) -> list[str]:
        """Fetches list of available OBS Profiles."""
        with self._lock:
            if not self._ensure_connected():
                return []
            t0 = time.perf_counter()
            try:
                res = self._client.get_profile_list()
                elapsed_ms = (time.perf_counter() - t0) * 1000
                logger.debug(f"[OBS] get_profile_list completed in {elapsed_ms:.1f}ms")
                return list(getattr(res, "profiles", []) or [])
            except Exception as e:
                elapsed_ms = (time.perf_counter() - t0) * 1000
                logger.warning(f"[OBS] Error fetching profiles ({elapsed_ms:.1f}ms): {e}")
                if _is_obs_unreachable_error(e):
                    self.disconnect()
                return []

    def get_scene_collections(self) -> list[str]:
        """Fetches list of available OBS Scene Collections."""
        with self._lock:
            if not self._ensure_connected():
                return []
            t0 = time.perf_counter()
            try:
                res = self._client.get_scene_collection_list()
                elapsed_ms = (time.perf_counter() - t0) * 1000
                logger.debug(f"[OBS] get_scene_collection_list completed in {elapsed_ms:.1f}ms")
                return list(getattr(res, "scene_collections", []) or [])
            except Exception as e:
                elapsed_ms = (time.perf_counter() - t0) * 1000
                logger.warning(f"[OBS] Error fetching scene collections ({elapsed_ms:.1f}ms): {e}")
                if _is_obs_unreachable_error(e):
                    self.disconnect()
                return []

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
                self._mark_stream_started()
                youtube_manager.transition_to_live_async()
                return True
            except Exception as e:
                elapsed_ms = (time.perf_counter() - t0) * 1000
                err_str = str(e).lower()
                if "already active" in err_str or "output_running" in err_str or "code 500" in err_str:
                    logger.info(f"[OBS] Stream is already active ({elapsed_ms:.1f}ms).")
                    self._mark_stream_started()
                    youtube_manager.transition_to_live_async()
                    return True
                logger.error(f"[OBS] Failed to start stream ({elapsed_ms:.1f}ms): {e}")
                if _is_obs_unreachable_error(e):
                    self.disconnect()
                return False

    def _handle_shutdown_on_stream_end(self):
        """Triggers YouTube broadcast completion and system shutdown if enabled."""
        youtube_manager.complete_broadcast_async()
        if self.shutdown_enabled:
            logger.warning(
                f"[OBS] Stream ended and PC auto-shutdown is enabled. "
                f"Shutting down in {self.shutdown_delay} seconds..."
            )
            shutdown_system(delay_seconds=self.shutdown_delay, reason="Hexgate Spectator stream ended")

    def stop_stream(self, trigger_shutdown: bool = True) -> bool:
        """Stops streaming in OBS directly without redundant pre-flight query."""
        if not self.enabled:
            return False
        with self._lock:
            self._pending_stop_after_game = False
            if not self._ensure_connected():
                return False
            t0 = time.perf_counter()
            try:
                logger.info("[OBS] Stopping stream...")
                self._client.stop_stream()
                elapsed_ms = (time.perf_counter() - t0) * 1000
                logger.info(f"[OBS] Stream stopped successfully in {elapsed_ms:.1f}ms.")
                self._mark_stream_stopped()
                if trigger_shutdown:
                    self._handle_shutdown_on_stream_end()
                return True
            except Exception as e:
                elapsed_ms = (time.perf_counter() - t0) * 1000
                err_str = str(e).lower()
                if "not active" in err_str or "output_not_running" in err_str or "code 501" in err_str:
                    logger.info(f"[OBS] Stream is already stopped ({elapsed_ms:.1f}ms).")
                    self._mark_stream_stopped()
                    if trigger_shutdown:
                        self._handle_shutdown_on_stream_end()
                    return True
                logger.error(f"[OBS] Failed to stop stream ({elapsed_ms:.1f}ms): {e}")
                if _is_obs_unreachable_error(e):
                    self.disconnect()
                return False

    def is_game_in_progress(self) -> bool:
        """Returns True if the spectator bot is actively in an InProgress match."""
        try:
            from core.hexgate.state import bot_state
            return bool(bot_state.bot_active and bot_state.current_phase == "InProgress")
        except Exception:
            return False

    def _apply_scene_and_start(self):
        """
        Applies configured profile, scene collection, and scene before starting stream.
        Guarded against concurrent duplicate executions.
        """
        with self._lock:
            if self._is_starting:
                logger.debug("[OBS] _apply_scene_and_start already in progress. Skipping.")
                return
            self._is_starting = True

        t0 = time.perf_counter()
        try:
            status = self.get_stream_status()
            is_active = status.get("active", False)

            if not is_active:
                if self.profile:
                    self.set_profile(self.profile)
                if self.scene_collection:
                    self.set_scene_collection(self.scene_collection)
                self.start_stream()
            else:
                logger.info("[OBS] Stream is already active. Skipping start_stream.")
                
            elapsed_ms = (time.perf_counter() - t0) * 1000
            logger.info(f"[OBS] _apply_scene_and_start completed in {elapsed_ms:.1f}ms")
        finally:
            with self._lock:
                self._is_starting = False

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
        """Background loop that evaluates schedule window state and manages stream lifecycle."""
        logger.info(
            f"[OBS Schedule] Scheduler active "
            f"(Start: {self.schedule_start_time or 'Any'}, "
            f"Stop: {self.schedule_stop_time or 'Any'})."
        )
        while not self._stop_scheduler_event.is_set():
            try:
                if self.enabled:
                    if self._client is not None:
                        self.get_stream_status()

                    if self.schedule_enabled and self.schedule_start_time and self.schedule_stop_time:
                        in_range = self.is_current_time_in_range()
                        is_active = self.cached_status.get("active", False)
                        now_ts = time.time()

                        if in_range:
                            self._pending_stop_after_game = False
                            if not is_active and not self._is_starting:
                                if (now_ts - self._last_start_attempt) >= self.START_RETRY_COOLDOWN:
                                    self._last_start_attempt = now_ts
                                    logger.info(
                                        f"[OBS Schedule] In active schedule window "
                                        f"({self.schedule_start_time} - {self.schedule_stop_time}) "
                                        f"and stream is inactive. Starting stream..."
                                    )
                                    threading.Thread(
                                        target=self._apply_scene_and_start,
                                        daemon=True,
                                        name="OBSScheduledStartWorker"
                                    ).start()
                        else:
                            if self.is_game_in_progress():
                                if is_active and not self._pending_stop_after_game:
                                    self._pending_stop_after_game = True
                                    logger.info(
                                        f"[OBS Schedule] Outside scheduled window "
                                        f"({self.schedule_start_time} - {self.schedule_stop_time}), "
                                        f"but a game is currently in progress. Postponing stream stop until match finishes."
                                    )
                            elif is_active or self._pending_stop_after_game:
                                logger.info(
                                    f"[OBS Schedule] Outside scheduled window "
                                    f"({self.schedule_start_time} - {self.schedule_stop_time}). Stopping stream..."
                                )
                                self._pending_stop_after_game = False
                                threading.Thread(
                                    target=self.stop_stream,
                                    daemon=True,
                                    name="OBSScheduledStopWorker"
                                ).start()

            except Exception as e:
                logger.warning(f"[OBS Schedule] Loop error: {e}")

            self._stop_scheduler_event.wait(timeout=2)

        logger.info("[OBS Schedule] Scheduler thread stopped.")

    def stop_scheduler(self):
        """Stops the background schedule monitor loop cleanly."""
        self._stop_scheduler_event.set()
        self._pending_stop_after_game = False

    def get_status_summary(self, is_bot_running: bool = False) -> dict:
        """Returns thread-safe formatted status summary for the GUI header indicator."""
        with self._lock:
            if not self.enabled:
                return {
                    "state": "Disabled",
                    "color": "#7f8c8d",
                    "label": "Stream: Disabled",
                    "detail": "OBS integration disabled in settings",
                }

            is_active = self.cached_status.get("active", False)
            timecode = self.cached_status.get("timecode", "")

            # If stream is actively transmitting
            if is_active:
                start_str = self.stream_started_at.strftime("%I:%M %p") if self.stream_started_at else ""
                duration_str = timecode
                if not duration_str and self.stream_started_at:
                    elapsed = int((datetime.now() - self.stream_started_at).total_seconds())
                    h, rem = divmod(elapsed, 3600)
                    m, s = divmod(rem, 60)
                    duration_str = f"{h:02d}:{m:02d}:{s:02d}"

                detail = f"Live: {duration_str}" if duration_str else "Live streaming in progress"
                if self._pending_stop_after_game:
                    detail += " • Stopping after match"
                elif start_str:
                    detail += f" (Started at {start_str})"

                return {
                    "state": "Live",
                    "color": "#2ecc71",
                    "label": "Stream: Live",
                    "detail": detail,
                }

            # If schedule is enabled
            if self.schedule_enabled and self.schedule_start_time:
                now_dt = datetime.now()
                try:
                    start_t = datetime.strptime(self.schedule_start_time, "%H:%M").time()
                    stop_t = datetime.strptime(self.schedule_stop_time, "%H:%M").time() if self.schedule_stop_time else None
                    start_12h = start_t.strftime("%I:%M %p")
                    stop_12h = stop_t.strftime("%I:%M %p") if stop_t else "Open"

                    # Check if inside window
                    if self.is_current_time_in_range():
                        detail = f"Active window ({start_12h} - {stop_12h})"
                        if is_bot_running and self.auto_start:
                            detail += " • Waiting for match"
                        return {
                            "state": "Standby",
                            "color": "#3498db",
                            "label": "Stream: In Window",
                            "detail": detail,
                        }

                    # Outside window: compute countdown to start
                    target = now_dt.replace(hour=start_t.hour, minute=start_t.minute, second=0, microsecond=0)
                    if target <= now_dt:
                        target += timedelta(days=1)
                    delta = target - now_dt
                    h, rem = divmod(int(delta.total_seconds()), 3600)
                    m, s = divmod(rem, 60)
                    
                    return {
                        "state": "Scheduled",
                        "color": "#f1c40f",
                        "label": "Stream: Scheduled",
                        "detail": f"Starts in {h:02d}h {m:02d}m {s:02d}s (Window: {start_12h} - {stop_12h})",
                    }
                except Exception as e:
                    logger.debug(f"Error calculating schedule summary: {e}")

            # If bot is running without schedule
            if is_bot_running:
                if self.auto_start:
                    return {
                        "state": "Standby",
                        "color": "#3498db",
                        "label": "Stream: Standby",
                        "detail": "Auto-starts when game begins",
                    }
                else:
                    return {
                        "state": "Offline",
                        "color": "#7f8c8d",
                        "label": "Stream: Offline",
                        "detail": "Auto-start disabled",
                    }

            # Bot not running, not streaming
            if self.stream_stopped_at:
                stopped_str = self.stream_stopped_at.strftime("%I:%M %p")
                return {
                    "state": "Stopped",
                    "color": "#e74c3c",
                    "label": "Stream: Stopped",
                    "detail": f"Last stream stopped at {stopped_str}",
                }

            return {
                "state": "Ready",
                "color": "#7f8c8d",
                "label": "Stream: Ready",
                "detail": "Start bot to begin monitoring",
            }

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
        if self.schedule_enabled and self.is_current_time_in_range() and not self._pending_stop_after_game:
            logger.info("[OBS] Skipping auto-stop on game end because schedule window is active.")
            return
        self._pending_stop_after_game = False
        threading.Thread(target=self.stop_stream, daemon=True, name="OBSGameEndWorker").start()

    def on_bot_stop(self):
        """
        Triggered when the spectator bot is stopped by the user.
        Stops the scheduler, terminates the stream if outside schedule window,
        and disconnects from OBS WebSocket cleanly.
        """
        self.stop_scheduler()
        if self.enabled:
            if self.schedule_enabled and self.is_current_time_in_range():
                logger.info("[OBS] Bot stopped, but leaving stream active due to schedule window.")
            else:
                self.stop_stream(trigger_shutdown=False)
            self.disconnect()


# Global singleton instance
obs_controller = OBSController()


