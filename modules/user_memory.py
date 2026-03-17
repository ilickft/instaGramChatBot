"""
user_memory.py — Persistent per-user profile memory for Aryaa.
Stores and loads user profiles from user_profiles.json.

Profile fields per username:
  name        : what they told Arya their name is
  behavior    : Arya's note on how they act
  talk_type   : their communication style
  relation    : Arya's feel for them
  bestfriend  : bool
  stranger    : bool
  bad_person  : bool — if True, Arya will semi-ignore them
  msg_count   : how many messages Arya has seen from them
"""

import json
import logging
import random
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

logger = logging.getLogger("user_memory")

PROFILES_FILE = Path("user_profiles.json")

# Probability of ignoring a message from a bad-listed person (0.0–1.0)
BAD_PERSON_IGNORE_CHANCE = 0.55

# Default empty profile
_DEFAULT_PROFILE = {
    "name":             None,
    "behavior":         None,
    "current_behavior": None,
    "behavior_history": [],
    "talk_type":        None,
    "preferred_language": None,  # e.g. "english", "hinglish", "hindi"
    "relation":         None,
    "hobbies":          None,
    "dislikes":         None,
    "notes":            None,
    "recent_activity":  [],     # last 4 messages [{"from": "user"|"arya", "text": "..."}]
    "bestfriend":       False,
    "stranger":         True,
    "bad_person":       False,
    "msg_count":        0,
}


