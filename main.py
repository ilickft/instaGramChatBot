"""
main.py — Entry point for AryaChatBot (Instagram Chat Bot with Groq).
"""

import asyncio
import logging
import sys

from modules.groq_handler import GroqHandler
from modules.instagram_client import InstagramClient
from modules.vlc_player import VLCPlayer
from modules.music_handler import MusicHandler
from modules.relay_handler import RelayHandler
from modules.config import OWNER_USERNAME

# Setup root logger
root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)

# Console handler
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(logging.Formatter("[%(asctime)s] [%(levelname)s] %(name)s: %(message)s", datefmt="%H:%M:%S"))
root_logger.addHandler(console_handler)

# File handler
try:
    file_handler = logging.FileHandler("bot.log", encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))
    root_logger.addHandler(file_handler)
except Exception as e:
    print(f"Failed to setup file logging: {e}")

logger = logging.getLogger("main")

# Mute noisy third-party loggers
logging.getLogger("instagrapi").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)
logging.getLogger("private_request").setLevel(logging.WARNING)
logging.getLogger("public_request").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

async def main() -> None:
    logger.info("AryaChatBot starting up…")

    groq_handler = GroqHandler()
    logger.info("Groq Handler initialized.")

    player = VLCPlayer(poll_interval=1.0)
    logger.info("VLC player ready.")

    music_handler = MusicHandler(player=player)
    logger.info("Music Handler initialized.")

    relay_handler = RelayHandler(owner_username=OWNER_USERNAME)
    logger.info("Relay Handler initialized (owner: %s).", OWNER_USERNAME or "<not set>")

    client = InstagramClient(groq_handler=groq_handler, music_handler=music_handler, relay_handler=relay_handler)

    try:
        client.login()
    except Exception as exc:
        logger.critical("Failed to authenticate with Instagram: %s", exc)
        logger.critical("Check instaCookies.txt and try again.")
        return

    logger.info("Listening for DMs… (Press Ctrl+C to stop)")
    try:
        await client.poll_dms()
    except KeyboardInterrupt:
        pass
    except asyncio.CancelledError:
        pass
    finally:
        logger.info("Bot shut down.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nShutdown requested — bye!")
