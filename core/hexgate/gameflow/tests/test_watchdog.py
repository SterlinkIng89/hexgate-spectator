import pytest
import time
from unittest.mock import AsyncMock, patch
from core.hexgate.gameflow import watchdog
from core.hexgate.config import GAME_FREEZE_TIMEOUT

@pytest.fixture
def setup_watchdog():
    watchdog.reset()
    yield
    watchdog.reset()

@pytest.mark.asyncio
async def test_watchdog_does_not_cleanup_on_long_pause(setup_watchdog, mocker):
    """
    Test that the spectator watchdog does not force cleanup when the game is paused
    (game time stopped advancing) for longer than GAME_FREEZE_TIMEOUT.
    """
    mock_cleanup = AsyncMock()
    mock_connection = AsyncMock()
    
    # Mock time.time to control the simulated time
    mock_time = mocker.patch("core.hexgate.gameflow.watchdog.time.time")
    
    # Mock the live client API
    mock_get_time = mocker.patch("core.hexgate.client.live_client_api.get_current_game_time", new_callable=AsyncMock)
    mock_get_players = mocker.patch("core.hexgate.client.live_client_api.get_current_all_players", new_callable=AsyncMock)
    
    mock_get_players.return_value = [{"summonerName": "Player1", "championName": "Annie"}]
    
    # Tick 1: Game running at time 100.0, gameTime 10.0
    mock_time.return_value = 100.0
    mock_get_time.return_value = 10.0
    await watchdog.check_game_freeze(mock_connection, mock_cleanup)
    
    assert watchdog._game_time_last_changed_at == 100.0
    
    # Tick 2: Game still at time 10.0, but real time advanced by GAME_FREEZE_TIMEOUT + 10s
    mock_time.return_value = 100.0 + GAME_FREEZE_TIMEOUT + 10.0
    mock_get_time.return_value = 10.0
    await watchdog.check_game_freeze(mock_connection, mock_cleanup)
    
    # Ensure cleanup is NOT called
    mock_cleanup.assert_not_called()
