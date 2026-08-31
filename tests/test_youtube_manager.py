import os
import json
from unittest.mock import MagicMock, patch
from datetime import datetime
import pytest

from core.youtube_manager import YouTubeManager


def test_format_title():
    now_date = datetime.now().strftime("%d/%m/%Y")
    template = "EST vs INTZ - {date}"
    formatted = YouTubeManager.format_title(template)
    assert formatted == f"EST vs INTZ - {now_date}"

    custom = "Scrim Match #1"
    assert YouTubeManager.format_title(custom) == custom


def test_is_configured_and_authenticated(tmp_path):
    mgr = YouTubeManager()
    mgr.client_secret_file = str(tmp_path / "client_secret.json")
    mgr.token_file = str(tmp_path / "yt_token.json")

    assert not mgr.is_configured()
    assert not mgr.is_authenticated()

    # Create dummy secret file
    (tmp_path / "client_secret.json").write_text("{}", encoding="utf-8")
    assert mgr.is_configured()


def test_create_broadcast_default_unlisted(tmp_path):
    mgr = YouTubeManager()
    mgr.client_secret_file = str(tmp_path / "client_secret.json")
    mgr.token_file = str(tmp_path / "yt_token.json")

    mock_creds = MagicMock()
    mock_creds.valid = True
    mgr.credentials = mock_creds

    mock_yt = MagicMock()
    mgr.youtube = mock_yt

    mock_insert = MagicMock()
    mock_insert.execute.return_value = {"id": "mock_broadcast_123"}
    mock_yt.liveBroadcasts().insert.return_value = mock_insert

    mock_streams_list = MagicMock()
    mock_streams_list.execute.return_value = {"items": [{"id": "mock_stream_abc"}]}
    mock_yt.liveStreams().list.return_value = mock_streams_list

    mock_bind = MagicMock()
    mock_bind.execute.return_value = {}
    mock_yt.liveBroadcasts().bind.return_value = mock_bind

    bid, watch_url = mgr.create_broadcast("EST vs INTZ - {date}")

    assert bid == "mock_broadcast_123"
    assert watch_url == "https://www.youtube.com/watch?v=mock_broadcast_123"
    assert mgr.active_broadcast_id == "mock_broadcast_123"
    assert mgr.active_stream_url == watch_url

    # Check insert body status
    call_args = mock_yt.liveBroadcasts().insert.call_args
    assert call_args.kwargs["body"]["status"]["privacyStatus"] == "unlisted"


def test_create_broadcast_configurable_privacy(tmp_path):
    mgr = YouTubeManager()
    mgr.client_secret_file = str(tmp_path / "client_secret.json")
    mgr.token_file = str(tmp_path / "yt_token.json")

    mock_creds = MagicMock()
    mock_creds.valid = True
    mgr.credentials = mock_creds

    mock_yt = MagicMock()
    mgr.youtube = mock_yt

    mock_insert = MagicMock()
    mock_insert.execute.return_value = {"id": "mock_broadcast_123"}
    mock_yt.liveBroadcasts().insert.return_value = mock_insert

    mock_streams_list = MagicMock()
    mock_streams_list.execute.return_value = {"items": [{"id": "mock_stream_abc"}]}
    mock_yt.liveStreams().list.return_value = mock_streams_list

    mock_bind = MagicMock()
    mock_bind.execute.return_value = {}
    mock_yt.liveBroadcasts().bind.return_value = mock_bind

    # Public
    mgr.create_broadcast("EST vs INTZ - {date}", privacy="public")
    call_args = mock_yt.liveBroadcasts().insert.call_args
    assert call_args.kwargs["body"]["status"]["privacyStatus"] == "public"

    # Private
    mgr.create_broadcast("EST vs INTZ - {date}", privacy="private")
    call_args = mock_yt.liveBroadcasts().insert.call_args
    assert call_args.kwargs["body"]["status"]["privacyStatus"] == "private"

    # Invalid fallback
    mgr.create_broadcast("EST vs INTZ - {date}", privacy="unknown_status")
    call_args = mock_yt.liveBroadcasts().insert.call_args
    assert call_args.kwargs["body"]["status"]["privacyStatus"] == "unlisted"


