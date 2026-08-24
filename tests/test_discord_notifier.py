import unittest
from unittest.mock import patch, MagicMock
from core.discord_notifier import send_discord_notification

class TestDiscordNotifier(unittest.TestCase):
    @patch('core.discord_notifier.requests.post')
    def test_send_discord_notification_success(self, mock_post):
        # Arrange
        mock_response = MagicMock()
        mock_response.status_code = 204
        mock_post.return_value = mock_response

        webhook_url = "https://discord.com/api/webhooks/123/abc"
        title = "Scrim vs INTZ - 23/08/2026"
        stream_url = "https://youtube.com/live/N6h7pfnvqCQ?feature=share"

        # Act
        result = send_discord_notification(webhook_url, title, stream_url)

        # Assert
        self.assertTrue(result)
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        self.assertEqual(args[0], webhook_url)
        
        expected_content = f"{title} - ||{stream_url}||"
        self.assertEqual(kwargs['json']['content'], expected_content)

    def test_send_discord_notification_empty_url(self):
        # Act
        result = send_discord_notification("", "EST vs INTZ - 23/08/2026", "https://youtube.com/live/xyz")

        # Assert
        self.assertFalse(result)

    @patch('core.discord_notifier.requests.post')
    def test_send_discord_notification_request_error(self, mock_post):
        # Arrange
        import requests
        mock_post.side_effect = requests.RequestException("Network Error")

        # Act
        result = send_discord_notification("https://discord.com/api/webhooks/123/abc", "EST vs INTZ - 23/08/2026", "https://youtube.com/live/xyz")

        # Assert
        self.assertFalse(result)

    @patch('core.discord_notifier.send_discord_notification')
    @patch('threading.Thread')
    def test_send_discord_notification_async(self, mock_thread_cls, mock_send):
        from core.discord_notifier import send_discord_notification_async
        mock_thread_instance = MagicMock()
        mock_thread_cls.return_value = mock_thread_instance

        webhook = "https://discord.com/api/webhooks/123/abc"
        title = "EST vs INTZ - 24/08/2026"
        url = "https://youtube.com/live/xyz"

        thread = send_discord_notification_async(webhook, title, url)

        mock_thread_cls.assert_called_once_with(
            target=mock_send,
            args=(webhook, title, url),
            daemon=True,
            name="DiscordNotifierWorker"
        )
        mock_thread_instance.start.assert_called_once()
        self.assertEqual(thread, mock_thread_instance)

if __name__ == '__main__':
    unittest.main()
