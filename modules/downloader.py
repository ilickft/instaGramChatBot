"""
downloader.py — Async audio downloader powered by yt-dlp.
Downloads are placed permanently in the Downloads/ folder.
Never deletes files.
"""

import asyncio
import logging
import re
from pathlib import Path
from typing import Tuple, Optional

import yt_dlp

from modules.config import DOWNLOADS_DIR, YT_COOKIES

logger = logging.getLogger("downloader")


def _sanitize_filename(name: str) -> str:
    """Strip characters that are unsafe in Windows filenames."""
    return re.sub(r'[\\/*?:"<>|]', "_", name).strip()


def _build_ydl_opts(output_template: str, use_cookies: bool = False) -> dict:
    """Build yt-dlp options dict."""
    opts = {
        # Best audio quality, fallback to any available if the video doesn't have split streams
        "format": "bestaudio/best/ba/b",
        "outtmpl": output_template,
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        # Write metadata for later use
        "writethumbnail": False,
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }
        ],
    }

    # Only add cookiefile if the file actually exists AND is explicitly requested
    if use_cookies and YT_COOKIES.exists():
        opts["cookiefile"] = str(YT_COOKIES)

    return opts


def _format_duration(seconds: int) -> str:
    if not seconds:
        return "00:00"
    m, s = divmod(seconds, 60)
    h, m = divmod(m, 60)
    if h > 0:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"

def _format_views(views: int) -> str:
    if not views:
        return "0"
    if views >= 1_000_000:
        return f"{views / 1_000_000:.1f}M".replace(".0M", "M")
    if views >= 1_000:
        return f"{views / 1_000:.1f}K".replace(".0K", "K")
    return str(views)

def _get_info_sync(query_or_url: str) -> Tuple[Optional[Path], str, str, str, str, str]:
    """
    Returns (cached_path_if_exists, title, safe_title, search_target, duration_str, views_str)
    """
    is_url = query_or_url.startswith(("http://", "https://"))
    search_target = query_or_url if is_url else f"ytsearch1:{query_or_url}"

    info_opts = {
        "format": "bestaudio/best/ba/b",
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "skip_download": True,
    }

    def fetch_info(use_cookies: bool):
        opts = dict(info_opts)
        if use_cookies and YT_COOKIES.exists():
            opts["cookiefile"] = str(YT_COOKIES)
        with yt_dlp.YoutubeDL(opts) as ydl:
            return ydl.extract_info(search_target, download=False)

    try:
        # Try without cookies first to avoid bot detection for normal videos
        info = fetch_info(use_cookies=False)
    except yt_dlp.utils.DownloadError as e:
        err_msg = str(e).lower()
        if "sign in" in err_msg or "age" in err_msg or "private" in err_msg or "restricted" in err_msg or "kids" in err_msg:
            # Target may be age-restricted, fallback to cookies
            try:
                info = fetch_info(use_cookies=True)
            except yt_dlp.utils.DownloadError as e_inner:
                err_msg_inner = str(e_inner).lower()
                if "not available" in err_msg_inner or "private" in err_msg_inner or "restricted" in err_msg_inner or "kids" in err_msg_inner or "sign in" in err_msg_inner:
                    raise ValueError("restricted_content")
                raise e_inner
        else:
            err_msg_outer = str(e).lower()
            if "not available" in err_msg_outer:
                 raise ValueError("restricted_content")
            raise e

    if "entries" in info:
        if not info["entries"]:
            raise ValueError("not_found")
        info = info["entries"][0]

    title: str = info.get("title", "unknown_track")
    safe_title = _sanitize_filename(title)
    
    duration = info.get("duration", 0)
    views = info.get("view_count", 0)
    
    dur_str = _format_duration(duration)
    views_str = _format_views(views)

    matches = list(DOWNLOADS_DIR.glob(f"{safe_title}.*"))
    if matches:
        final_path = matches[0]
        logger.debug("Cache hit: File already exists locally -> %s", final_path)
        return final_path, title, safe_title, search_target, dur_str, views_str

    return None, title, safe_title, search_target, dur_str, views_str


def _download_file_sync(search_target: str, safe_title: str) -> Path:
    """Actually downloads the file."""
    output_template = str(DOWNLOADS_DIR / f"{safe_title}.%(ext)s")
    
    try:
        opts = _build_ydl_opts(output_template, use_cookies=False)
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.download([search_target])
    except yt_dlp.utils.DownloadError as e:
        err_msg = str(e).lower()
        if "sign in" in err_msg or "age" in err_msg or "private" in err_msg or "restricted" in err_msg or "kids" in err_msg:
            logger.debug("Download restricted without cookies for %r, retrying with cookies...", safe_title)
            opts_with_cookies = _build_ydl_opts(output_template, use_cookies=True)
            with yt_dlp.YoutubeDL(opts_with_cookies) as ydl:
                ydl.download([search_target])
        else:
            raise e

    final_path = DOWNLOADS_DIR / f"{safe_title}.mp3"
    if not final_path.exists():
        matches = list(DOWNLOADS_DIR.glob(f"{safe_title}.*"))
        if matches:
            final_path = matches[0]
        else:
            raise FileNotFoundError(f"Output file not found for: {safe_title!r}")

    logger.debug("Downloaded: %s", final_path)
    return final_path


async def get_info(query_or_url: str) -> Tuple[Optional[Path], str, str, str, str, str]:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _get_info_sync, query_or_url)


async def download_audio(search_target: str, safe_title: str) -> Path:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _download_file_sync, search_target, safe_title)