def test_create_broadcast_async_with_privacy(tmp_path):
    mgr = YouTubeManager()
    with patch.object(mgr, "create_broadcast", return_value=("bid1", "https://youtube.com/watch?v=bid1")) as mock_cb:
        callback = MagicMock()
        mgr.create_broadcast_async("Title", privacy="private", on_success=callback)
        import time
        time.sleep(0.1)
        mock_cb.assert_called_with(title_template="Title", privacy="private")
        callback.assert_called_with("https://youtube.com/watch?v=bid1")


def test_transition_and_complete():
    mgr = YouTubeManager()
    mock_yt = MagicMock()
    mgr.youtube = mock_yt
    mgr.active_broadcast_id = "test_bid_456"

    mock_transition = MagicMock()
    mock_transition.execute.return_value = {}
    mock_yt.liveBroadcasts().transition.return_value = mock_transition

    # Test transition to live
    res_live = mgr.transition_to_live()
    assert res_live is True
    mock_yt.liveBroadcasts().transition.assert_called_with(
        broadcastStatus="live",
        id="test_bid_456",
        part="status"
    )

    # Test complete broadcast
    res_comp = mgr.complete_broadcast()
    assert res_comp is True
    mock_yt.liveBroadcasts().transition.assert_called_with(
        broadcastStatus="complete",
        id="test_bid_456",
        part="status"
    )
    assert mgr.active_broadcast_id is None


