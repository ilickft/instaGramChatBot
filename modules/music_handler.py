"""
music_handler.py — Connects special prefixed DMs to VLCPlayer and yt-dlp downloader.
"""

import asyncio
import logging
import webbrowser
from typing import Optional, Callable, Awaitable
from pathlib import Path

from modules.config import CALL_LINK
from modules.downloader import get_info, download_audio
from modules.vlc_player import VLCPlayer

logger = logging.getLogger("music_handler")

# Your custom map covering both upper and lowercase
SMALL_CAPS_MAP = str.maketrans(
    "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz",
    "ᴀʙᴄᴅᴇꜰɢʜɪᴊᴋʟᴍɴᴏᴘǭʀꜱᴛᴜᴠᴡxʏᴢᴀʙᴄᴅᴇꜰɢʜɪᴊᴋʟᴍɴᴏᴘφʀꜱᴛᴜᴠᴡxʏᴢ"
)

def _to_small_caps(text: str) -> str:
    """Translates text to small caps using the map above."""
    return text.translate(SMALL_CAPS_MAP)

class MusicHandler:
    def __init__(self, player: VLCPlayer) -> None:
        self._player = player
        self.prefixes = ("/", ".", "!", "$", "0")

    def is_music_command(self, text: str) -> bool:
        """Returns True if the text starts with any of the configured prefixes."""
        text = text.strip()
        return any(text.startswith(p) for p in self.prefixes)

    def _get_help_message(self) -> str:
        help_text = (
            f"🎵 {_to_small_caps('MUSIC BOT COMMANDS')} 🎵\n"
            "------------------------------------\n"
            f"Use any prefix: /, ., !, $, 0\n"
            f"▶️ {_to_small_caps('PLAY <QUERY>')}\n"
            f"   {_to_small_caps('search and play or queue music')}\n"
            f"   {_to_small_caps('ex: /play stay with me')}\n\n"
            f"⏭️ {_to_small_caps('SKIP')}\n"
            f"   {_to_small_caps('play the next song in queue')}\n\n"
            f"⏸️ {_to_small_caps('PAUSE / RESUME')}\n"
            f"   {_to_small_caps('control current playback')}\n\n"
            f"⏹️ {_to_small_caps('STOP / END')}\n"
            f"   {_to_small_caps('stop music and clear queue')}\n\n"
            f"⏪ {_to_small_caps('PREV')}\n"
            f"   {_to_small_caps('play the previous track')}\n"
            "------------------------------------\n"
            f" @ilickft {_to_small_caps('dm bugs / issues')}\n"
            "------------------------------------"
        )
        return help_text

    async def handle(self, text: str, reply_cb: Optional[Callable[[str], Awaitable[None]]] = None) -> Optional[str]:
        """
        Strips the prefix, checks the command, and triggers VLC/downloader.
        """
        text = text.strip()
        
        # Strip the prefix
        for p in self.prefixes:
            if text.startswith(p):
                text = text[len(p):].strip()
                break
                
        lower = text.lower()

        try:
            if lower == "start":
                return await self._handle_start()

            if lower in ("-help", "help"):
                return self._get_help_message()

            if lower.startswith("play"):
                query = text[4:].strip()
                if query:
                    return await self._handle_play(query, reply_cb)
                return _to_small_caps("Try something like \n /play <song name> 🥀")

            if lower == "skip":
                return await self._handle_skip()

            if lower in ("stop", "end"):
                return await self._handle_stop()

            if lower == "pause":
                return await self._handle_pause()

            if lower == "resume":
                return await self._handle_resume()

            if lower == "prev":
                return await self._handle_prev()
            
            if lower in ("ping", "alive"):
                return _to_small_caps("I'm alive nigga 🥀")

        except Exception as exc:
            logger.error("Error handling command %r: %s", text, exc, exc_info=True)

        return None

    async def _handle_start(self) -> None:
        if CALL_LINK:
            webbrowser.open(CALL_LINK)
            logger.debug("Opened call link: %s", CALL_LINK)
        return None

    async def _handle_play(self, query: str, reply_cb: Optional[Callable[[str], Awaitable[None]]] = None) -> Optional[str]:
        logger.debug("play command: %r", query)

        if reply_cb is not None:
            await reply_cb(_to_small_caps("Hold on..."))

        try:
            cached_path, title, safe_title, search_target, dur_str, views_str = await get_info(query)
        except ValueError as e:
            if str(e) == "restricted_content":
                return _to_small_caps("This content is restricted from youtube \n[ made for kids or offensive]")
            elif str(e) == "not_found":
                return _to_small_caps("Try something else twin 🥀")
            raise

        title_caps = _to_small_caps(title)

        start_message = (
            f"🎵 {_to_small_caps('Starting stream')} 🎵\n"
            f"------------------------------------\n"
            f" {title_caps}\n"
            f"------------------------------------\n"
            f"↬ {_to_small_caps('duration')} - {dur_str}\n"
            f"↬ {_to_small_caps('views')} - {views_str}\n"
            f"------------------------------------\n"
            f" @ilickft {_to_small_caps('dm bugs / issues')}\n"
            "------------------------------------"
        )
        
        queue_message = (
            f" {title_caps}\n"
            f"------------------------------------\n"
            f"↬ {_to_small_caps('duration')} - {dur_str}\n"
            f"↬ {_to_small_caps('views')} - {views_str}\n"
            f"------------------------------------\n"
            f"{_to_small_caps('Added to Queue')}\n"
            "------------------------------------"
        )

        track_info = {
            "title": title_caps,
            "announcement": start_message,
            "reply_cb": reply_cb,
            "loop": asyncio.get_event_loop()
        }

        asyncio.create_task(
            self._download_and_enqueue(cached_path, title, safe_title, search_target, track_info)
        )

        return queue_message if self._player.is_active() else None

    async def _download_and_enqueue(self, cached_path: Optional[Path], title: str, safe_title: str, search_target: str, track_info: dict) -> None:
        try:
            path = cached_path if cached_path else await download_audio(search_target, safe_title)
            track_info["path"] = path
            self._player.enqueue(track_info)
            if not self._player.is_active():
                self._player.play_next()
        except Exception as exc:
            logger.error("Background download failed for %r: %s", title, exc)

    async def _handle_skip(self) -> str:
        self._player.skip()
        if self._player.is_active():
            return f"🎵 {_to_small_caps('Stream skipped')} 🎵\n"
        return _to_small_caps('really nigga?\nstream cleared btw')

    async def _handle_stop(self) -> str:
        self._player.stop()
        return _to_small_caps("okay bye,\nclearing all tracks 🥀")

    async def _handle_pause(self) -> str:
        self._player.pause()
        return _to_small_caps("okay,\ni'll keep quiet")

    async def _handle_resume(self) -> str:
        self._player.resume()
        return _to_small_caps("should i touch you?\n resumed")

    async def _handle_prev(self) -> str:
        self._player.prev()
        return _to_small_caps("WTF, why again?")
