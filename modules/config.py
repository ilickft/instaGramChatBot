"""
config.py — Central configuration and path constants.
Loads environment variables from .env and creates the Downloads directory.
"""

import os
import logging
from pathlib import Path
from dotenv import load_dotenv

# ── Base paths ──────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent  # Root

# Load .env from project root
load_dotenv(BASE_DIR / ".env")

# ── Environment variables ────────────────────────────────────────────────────
CALL_LINK: str = os.getenv("CALL_LINK", "")
OWNER_USERNAME: str = os.getenv("OWNER_USERNAME", "")
LOGIN_METHOD: int = int(os.getenv("LOGIN_METHOD", "1"))
IG_USERNAME: str = os.getenv("IG_USERNAME", "")
IG_PASSWORD: str = os.getenv("IG_PASSWORD", "")

# ── File paths ───────────────────────────────────────────────────────────────
DOWNLOADS_DIR: Path = BASE_DIR / "Downloads"
LOG_FILE: Path = BASE_DIR / "bot.log"
INSTA_COOKIES: Path = BASE_DIR / "instaCookies.txt"
YT_COOKIES: Path = BASE_DIR / "ytCookies.txt"

# ── Ensure Downloads directory exists ───────────────────────────────────────
DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)
