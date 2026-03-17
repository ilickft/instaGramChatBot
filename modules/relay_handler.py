"""
relay_handler.py — Lets the bot owner relay a message to a known user.

Command format:
    message @username [what to say]
    msg @username [what to say]

Scenario A (known user): bot tags @username in their thread with the relayed message.
Scenario B (unknown user): bot replies to owner asking for clarification.
"""

import logging
import re
from typing import Callable, Awaitable, Optional

logger = logging.getLogger("relay_handler")

# Regex: matches "message @username rest of text" or "msg @username rest of text"
_RELAY_RE = re.compile(
    r"^(?:message|msg)\s+@([\w.]+)\s+(.+)$",
    re.IGNORECASE | re.DOTALL,
)


def is_relay_command(text: str) -> bool:
    """Returns True if the text looks like a relay command."""
    return bool(_RELAY_RE.match(text.strip()))


class RelayHandler:
    def __init__(self, owner_username: str) -> None:
        """
        owner_username: the Instagram handle of the bot owner.
                        Only messages from this user trigger relays.
        """
        self.owner_username = owner_username.lower().lstrip("@") if owner_username else ""

    def is_owner(self, sender_username: Optional[str]) -> bool:
        if not self.owner_username or not sender_username:
            return False
        return sender_username.lower().lstrip("@") == self.owner_username

    async def handle(
        self,
        text: str,
        sender_username: Optional[str],
        user_registry: dict,                        # {username: thread_id}
        reply_cb: Callable[[str], Awaitable[None]], # sends to owner's thread
        send_to_thread_cb: Callable[[str, str], Awaitable[None]],  # (thread_id, msg)
    ) -> Optional[str]:
        """
        Main entry point for a relay command.
        Returns a reply string for the owner's thread, or None.
        """
        m = _RELAY_RE.match(text.strip())
        if not m:
            return None

        target_username = m.group(1).lower()
        relay_text = m.group(2).strip()

        owner_display = f"@{sender_username}" if sender_username else "Someone"

        # ── Scenario A: user is known ─────────────────────────────────────────
        if target_username in user_registry:
            target_thread_id = user_registry[target_username]
            outgoing = (
                f"Hey @{target_username}! {owner_display} asked me to pass this along: \n\n"
                f"\"{relay_text}\""
            )
            await send_to_thread_cb(target_thread_id, outgoing)
            logger.debug("Relayed message to @%s in thread %s", target_username, target_thread_id)
            return f"✅ Message sent to @{target_username}!"

        # ── Scenario B: user is unknown ──────────────────────────────────────
        logger.debug("Relay target @%s not in registry (%d known users)", target_username, len(user_registry))
        known_list = ", ".join(f"@{u}" for u in sorted(user_registry.keys())) or "nobody yet"
        return (
            f"I haven't talked to @{target_username} before, so I don't know which thread they're in.\n\n"
            f"Are they in one of my groups? Or is this a DM-only contact?\n\n"
            f"People I currently know: {known_list}"
        )