class UserMemory:
    """Load, query, and persist user profiles."""

    def __init__(self) -> None:
        self._profiles: dict = {}
        self.load()

    # ── Persistence ───────────────────────────────────────────────────────────

    def load(self) -> None:
        if PROFILES_FILE.exists():
            try:
                self._profiles = json.loads(PROFILES_FILE.read_text(encoding="utf-8"))
                logger.debug("Loaded %d user profiles from %s", len(self._profiles), PROFILES_FILE)
            except Exception as exc:
                logger.error("Failed to load user profiles: %s", exc)
                self._profiles = {}
        else:
            self._profiles = {}

    def save(self) -> None:
        try:
            PROFILES_FILE.write_text(
                json.dumps(self._profiles, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except Exception as exc:
            logger.error("Failed to save user profiles: %s", exc)

    # ── Profile access ────────────────────────────────────────────────────────

    def get_profile(self, username: str) -> dict:
        username = username.lower().lstrip("@")
        if username not in self._profiles:
            self._profiles[username] = dict(_DEFAULT_PROFILE)
        else:
            # Forward-compatible: backfill any keys that didn't exist in older versions
            for key, default_val in _DEFAULT_PROFILE.items():
                if key not in self._profiles[username]:
                    self._profiles[username][key] = default_val
        return self._profiles[username]

    def bump_msg_count(self, username: str) -> None:
        p = self.get_profile(username)
        p["msg_count"] = p.get("msg_count", 0) + 1
        self.save()

    def push_activity(self, username: str, sender: str, text: str) -> None:
        """Append a message to recent_activity, keeping only the last 4."""
        p = self.get_profile(username)
        if not isinstance(p.get("recent_activity"), list):
            p["recent_activity"] = []
        p["recent_activity"].append({"from": sender, "text": text[:200]})  # cap length
        p["recent_activity"] = p["recent_activity"][-4:]  # keep last 4 only
        self.save()

    # ── Memory update ─────────────────────────────────────────────────────────

    def push_behavior_history(self, username: str, note: str) -> None:
        """
        Upsert today's behavior_history entry. If an entry for today already
        exists it gets replaced; otherwise a new one is appended.
        Max 4 entries total — oldest entry is dropped when limit is exceeded.
        """
        p = self.get_profile(username)
        if not isinstance(p.get("behavior_history"), list):
            p["behavior_history"] = []
        today = datetime.now().strftime("%Y-%m-%d")
        # Update existing entry for today if present
        for entry in p["behavior_history"]:
            if entry.get("date") == today:
                entry["note"] = note
                p["behavior_history"] = p["behavior_history"][-4:]  # trim either way
                self.save()
                return
        # No entry yet today — append and trim to max 4
        p["behavior_history"].append({"date": today, "note": note})
        p["behavior_history"] = p["behavior_history"][-4:]
        self.save()

    def apply_updates(self, username: str, updates: dict) -> None:
        """
        Merge updates into the user's profile.
        Special cases:
          - behavior_history → routed to push_behavior_history (once-per-day, max 4)
          - dislikes        → auto-removes matching items from hobbies
        """
        p = self.get_profile(username)

        for key, val in updates.items():
            if key == "behavior_history":
                # AI wrote a daily summary — push it properly
                self.push_behavior_history(username, str(val))
                continue
            if key in _DEFAULT_PROFILE or key == "msg_count":
                p[key] = val
                logger.debug("Memory update for @%s: %s = %r", username, key, val)

        # Auto cross-check: remove newly disliked things from hobbies
        if "dislikes" in updates and p.get("hobbies") and updates["dislikes"]:
            new_dislikes = [d.strip().lower() for d in str(updates["dislikes"]).split(",")]
            hobby_items  = [h.strip() for h in str(p["hobbies"]).split(",")]
            cleaned      = [h for h in hobby_items if h.lower() not in new_dislikes]
            if len(cleaned) != len(hobby_items):
                p["hobbies"] = ", ".join(cleaned) if cleaned else None
                logger.debug("Removed disliked items from hobbies for @%s", username)

        self.save()

    # ── Bad person logic ──────────────────────────────────────────────────────

    def is_bad_person(self, username: str) -> bool:
        return self.get_profile(username).get("bad_person", False)

    def should_ignore(self, username: str) -> bool:
        """Returns True if this message should be silently dropped (bad person throttle)."""
        if not self.is_bad_person(username):
            return False
        return random.random() < BAD_PERSON_IGNORE_CHANCE

    # ── Context string for Groq ───────────────────────────────────────────────

    def build_context(self, username: str) -> str:
        """
        Returns a short plain-text summary of what Arya knows about this user,
        ready to inject into the Groq system/user message.
        """
        p = self.get_profile(username)
        username = username.lower().lstrip("@")

        lines = [f"What you know about @{username}:"]

        if p.get("name"):
            lines.append(f"  Their name: {p['name']}")
        if p.get("behavior"):
            lines.append(f"  General personality: {p['behavior']}")
        if p.get("current_behavior"):
            lines.append(f"  Current behavior (right now): {p['current_behavior']}")
        if p.get("behavior_history"):
            recent = p["behavior_history"][-3:]  # show last 3 entries max
            history_str = " | ".join(f"{e['date']}: {e['note']}" for e in recent)
            lines.append(f"  Behavior last 7 days: {history_str}")
        if p.get("talk_type"):
            lines.append(f"  How they talk: {p['talk_type']}")
        if p.get("preferred_language"):
            lines.append(f"  Preferred language: {p['preferred_language']} — ALWAYS reply in this language/style")
        if p.get("relation"):
            lines.append(f"  Your relation: {p['relation']}")
        if p.get("hobbies"):
            lines.append(f"  Their hobbies: {p['hobbies']}")
        if p.get("dislikes"):
            lines.append(f"  Things they dislike: {p['dislikes']}")
        if p.get("notes"):
            lines.append(f"  Personal notes: {p['notes']}")
        if p.get("recent_activity"):
            lines.append("  Recent conversation (last 4 messages):")
            for msg in p["recent_activity"]:
                who = "You" if msg["from"] == "arya" else f"@{username}"
                lines.append(f"    {who}: {msg['text']}")
        if p.get("bestfriend"):
            lines.append("  They are your best friend.")
        if p.get("bad_person"):
            lines.append("  WARNING: You don't like this person. Be cold or semi-ignore them.")
        if p.get("stranger") and not p.get("behavior"):
            lines.append("  You don't know them yet. First time talking.")

        lines.append(f"  Messages seen: {p.get('msg_count', 0)}")
        return "\n".join(lines)
