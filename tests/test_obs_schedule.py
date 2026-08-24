import unittest
from unittest.mock import MagicMock, patch
from datetime import datetime, time
from core.obs_controller import OBSController


class TestOBSSchedule(unittest.TestCase):
    def setUp(self):
        self.controller = OBSController()
        self.controller.enabled = True
        self.controller.schedule_enabled = True
        self.controller.schedule_start_time = "10:00"
        self.controller.schedule_stop_time = "16:00"

    def test_is_current_time_in_range_standard(self):
        # Within window: 12:30
        with patch("core.obs_controller.datetime") as mock_dt:
            mock_dt.now.return_value.time.return_value = time(12, 30)
            mock_dt.strptime = datetime.strptime
            self.assertTrue(self.controller.is_current_time_in_range())

        # Outside window (before): 08:00
        with patch("core.obs_controller.datetime") as mock_dt:
            mock_dt.now.return_value.time.return_value = time(8, 0)
            mock_dt.strptime = datetime.strptime
            self.assertFalse(self.controller.is_current_time_in_range())

        # Outside window (after): 17:00
        with patch("core.obs_controller.datetime") as mock_dt:
            mock_dt.now.return_value.time.return_value = time(17, 0)
            mock_dt.strptime = datetime.strptime
            self.assertFalse(self.controller.is_current_time_in_range())

    def test_is_current_time_in_range_midnight_spanning(self):
        self.controller.schedule_start_time = "22:00"
        self.controller.schedule_stop_time = "04:00"

        # Inside (night): 23:30
        with patch("core.obs_controller.datetime") as mock_dt:
            mock_dt.now.return_value.time.return_value = time(23, 30)
            mock_dt.strptime = datetime.strptime
            self.assertTrue(self.controller.is_current_time_in_range())

        # Inside (morning): 02:30
        with patch("core.obs_controller.datetime") as mock_dt:
            mock_dt.now.return_value.time.return_value = time(2, 30)
            mock_dt.strptime = datetime.strptime
            self.assertTrue(self.controller.is_current_time_in_range())

        # Outside: 15:00
        with patch("core.obs_controller.datetime") as mock_dt:
            mock_dt.now.return_value.time.return_value = time(15, 0)
            mock_dt.strptime = datetime.strptime
            self.assertFalse(self.controller.is_current_time_in_range())

    def test_apply_scene_and_start_concurrency_guard(self):
        self.controller._is_starting = True
        with patch.object(self.controller, "get_stream_status") as mock_status:
            self.controller._apply_scene_and_start()
            mock_status.assert_not_called()
        self.assertTrue(self.controller._is_starting)

    @patch("core.obs_controller.threading.Thread")
    def test_schedule_loop_in_range_starts_stream(self, mock_thread):
        # Configure in range and inactive stream
        self.controller.cached_status = {"active": False, "connected": True}
        self.controller._last_start_attempt = 0.0

        # Terminate loop after first wait
        self.controller._stop_scheduler_event.wait = MagicMock(side_effect=lambda timeout=None: self.controller._stop_scheduler_event.set())

        with patch.object(self.controller, "is_current_time_in_range", return_value=True):
            self.controller._schedule_loop()

            # Should have launched thread for _apply_scene_and_start
            mock_thread.assert_called()
            call_kwargs = mock_thread.call_args.kwargs
            self.assertEqual(call_kwargs.get("name"), "OBSScheduledStartWorker")
            self.assertEqual(call_kwargs.get("target"), self.controller._apply_scene_and_start)

    @patch("core.obs_controller.threading.Thread")
    def test_schedule_loop_in_range_already_active_does_not_start(self, mock_thread):
        # Configure in range and already active stream
        self.controller.cached_status = {"active": True, "connected": True}
        self.controller._stop_scheduler_event.wait = MagicMock(side_effect=lambda timeout=None: self.controller._stop_scheduler_event.set())

        with patch.object(self.controller, "is_current_time_in_range", return_value=True):
            self.controller._schedule_loop()

            # No start thread should be spawned
            for call in mock_thread.call_args_list:
                self.assertNotEqual(call.kwargs.get("name"), "OBSScheduledStartWorker")

    @patch("core.obs_controller.threading.Thread")
    def test_schedule_loop_outside_range_stops_stream(self, mock_thread):
        # Configure outside range and active stream
        self.controller.cached_status = {"active": True, "connected": True}
        self.controller._stop_scheduler_event.wait = MagicMock(side_effect=lambda timeout=None: self.controller._stop_scheduler_event.set())

        with patch.object(self.controller, "is_current_time_in_range", return_value=False), \
             patch.object(self.controller, "is_game_in_progress", return_value=False):
            self.controller._schedule_loop()

            mock_thread.assert_called()
            call_kwargs = mock_thread.call_args.kwargs
            self.assertEqual(call_kwargs.get("name"), "OBSScheduledStopWorker")
            self.assertEqual(call_kwargs.get("target"), self.controller.stop_stream)

    @patch("core.obs_controller.threading.Thread")
    def test_schedule_loop_outside_range_game_in_progress_postpones_stop(self, mock_thread):
        # Configure outside range and active stream, but game in progress
        self.controller.cached_status = {"active": True, "connected": True}
        self.controller._stop_scheduler_event.wait = MagicMock(side_effect=lambda timeout=None: self.controller._stop_scheduler_event.set())

        with patch.object(self.controller, "is_current_time_in_range", return_value=False), \
             patch.object(self.controller, "is_game_in_progress", return_value=True):
            self.controller._schedule_loop()

            # Stop thread should NOT be called yet
            for call in mock_thread.call_args_list:
                self.assertNotEqual(call.kwargs.get("name"), "OBSScheduledStopWorker")
            
            # _pending_stop_after_game should be True
            self.assertTrue(self.controller._pending_stop_after_game)


if __name__ == "__main__":
    unittest.main()
