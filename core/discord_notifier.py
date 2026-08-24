import logging
import threading
import requests

logger = logging.getLogger(__name__)


def send_discord_notification(webhook_url: str, stream_title: str, stream_url: str) -> bool:
    """
    Sends a formatted notification to a Discord webhook.
    Format: <Stream Title> - ||<Stream URL>||
    """
    if not webhook_url:
        return False

    content = f"{stream_title} - ||{stream_url}||"
    payload = {"content": content}

    try:
        response = requests.post(webhook_url, json=payload, timeout=10)
        response.raise_for_status()
        logger.info("[Discord] Notification sent successfully.")
        return True
    except requests.RequestException as e:
        logger.error(f"[Discord] Failed to post notification: {e}")
        return False


def send_discord_notification_async(webhook_url: str, stream_title: str, stream_url: str) -> threading.Thread:
    """
    Dispatches a Discord notification in a background daemon thread.
    """
    thread = threading.Thread(
        target=send_discord_notification,
        args=(webhook_url, stream_title, stream_url),
        daemon=True,
        name="DiscordNotifierWorker"
    )
    thread.start()
    return thread
