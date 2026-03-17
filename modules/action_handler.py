"""
action_handler.py — Parses [ACTION:xxx] tags from Groq responses
and executes them.

Supported actions:
  [ACTION:post_story]  — renders a conversation card and posts to IG story
  [ACTION:post_feed]   — owner only: posts last photo from thread to IG feed

REMOVED (incompatible with cookie-only Instagram sessions):
  [ACTION:send_photo]  — direct media send blocked by Instagram API
  [ACTION:send_voice]  — direct audio send blocked by Instagram API
"""

import logging
import re
from pathlib import Path
from typing import Callable, Awaitable, Optional, Tuple

logger = logging.getLogger("action_handler")

# ── Action tag regex ──────────────────────────────────────────────────────────
_ACTION_RE = re.compile(r"\[ACTION:(\w+)\]", re.IGNORECASE)


# ── Public helpers ────────────────────────────────────────────────────────────

def parse_action(text: str) -> Tuple[str, Optional[str]]:
    """
    Extracts the first [ACTION:xxx] tag from text.
    Returns (clean_text, action_name) — action_name is None if no tag found.
    """
    m = _ACTION_RE.search(text)
    if not m:
        return text, None
    action = m.group(1).lower()
    clean  = _ACTION_RE.sub("", text).strip()
    return clean, action


class ActionHandler:
    """Executes action tags returned by Groq."""

    async def execute(
        self,
        action: str,
        thread_id: str,
        reply_text: str,
        convo_buffer: list,                                             # recent messages in this thread
        instagram_client,                                               # the InstagramClient instance
        reply_cb: Callable[[str], Awaitable[None]],
        owner_username: str = "",
        sender_username: str = "",
    ) -> None:
        """
        Execute an action.

        action            : action name from the [ACTION:xxx] tag
        thread_id         : current thread
        reply_text        : clean Groq reply (without action tag)
        convo_buffer      : list of recent {username, text, is_bot} dicts
        instagram_client  : InstagramClient (for its instagrapi _client + bot_username)
        reply_cb          : sends text back to the current thread
        owner_username    : bot owner's instagram handle
        sender_username   : who triggered this message
        """
        from modules.post_handler import generate_convo_card, post_to_story, post_to_feed

        # ── post_story: disabled — Instagram blocks media uploads for cookie-only sessions ──
        if action == "post_story":
            logger.debug("post_story action skipped (not supported with cookie-only auth)")

        # ── post_feed: owner-only feed post ──────────────────────────────────
        elif action == "post_feed":
            is_owner = (
                owner_username and
                sender_username and
                sender_username.lower().lstrip("@") == owner_username.lower().lstrip("@")
            )
            if not is_owner:
                logger.debug("post_feed ignored — sender %r is not owner", sender_username)
                return

            # The caption is whatever Arya said (or the owner's command text)
            caption = reply_text
            # For feed post we need an image — owner must have replied to one.
            # This is handled upstream in InstagramClient.handle_post_command().
            await reply_cb("(feed posting needs to be triggered with the `post` command — see docs)")

        else:
            logger.debug("Unknown action tag: %r — ignoring", action)
