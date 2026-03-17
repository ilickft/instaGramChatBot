"""
instagram_client.py — Instagram DM listener using instagrapi.
Authenticates via instaCookies.txt. Polls all DM threads and dispatches them to GroqHandler.
"""

import asyncio
import logging
import json
import time
import re
from collections import deque
from pathlib import Path
from typing import Dict, Optional

from instagrapi import Client
from instagrapi.exceptions import LoginRequired, ClientError

from modules.groq_handler import GroqHandler
from modules.music_handler import MusicHandler
from modules.relay_handler import RelayHandler, is_relay_command
from modules.action_handler import ActionHandler
from modules.config import OWNER_USERNAME
from modules.user_memory import UserMemory

logger = logging.getLogger("instagram_client")

# How many seconds to wait between DM polls
POLL_INTERVAL: float = 5.0

# How many DM threads to check on each poll cycle
THREAD_LIMIT: int = 40

# Directory for cookies
INSTA_COOKIES = Path("instaCookies.txt")

class InstagramClient:
    """Manages Instagram authentication and the DM polling loop."""

    def __init__(self, groq_handler: GroqHandler, music_handler: MusicHandler, relay_handler: RelayHandler) -> None:
        self._groq_handler    = groq_handler
        self._music_handler   = music_handler
        self._relay_handler   = relay_handler
        self._action_handler  = ActionHandler()
        self._user_memory      = UserMemory()
        self._client          = Client()
        self._client.set_user_agent("Instagram 410.0.0.0.96 Android (33/13; 480dpi; 1080x2400; xiaomi; M2007J20CG; surya; qcom; en_US; 641123490)")

        
        # Monkey patch private_request to fix 1404006 error on direct_v2/inbox/
        original_private_request = self._client.private_request
        def patched_private_request(endpoint, data=None, params=None, **kwargs):
            if endpoint == "direct_v2/inbox/" and isinstance(params, dict):
                params.pop("persistentBadging", None)
                params.pop("is_prefetching", None)
                params.pop("thread_message_limit", None)
                params.pop("visual_message_return_type", None)
                params.pop("limit", None)
            return original_private_request(endpoint, data=data, params=params, **kwargs)
        self._client.private_request = patched_private_request

        self._last_seen: Dict[str, str] = {}
        self._authenticated   = False
        self._chatbot_enabled = True
        # username -> thread_id registry
        self._user_registry: Dict[str, str] = {}
        # rolling conversation buffer per thread: {thread_id: deque of {username, text, is_bot}}
        self._convo_buffers: Dict[str, deque] = {}
        # bot's own username (resolved after login)
        self.bot_username: str = "aryaa.kiu"
        self._owner_username: str = OWNER_USERNAME

        from dotenv import load_dotenv
        import os
        load_dotenv()
        self.ignored_usernames = set(
            name.strip().lower() for name in os.getenv("IGNORED_USERNAMES", "").split(",") if name.strip()
        )
        self.ignored_user_ids = set()

    @staticmethod
    def _parse_netscape_cookies(raw: str) -> dict:
        cookies: dict = {}
        for line in raw.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split("\t")
            if len(parts) < 7:
                continue
            name = parts[5].strip()
            value = parts[6].strip()
            if name:
                cookies[name] = value
        return cookies

    def _load_cookies(self) -> None:
        if not INSTA_COOKIES.exists():
            raise FileNotFoundError(
                f"Cookie file not found: {INSTA_COOKIES}\n"
                "Export your Instagram cookies and save them as 'instaCookies.txt'."
            )

        raw = INSTA_COOKIES.read_text(encoding="utf-8").strip()

        try:
            settings = json.loads(raw)
            if isinstance(settings, dict) and "cookies" in settings:
                self._client.set_settings(settings)
                self._client.login(
                    settings.get("username", ""),
                    settings.get("password", ""),
                    relogin=True,
                )
                logger.debug("Authenticated via instagrapi settings JSON.")
                return
        except json.JSONDecodeError:
            pass
        except Exception as exc:
            logger.error("Settings JSON login failed: %s", exc)

        try:
            parsed = json.loads(raw)
            if isinstance(parsed, list):
                cookie_dict = {c["name"]: c["value"] for c in parsed if "name" in c}
                self._apply_cookie_dict(cookie_dict)
                logger.debug("Authenticated via browser JSON cookie array.")
                return
        except json.JSONDecodeError:
            pass
        except Exception as exc:
            logger.error("Browser JSON cookie login failed: %s", exc)

        if raw.startswith("# Netscape") or "\t" in raw:
            try:
                cookie_dict = self._parse_netscape_cookies(raw)
                if not cookie_dict:
                    raise ValueError("No cookies parsed from Netscape file.")
                self._apply_cookie_dict(cookie_dict)
                logger.debug("Authenticated via Netscape cookie file.")
                return
            except Exception as exc:
                logger.error("Netscape cookie login failed: %s", exc)

        raise RuntimeError("Could not authenticate from instaCookies.txt.")

    def _apply_cookie_dict(self, cookie_dict: dict) -> None:
        session_id = cookie_dict.get("sessionid", "")
        ds_user_id = cookie_dict.get("ds_user_id", "")

        if not session_id:
            raise ValueError("No 'sessionid' cookie found.")

        self._client.device_settings.update({
            "app_version": "410.0.0.0.96",
            "version_code": "641123490",
            "android_version": 33,
            "android_release": "13",
            "dpi": "480dpi",
            "resolution": "1080x2400",
            "manufacturer": "xiaomi",
            "device": "surya",
            "model": "M2007J20CG",
            "cpu": "qcom",
        })
        self._client.user_agent = f"Instagram {self._client.device_settings['app_version']} " \
                                  f"Android ({self._client.device_settings['android_version']}/" \
                                  f"{self._client.device_settings['android_release']}; " \
                                  f"{self._client.device_settings['dpi']}; " \
                                  f"{self._client.device_settings['resolution']}; " \
                                  f"{self._client.device_settings['manufacturer']}; " \
                                  f"{self._client.device_settings['model']}; " \
                                  f"{self._client.device_settings['device']}; " \
                                  f"{self._client.device_settings['cpu']}; en_US; " \
                                  f"{self._client.device_settings['version_code']})"

        settings = {
            "cookies": cookie_dict,
            "uuids": {
                "phone_id": self._client.phone_id,
                "uuid": self._client.uuid,
                "client_session_id": self._client.client_session_id,
                "advertising_id": self._client.advertising_id,
                "android_device_id": self._client.android_device_id,
            },
            "authorization_data": {"sessionid": session_id},
            "last_login": time.time(),
            "device_settings": self._client.device_settings,
            "user_agent": self._client.user_agent,
        }

        self._client.set_settings(settings)
        self._client.private.cookies.update(cookie_dict)

        user_id = self._client.user_id_from_username(self._client.username) if self._client.username else ds_user_id
        if not user_id and ds_user_id:
            user_id = ds_user_id

        logger.debug("Session validated — user_id=%s", user_id)

    def login(self) -> None:
        logger.debug("Logging in to Instagram…")
        from modules.config import LOGIN_METHOD, IG_USERNAME, IG_PASSWORD, BASE_DIR
        
        if LOGIN_METHOD == 2:
            if not IG_USERNAME or not IG_PASSWORD:
                logger.error("IG_USERNAME or IG_PASSWORD not set. Falling back to cookies (method 1).")
                self._load_cookies()
            else:
                logger.info("Using Username/Password login (LOGIN_METHOD=2)")
                settings_file = BASE_DIR / "ig_settings.json"
                try:
                    if settings_file.exists():
                        self._client.load_settings(settings_file)
                        logger.debug("Loaded saved session from ig_settings.json")
                    self._client.login(IG_USERNAME, IG_PASSWORD)
                    self._client.dump_settings(settings_file)
                    logger.debug("Credentials login successful, saved session")
                except Exception as e:
                    logger.error("Username/Password login failed: %s", e)
                    raise
        else:
            self._load_cookies()

        self._authenticated = True
        logger.info("Instagram login successful.")
        
        for username in self.ignored_usernames:
            try:
                user_id = self._client.user_id_from_username(username)
                if user_id:
                    self.ignored_user_ids.add(str(user_id))
                    logger.debug("Resolved ignored user %s to ID %s", username, user_id)
            except Exception as e:
                logger.error("Failed to resolve user ID for ignored user %s: %s", username, e)

    async def poll_dms(self) -> None:
        if not self._authenticated:
            raise RuntimeError("Call login() before poll_dms().")

        logger.info("DM polling started (interval=%.1fs). Listening for new messages...", POLL_INTERVAL)

        while True:
            try:
                await self._poll_once()
            except LoginRequired:
                logger.error("Instagram session expired — re-authenticating…")
                try:
                    self.login()
                except Exception as relogin_exc:
                    logger.error("Re-authentication failed: %s", relogin_exc)
                    await asyncio.sleep(30)
            except ClientError as exc:
                logger.error("Instagram API error: %s", exc, exc_info=True)
                await asyncio.sleep(POLL_INTERVAL * 2)
            except asyncio.CancelledError:
                logger.debug("DM polling cancelled.")
                raise
            except Exception as exc:
                logger.error("Unexpected poll error: %s", exc, exc_info=True)

            await asyncio.sleep(POLL_INTERVAL)

    async def _poll_once(self) -> None:
        loop = asyncio.get_event_loop()
        threads = await loop.run_in_executor(
            None, lambda: self._client.direct_threads(amount=THREAD_LIMIT)
        )

        for thread in threads:
            thread_id = str(thread.id)
            messages = thread.messages 

            if not messages:
                continue

            newest_id = str(messages[0].id)
            if self._last_seen.get(thread_id) == newest_id:
                continue

            # Accumulate all new messages since the last time we checked this thread
            new_msgs = []
            for msg in messages:
                if str(msg.id) == self._last_seen.get(thread_id):
                    break
                new_msgs.append(msg)

            self._last_seen[thread_id] = newest_id

            new_user_texts = []
            sender_username = None

            # Process chronologically
            for msg in reversed(new_msgs):
                if str(msg.user_id) == str(self._client.user_id):
                    continue
                if str(msg.user_id) in self.ignored_user_ids:
                    continue

                # Lazily resolve sender username
                if not sender_username:
                    sender_username = next((u.username for u in thread.users if str(u.pk) == str(msg.user_id)), None)
                if sender_username and sender_username.lower() in self.ignored_usernames:
                    continue

                if msg.item_type != "text":
                    continue

                text = msg.text or ""
                if text.strip():
                    new_user_texts.append(text.strip())

            if not new_user_texts:
                continue

            combined_text = "\n".join(new_user_texts)

            # Register user in the known-users registry (username -> thread_id)
            if sender_username:
                self._user_registry[sender_username.lower()] = thread_id

            # Add to per-thread conversation buffer (keep last 12 messages)
            if thread_id not in self._convo_buffers:
                self._convo_buffers[thread_id] = deque(maxlen=12)
            self._convo_buffers[thread_id].append({
                "username": sender_username or "unknown",
                "text": combined_text,
                "is_bot": False,
            })

            # Record in persistent recent_activity for this user
            if sender_username:
                self._user_memory.push_activity(sender_username, "user", combined_text)

            logger.debug("New message(s) in thread %s: %s", thread_id, combined_text)

            loop.create_task(self._handle_message_async(combined_text, thread_id, sender_username))
            
    async def _handle_message_async(self, text: str, thread_id: str, sender_username: Optional[str] = None):
        async def reply_cb(msg: str) -> None:
            await self._send_reply(thread_id, msg)

        try:
            # ── Owner post command ────────────────────────────────────────────
            is_owner = (
                self._owner_username and
                sender_username and
                sender_username.lower().lstrip("@") == self._owner_username.lower().lstrip("@")
            )
            if is_owner and re.match(r'^post\b', text, re.IGNORECASE):
                logger.debug("Routing message to post command handler")
                await self._handle_post_command(text, thread_id, sender_username)
                return

            if is_owner and text.lower().startswith("/chatbot "):
                cmd_param = text.lower().split("/chatbot ")[1].strip()
                if cmd_param == "off":
                    self._chatbot_enabled = False
                    await reply_cb("Chatbot AI responses are now OFF. 🛑")
                elif cmd_param == "on":
                    self._chatbot_enabled = True
                    await reply_cb("Chatbot AI responses are now ON. 🟢")
                else:
                    await reply_cb("Usage: /chatbot on | /chatbot off")
                return

            # If chatbot is disabled, do not process Groq AI or Relay
            if not self._chatbot_enabled:
                if is_owner:
                    logger.debug("Chatbot disabled. Owner message ignored by AI.")
                return

            # ── Relay command (owner only) ────────────────────────────────────
            if is_relay_command(text) and self._relay_handler.is_owner(sender_username):
                logger.debug("Routing message to RelayHandler")
                reply: Optional[str] = await self._relay_handler.handle(
                    text=text,
                    sender_username=sender_username,
                    user_registry=self._user_registry,
                    reply_cb=reply_cb,
                    send_to_thread_cb=self._send_to_thread,
                )
            elif self._music_handler.is_music_command(text):
                logger.debug("Routing message to MusicHandler")
                reply: Optional[str] = await self._music_handler.handle(text, reply_cb)
            else:
                logger.debug("Routing message to GroqHandler")

                # Check if this person is on Arya's bad list — maybe ignore
                if sender_username and self._user_memory.should_ignore(sender_username):
                    logger.info("Ignoring message from bad-listed user @%s", sender_username)
                    return  # silent drop

                # Stranger filter: only reply to known people or if they @mention Arya
                if sender_username:
                    profile = self._user_memory.get_profile(sender_username)
                    is_stranger = profile.get("stranger", True)
                    mentioned = any(
                        kw in text.lower()
                        for kw in ("@aryaa.kiu", "@aryaa", "arya")
                    )
                    if is_stranger and not mentioned:
                        logger.debug("Ignoring stranger @%s (no @mention)", sender_username)
                        return  # silent drop

                # Bump message count and build user context for Groq
                if sender_username:
                    self._user_memory.bump_msg_count(sender_username)
                    user_ctx = self._user_memory.build_context(sender_username)
                else:
                    user_ctx = ""

                result = await self._groq_handler.handle(
                    user_text=text,
                    thread_id=thread_id,
                    sender_username=sender_username,
                    user_context=user_ctx,
                )
                # groq_handler returns (clean_reply, action, memory_updates)
                if isinstance(result, tuple) and len(result) == 3:
                    reply, action, memory_updates = result
                elif isinstance(result, tuple):
                    reply, action = result
                    memory_updates = {}
                else:
                    reply, action, memory_updates = result, None, {}

                # Apply memory updates Arya decided on
                if sender_username and memory_updates:
                    self._user_memory.apply_updates(sender_username, memory_updates)
                    logger.debug("Applied %d memory updates for @%s", len(memory_updates), sender_username)

                if reply:
                    # Add bot reply to convo buffer
                    if thread_id in self._convo_buffers:
                        self._convo_buffers[thread_id].append({
                            "username": self.bot_username,
                            "text": reply,
                            "is_bot": True,
                        })
                    await reply_cb(reply)
                    # Record Arya's reply in persistent recent_activity
                    if sender_username:
                        self._user_memory.push_activity(sender_username, "arya", reply)

                if action:
                    await self._action_handler.execute(
                        action=action,
                        thread_id=thread_id,
                        reply_text=reply or "",
                        convo_buffer=list(self._convo_buffers.get(thread_id, [])),
                        instagram_client=self,
                        reply_cb=reply_cb,
                        owner_username=self._owner_username,
                        sender_username=sender_username or "",
                    )
                return  # early return: we handled reply + action above

            if reply:
                await reply_cb(reply)
        except Exception as e:
            logger.error("Error handling message: %s", e)

    async def _send_reply(self, thread_id: str, text: str) -> None:
        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                lambda: self._client.direct_send(text, thread_ids=[int(thread_id)]),
            )
            logger.debug("Replied to thread %s: %r", thread_id, text)
        except Exception as exc:
            logger.error("Failed to send reply to thread %s: %s", thread_id, exc, exc_info=True)

    async def _send_to_thread(self, thread_id: str, text: str) -> None:
        """Send a message to any thread by ID (used by relay handler)."""
        await self._send_reply(thread_id, text)

    async def _handle_post_command(self, text: str, thread_id: str, sender_username: Optional[str]) -> None:
        """Owner-only: post a photo to Instagram feed. Owner replies to photo with 'post [caption]'."""
        from modules.post_handler import post_to_feed
        import re as _re
        async def reply_cb(msg: str):
            await self._send_reply(thread_id, msg)

        m = _re.match(r'^post\s+(.*)', text, _re.IGNORECASE)
        caption = m.group(1).strip() if m else ""

        # Try to find the last image in this thread from instagrapi
        try:
            loop = asyncio.get_event_loop()
            thread = await loop.run_in_executor(
                None, lambda: self._client.direct_thread(int(thread_id))
            )
            # Find the most recent media message
            photo_path = None
            for msg in thread.messages:
                if msg.item_type in ("media", "clip", "reel_share"):
                    try:
                        media = await loop.run_in_executor(
                            None, lambda: self._client.direct_media_download(msg.media, folder="Photos")
                        )
                        photo_path = Path(media)
                        break
                    except Exception:
                        continue

            if photo_path and photo_path.exists():
                await reply_cb("posting it now...")
                ok = await post_to_feed(self._client, photo_path, caption)
                await reply_cb("posted!" if ok else "something went wrong with the upload")
            else:
                await reply_cb("reply to a photo with `post [caption]` to post it to your feed")
        except Exception as exc:
            logger.error("post command failed: %s", exc)
            await reply_cb("couldn't do it rn, check logs")
