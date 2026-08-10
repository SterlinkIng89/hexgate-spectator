import time
import requests
import logging
import pydirectinput
import threading
import urllib3

# Suppress self-signed certificate warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger(__name__)

def wait_for_game_and_setup_camera(delay=3.0):
    """
    Connects to the game's Live Client Data API (port 2999).
    Waits for the game to start (time > 0) and executes the camera macro.
    """
    logger.info("Waiting for the game process to fully load (Loading Screen)...")
    
    url = "https://127.0.0.1:2999/liveclientdata/gamestats"
    game_started = False
    
    # Try for up to 10 minutes (600 iterations of 1 second)
    for _ in range(600):
        try:
            res = requests.get(url, verify=False, timeout=2)
            if res.status_code == 200:
                data = res.json()
                game_time = data.get("gameTime", 0)
                
                if game_time > 1.0:
                    logger.info(f"Game start detected (Time: {game_time}s). Setting up camera...")
                    game_started = True
                    break
        except requests.exceptions.RequestException:
            # Game is not ready yet or loading screen hasn't started
            pass
            
        time.sleep(1)
        
    if not game_started:
        logger.warning("Game start not detected within the time limit.")
        return

    # Wait for the configured delay
    logger.info(f"Waiting {delay} seconds (Configured Delay)...")
    time.sleep(delay)
    
    try:
        logger.info("Sending keyboard shortcuts (Shift + Z)...")
        # pydirectinput handles DirectX games better
        pydirectinput.keyDown('shift')
        pydirectinput.press('z')
        pydirectinput.keyUp('shift')
        
        time.sleep(0.5)
        
        logger.info("Zooming out (Scroll backward)...")
        # Scroll backward 3 times
        for _ in range(3):
            pydirectinput.scroll(-1000)
            time.sleep(0.2)
            
        logger.info("Camera setup completed.")
    except Exception as e:
        logger.error(f"Error sending keyboard commands: {e}")

def trigger_camera_automation(delay=3.0):
    """
    Launches the automation process in a separate thread to avoid blocking the async Event Loop.
    """
    threading.Thread(target=wait_for_game_and_setup_camera, args=(delay,), daemon=True).start()

if __name__ == "__main__":
    # Isolated manual test if run directly
    logging.basicConfig(level=logging.INFO)
    wait_for_game_and_setup_camera()
