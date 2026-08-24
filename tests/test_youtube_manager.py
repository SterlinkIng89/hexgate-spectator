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


def test_create_broadcast(tmp_path):
    mgr = YouTubeManager()
    mgr.client_secret_file = str(tmp_path / "client_secret.json")
    mgr.token_file = str(tmp_path / "yt_token.json")

    # Mock valid credentials and YouTube client
    mock_creds = MagicMock()
    mock_creds.valid = True
    mgr.credentials = mock_creds

    mock_yt = MagicMock()
    mgr.youtube = mock_yt

    # Mock liveBroadcasts().insert().execute()
    mock_insert = MagicMock()
    mock_insert.execute.return_value = {"id": "mock_broadcast_123"}
    mock_yt.liveBroadcasts().insert.return_value = mock_insert

    # Mock liveStreams().list().execute()
    mock_streams_list = MagicMock()
    mock_streams_list.execute.return_value = {"items": [{"id": "mock_stream_abc"}]}
    mock_yt.liveStreams().list.return_value = mock_streams_list

    # Mock liveBroadcasts().bind().execute()
    mock_bind = MagicMock()
    mock_bind.execute.return_value = {}
    mock_yt.liveBroadcasts().bind.return_value = mock_bind

    bid, watch_url = mgr.create_broadcast("EST vs INTZ - {date}", privacy="public")

    assert bid == "mock_broadcast_123"
    assert watch_url == "https://www.youtube.com/watch?v=mock_broadcast_123"
    assert mgr.active_broadcast_id == "mock_broadcast_123"
    assert mgr.active_stream_url == watch_url


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