def test_fetch_channel_name_and_caching(tmp_path):
    mgr = YouTubeManager()
    mgr.channel_cache_file = str(tmp_path / "yt_channel.json")
    
    mock_yt = MagicMock()
    mgr.youtube = mock_yt
    
    mock_channels = MagicMock()
    mock_channels.execute.return_value = {
        "items": [
            {
                "snippet": {
                    "title": "Sterlink Esports",
                    "customUrl": "@sterlinkesports"
                }
            }
        ]
    }
    mock_yt.channels().list.return_value = mock_channels

    mgr._fetch_channel_name()

    assert mgr.channel_name == "Sterlink Esports"
    assert os.path.exists(mgr.channel_cache_file)
    with open(mgr.channel_cache_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert data.get("channel_name") == "Sterlink Esports"


def test_load_credentials_loads_cached_channel(tmp_path):
    mgr = YouTubeManager()
    cache_file = tmp_path / "yt_channel.json"
    token_file = tmp_path / "yt_token.json"
    token_file.write_text("{}", encoding="utf-8")
    cache_file.write_text('{"channel_name": "Cached Esports"}', encoding="utf-8")
    
    mgr.token_file = str(token_file)
    mgr.channel_cache_file = str(cache_file)

    mock_creds = MagicMock()
    mock_creds.expired = False
    mock_creds.valid = True

    with patch("core.youtube_manager.Credentials.from_authorized_user_file", return_value=mock_creds), \
         patch("core.youtube_manager.build") as mock_build:
        mgr._load_credentials()

    assert mgr.channel_name == "Cached Esports"


def test_logout_clears_channel_cache(tmp_path):
    mgr = YouTubeManager()
    cache_file = tmp_path / "yt_channel.json"
    token_file = tmp_path / "yt_token.json"
    cache_file.write_text('{"channel_name": "Test Channel"}', encoding="utf-8")
    token_file.write_text("{}", encoding="utf-8")

    mgr.channel_cache_file = str(cache_file)
    mgr.token_file = str(token_file)
    mgr.channel_name = "Test Channel"

    mgr.logout()

    assert mgr.channel_name is None
    assert not os.path.exists(mgr.channel_cache_file)
    assert not os.path.exists(mgr.token_file)


def test_configure_discord():
    mgr = YouTubeManager()
    mgr.configure_discord("https://discord.com/api/webhooks/test", enabled=True)
    assert mgr.discord_webhook_url == "https://discord.com/api/webhooks/test"
    assert mgr.discord_enabled is True

    mgr.configure_discord("  ", enabled=False)
    assert mgr.discord_webhook_url == ""
    assert mgr.discord_enabled is False


def test_create_broadcast_does_not_send_discord_notification(tmp_path):
    mgr = YouTubeManager()
    mgr.client_secret_file = str(tmp_path / "client_secret.json")
    mgr.token_file = str(tmp_path / "yt_token.json")
    mgr.configure_discord("https://discord.com/api/webhooks/test", enabled=True)

    mock_creds = MagicMock()
    mock_creds.valid = True
    mgr.credentials = mock_creds

    mock_yt = MagicMock()
    mgr.youtube = mock_yt

    mock_insert = MagicMock()
    mock_insert.execute.return_value = {"id": "mock_bid_123"}
    mock_yt.liveBroadcasts().insert.return_value = mock_insert

    mock_streams_list = MagicMock()
    mock_streams_list.execute.return_value = {"items": [{"id": "mock_stream_abc"}]}
    mock_yt.liveStreams().list.return_value = mock_streams_list

    mock_bind = MagicMock()
    mock_bind.execute.return_value = {}
    mock_yt.liveBroadcasts().bind.return_value = mock_bind

    with patch("core.youtube_manager.send_discord_notification_async") as mock_notify:
        bid, watch_url = mgr.create_broadcast("EST vs INTZ - {date}")
        assert bid == "mock_bid_123"
        mock_notify.assert_not_called()


def test_transition_to_live_triggers_discord_notification():
    mgr = YouTubeManager()
    mock_yt = MagicMock()
    mgr.youtube = mock_yt
    mgr.active_broadcast_id = "live_bid_789"
    mgr.active_stream_url = "https://www.youtube.com/watch?v=live_bid_789"
    mgr.active_stream_title = "EST vs INTZ - 27/08/2026"
    mgr.configure_discord("https://discord.com/api/webhooks/test", enabled=True)

    mock_transition = MagicMock()
    mock_transition.execute.return_value = {"status": {"lifeCycleStatus": "live"}}
    mock_yt.liveBroadcasts().transition.return_value = mock_transition

    with patch("core.youtube_manager.send_discord_notification_async") as mock_notify:
        res = mgr.transition_to_live()
        assert res is True
        mock_notify.assert_called_once_with(
            "https://discord.com/api/webhooks/test",
            "EST vs INTZ - 27/08/2026",
            "https://www.youtube.com/watch?v=live_bid_789"
        )

        # Calling transition_to_live again for the same broadcast should not re-send
        res_again = mgr.transition_to_live()
        assert res_again is True
        assert mock_notify.call_count == 1


def test_transition_to_live_already_live_status():
    mgr = YouTubeManager()
    mock_yt = MagicMock()
    mgr.youtube = mock_yt
    mgr.active_broadcast_id = "already_live_bid"
    mgr.active_stream_url = "https://www.youtube.com/watch?v=already_live_bid"
    mgr.active_stream_title = "EST vs INTZ - Live Match"
    mgr.configure_discord("https://discord.com/api/webhooks/test", enabled=True)

    mock_list = MagicMock()
    mock_list.execute.return_value = {
        "items": [{"status": {"lifeCycleStatus": "live"}}]
    }
    mock_yt.liveBroadcasts().list.return_value = mock_list

    with patch("core.youtube_manager.send_discord_notification_async") as mock_notify:
        res = mgr.transition_to_live()
        assert res is True
        mock_notify.assert_called_once_with(
            "https://discord.com/api/webhooks/test",
            "EST vs INTZ - Live Match",
            "https://www.youtube.com/watch?v=already_live_bid"
        )


def test_transition_to_live_discord_disabled():
    mgr = YouTubeManager()
    mock_yt = MagicMock()
    mgr.youtube = mock_yt
    mgr.active_broadcast_id = "bid_no_discord"
    mgr.configure_discord("https://discord.com/api/webhooks/test", enabled=False)

    mock_transition = MagicMock()
    mock_transition.execute.return_value = {"status": {"lifeCycleStatus": "live"}}
    mock_yt.liveBroadcasts().transition.return_value = mock_transition

    with patch("core.youtube_manager.send_discord_notification_async") as mock_notify:
        res = mgr.transition_to_live()
        assert res is True
        mock_notify.assert_not_called()


def test_logout_resets_discord_state():
    mgr = YouTubeManager()
    mgr.configure_discord("https://discord.com/api/webhooks/test", enabled=True)
    mgr._notified_broadcast_ids.add("bid123")

    mgr.logout()

    assert mgr.discord_webhook_url is None
    assert mgr.discord_enabled is False
    assert len(mgr._notified_broadcast_ids) == 0


def test_youtube_manager_configure():
    mgr = YouTubeManager()
    mgr.configure({
        "yt_enabled": True,
        "yt_stream_title": "Custom Title - {date}",
        "yt_privacy": "private",
        "discord_webhook_url": "https://discord.com/webhook",
        "discord_enabled": True
    })
    assert mgr.enabled is True
    assert mgr.stream_title_template == "Custom Title - {date}"
    assert mgr.privacy == "private"
    assert mgr.discord_webhook_url == "https://discord.com/webhook"
    assert mgr.discord_enabled is True


def test_set_url_callback_dispatches_updates():
    mgr = YouTubeManager()
    urls_received = []

    def callback(url):
        urls_received.append(url)

    mgr.set_url_callback(callback)
    mgr._notify_url_changed("https://www.youtube.com/watch?v=123")
    assert urls_received == ["https://www.youtube.com/watch?v=123"]


def test_find_active_broadcast_success():
    mgr = YouTubeManager()
    mock_creds = MagicMock()
    mock_creds.valid = True
    mgr.credentials = mock_creds

    mock_yt = MagicMock()
    mgr.youtube = mock_yt

    mock_list = MagicMock()
    mock_list.execute.return_value = {
        "items": [
            {
                "id": "existing_active_bid",
                "snippet": {"title": "Active Live Broadcast"}
            }
        ]
    }
    mock_yt.liveBroadcasts().list.return_value = mock_list

    res = mgr.find_active_broadcast()
    assert res == ("existing_active_bid", "https://www.youtube.com/watch?v=existing_active_bid")
    assert mgr.active_broadcast_id == "existing_active_bid"
    assert mgr.active_stream_url == "https://www.youtube.com/watch?v=existing_active_bid"
    assert mgr.active_stream_title == "Active Live Broadcast"


def test_on_stream_start_creates_broadcast_when_enabled():
    mgr = YouTubeManager()
    mgr.enabled = True
    mgr.stream_title_template = "Match - {date}"
    mgr.privacy = "unlisted"

    with patch.object(mgr, "is_authenticated", return_value=True), \
         patch.object(mgr, "find_active_broadcast", return_value=None), \
         patch.object(mgr, "create_broadcast", return_value=("new_bid", "https://www.youtube.com/watch?v=new_bid")) as mock_create, \
         patch.object(mgr, "transition_to_live_async") as mock_trans:
        
        callback_urls = []
        mgr.set_url_callback(lambda url: callback_urls.append(url))

        mgr.on_stream_start()

        mock_create.assert_called_once_with(title_template="Match - {date}", privacy="unlisted")
        mock_trans.assert_called_once_with("new_bid")
        assert callback_urls == ["https://www.youtube.com/watch?v=new_bid"]


def test_on_stream_start_discovers_active_broadcast():
    mgr = YouTubeManager()
    mgr.enabled = False

    with patch.object(mgr, "is_authenticated", return_value=True), \
         patch.object(mgr, "find_active_broadcast", return_value=("found_bid", "https://www.youtube.com/watch?v=found_bid")), \
         patch.object(mgr, "create_broadcast") as mock_create, \
         patch.object(mgr, "transition_to_live_async") as mock_trans:
        
        mgr.on_stream_start()

        mock_create.assert_not_called()
        mock_trans.assert_called_once_with("found_bid")


def test_on_stream_start_not_authenticated():
    mgr = YouTubeManager()
    with patch.object(mgr, "is_authenticated", return_value=False), \
         patch.object(mgr, "authenticate", return_value=False), \
         patch.object(mgr, "create_broadcast") as mock_create:
        mgr.on_stream_start()
        mock_create.assert_not_called()


def test_load_credentials_without_client_secret_file(tmp_path):
    mgr = YouTubeManager()
    mgr.client_secret_file = str(tmp_path / "client_secret.json")
    mgr.token_file = str(tmp_path / "yt_token.json")
    mgr.channel_cache_file = str(tmp_path / "yt_channel.json")

    # Create token file but NO client_secret.json
    (tmp_path / "yt_token.json").write_text('{"token": "xyz", "refresh_token": "abc"}', encoding="utf-8")
    (tmp_path / "yt_channel.json").write_text('{"channel_name": "Persisted Channel"}', encoding="utf-8")

    mock_creds = MagicMock()
    mock_creds.expired = False
    mock_creds.valid = True

    with patch("core.youtube_manager.Credentials.from_authorized_user_file", return_value=mock_creds), \
         patch("core.youtube_manager.build") as mock_build:
        mgr._load_credentials()

    assert mgr.credentials is mock_creds
    assert mgr.channel_name == "Persisted Channel"
    assert mgr.is_authenticated() is True


def test_authenticate_non_interactive_without_client_secret(tmp_path):
    mgr = YouTubeManager()
    mgr.client_secret_file = str(tmp_path / "client_secret.json")
    mgr.token_file = str(tmp_path / "yt_token.json")
    mgr.channel_cache_file = str(tmp_path / "yt_channel.json")

    # Create token file but NO client_secret.json
    (tmp_path / "yt_token.json").write_text('{"token": "xyz"}', encoding="utf-8")
    (tmp_path / "yt_channel.json").write_text('{"channel_name": "Sterlink"}', encoding="utf-8")

    mock_creds = MagicMock()
    mock_creds.expired = False
    mock_creds.valid = True

    with patch("core.youtube_manager.Credentials.from_authorized_user_file", return_value=mock_creds), \
         patch("core.youtube_manager.build"):
        success = mgr.authenticate(force_interactive=False)

    assert success is True
    assert mgr.channel_name == "Sterlink"
    assert mgr.is_authenticated() is True


def test_load_credentials_preserves_valid_creds_on_build_or_fetch_error(tmp_path):
    mgr = YouTubeManager()
    mgr.client_secret_file = str(tmp_path / "client_secret.json")
    mgr.token_file = str(tmp_path / "yt_token.json")
    mgr.channel_cache_file = str(tmp_path / "yt_channel.json")

    (tmp_path / "yt_token.json").write_text('{"token": "xyz"}', encoding="utf-8")
    (tmp_path / "yt_channel.json").write_text('{"channel_name": "Cached Channel"}', encoding="utf-8")

    mock_creds = MagicMock()
    mock_creds.expired = False
    mock_creds.valid = True

    # Simulate network failure or googleapiclient build error on startup
    with patch("core.youtube_manager.Credentials.from_authorized_user_file", return_value=mock_creds), \
         patch("core.youtube_manager.build", side_effect=RuntimeError("Discovery cache failed")):
        mgr._load_credentials()

    # Credentials and cached channel name must NOT be wiped
    assert mgr.credentials is mock_creds
    assert mgr.channel_name == "Cached Channel"
    assert mgr.is_authenticated() is True


def test_discover_client_secret_from_alternate_locations(tmp_path):
    mgr = YouTubeManager()
    appdata_secret = tmp_path / "appdata" / "client_secret.json"
    alt_secret = tmp_path / "bin" / "client_secret.json"
    alt_secret.parent.mkdir(parents=True)
    alt_secret.write_text('{"installed": {"client_id": "123"}}', encoding="utf-8")

    mgr.client_secret_file = str(appdata_secret)

    with patch.object(mgr, "_candidate_secret_paths", return_value=[str(appdata_secret), str(alt_secret)]):
        found_path = mgr.get_client_secret_path()
        assert found_path == str(appdata_secret)
        # Should auto-migrate / copy to AppData
        assert os.path.exists(str(appdata_secret))
        assert json.loads(appdata_secret.read_text(encoding="utf-8")) == {"installed": {"client_id": "123"}}


def test_discover_token_from_alternate_locations(tmp_path):
    mgr = YouTubeManager()
    appdata_token = tmp_path / "appdata" / "yt_token.json"
    alt_token = tmp_path / "bin" / "yt_token.json"
    alt_token.parent.mkdir(parents=True)
    alt_token.write_text('{"token": "persisted_token"}', encoding="utf-8")

    mgr.token_file = str(appdata_token)

    with patch.object(mgr, "_candidate_token_paths", return_value=[str(appdata_token), str(alt_token)]):
        found_token = mgr.get_token_path()
        assert found_token == str(appdata_token)
        # Should auto-migrate / copy to AppData
        assert os.path.exists(str(appdata_token))
        assert json.loads(appdata_token.read_text(encoding="utf-8")) == {"token": "persisted_token"}





