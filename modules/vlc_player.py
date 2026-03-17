"""
vlc_player.py — VLC playback engine with a queue and history.

Uses python-vlc to control the host system's VLC Media Player.
A daemon monitor thread auto-advances the queue when a track ends.
"""

import logging
import threading
import time
from collections import deque
from pathlib import Path
from typing import Optional

import os
if hasattr(os, 'add_dll_directory'):
    try:
        os.add_dll_directory(r"C:\Program Files\VideoLAN\VLC")
    except Exception:
        pass

import vlc

logger = logging.getLogger("vlc_player")


class VLCPlayer:
    """
    Thread-safe wrapper around python-vlc.

    Queue:   deque of Path objects waiting to be played.
    History: list of Path objects already played (for 'prev').
    """

    def __init__(self, poll_interval: float = 1.0) -> None:
        self._instance = vlc.Instance("--no-xlib")  # headless-safe
        self._player: vlc.MediaPlayer = self._instance.media_player_new()
        self._queue: deque[dict] = deque()
        self._history: list[dict] = []
        self._current: Optional[dict] = None
        self._lock = threading.Lock()

        # Background thread that auto-advances the queue
        self._poll_interval = poll_interval
        self._monitor = threading.Thread(
            target=self._monitor_loop, daemon=True, name="vlc-monitor"
        )
        self._monitor.start()
        logger.debug("VLCPlayer initialised, monitor thread started.")

    # ── Internal helpers ─────────────────────────────────────────────────────

    def _play_file(self, track: dict) -> None:
        """Load and immediately play a local file. Must be called with _lock held."""
        path = track["path"]
        media = self._instance.media_new(str(path))
        self._player.set_media(media)
        self._player.play()
        self._current = track
        logger.debug("Now playing: %s", path.name)
        
        # Fire announcement callback if present
        cb = track.get("reply_cb")
        announcement = track.get("announcement")
        loop = track.get("loop")
        if cb and announcement and loop:
            import asyncio
            try:
                # Schedule the async callback safely from this sync monitor thread
                asyncio.run_coroutine_threadsafe(cb(announcement), loop)
            except Exception as e:
                logger.error("Failed to execute track announcement: %s", e)

    def _monitor_loop(self) -> None:
        """Daemon thread: watches VLC state and advances the queue on track end."""
        while True:
            time.sleep(self._poll_interval)
            try:
                with self._lock:
                    state = self._player.get_state()
                    # VLC states: Ended, Stopped, Error → advance queue if items waiting
                    if state in (vlc.State.Ended, vlc.State.Stopped, vlc.State.Error):
                        if self._current is not None:
                            # Track just finished — save to history
                            self._history.append(self._current)
                            self._current = None
                        if self._queue:
                            next_track = self._queue.popleft()
                            self._play_file(next_track)
            except Exception as exc:
                logger.error("Monitor thread error: %s", exc, exc_info=True)

    # ── Public API ────────────────────────────────────────────────────────────

    def enqueue(self, track: dict) -> None:
        """Add a track to the end of the queue."""
        with self._lock:
            self._queue.append(track)
            logger.debug("Enqueued: %s (queue len=%d)", track["path"].name, len(self._queue))

    def play_next(self) -> None:
        """
        If nothing is currently playing, start the next track in the queue.
        Called automatically by the monitor thread, but can be triggered manually.
        """
        with self._lock:
            state = self._player.get_state()
            is_idle = state in (
                vlc.State.NothingSpecial,
                vlc.State.Stopped,
                vlc.State.Ended,
                vlc.State.Error,
            )
            if is_idle and self._queue:
                next_track = self._queue.popleft()
                self._play_file(next_track)

    def is_playing(self) -> bool:
        """True if VLC is actively playing a track."""
        with self._lock:
            return self._player.get_state() == vlc.State.Playing

    def is_active(self) -> bool:
        """True if a track is currently loaded (playing or paused)."""
        with self._lock:
            return self._current is not None

    def skip(self) -> None:
        """Skip the current track and play the next one in the queue."""
        with self._lock:
            if self._current is not None:
                self._history.append(self._current)
                self._current = None
            self._player.stop()
            if self._queue:
                next_track = self._queue.popleft()
                self._play_file(next_track)
        logger.debug("Skipped to next track.")

    def stop(self) -> None:
        """Stop playback and clear the entire queue."""
        with self._lock:
            if self._current is not None:
                self._history.append(self._current)
                self._current = None
            self._player.stop()
            self._queue.clear()
        logger.debug("Playback stopped and queue cleared.")

    def pause(self) -> None:
        """Pause the current track."""
        with self._lock:
            if self._player.get_state() == vlc.State.Playing:
                self._player.pause()
        logger.debug("Paused.")

    def resume(self) -> None:
        """Resume a paused track."""
        with self._lock:
            if self._player.get_state() == vlc.State.Paused:
                self._player.pause()  # VLC toggle: pause() on Paused → resumes
        logger.debug("Resumed.")

    def prev(self) -> None:
        """
        Stop current track and replay the most recently played song.
        The track is pulled from history and placed at the front of the queue.
        """
        with self._lock:
            if not self._history:
                logger.debug("prev() called but history is empty.")
                return
            prev_track = self._history.pop()
            # Re-queue current track at the front if one is playing
            if self._current is not None:
                self._queue.appendleft(self._current)
                self._current = None
            self._player.stop()
            self._play_file(prev_track)
        logger.debug("Playing previous track: %s", prev_track["path"].name)

    def current_track(self) -> Optional[Path]:
        """Return the Path of the currently active track, or None."""
        with self._lock:
            return self._current["path"] if self._current else None
