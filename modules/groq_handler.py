import os
import re
import random
import asyncio
from groq import AsyncGroq, RateLimitError
from modules.action_handler import parse_action
from modules.music_handler import _to_small_caps
from dotenv import load_dotenv
import logging

logger = logging.getLogger("groq_handler")

# ── [MEMORY:key=value] tag regex ──────────────────────────────────────────────
_MEMORY_RE = re.compile(r'\[MEMORY:(\w+)=([^\]]*)\]', re.IGNORECASE)

def parse_memory_updates(text: str):
    """
    Extract all [MEMORY:key=value] tags from text.
    Handles comma-separated tags like [MEMORY:key=val, MEMORY:key2=val2] inside a single block.
    Returns (clean_text, updates_dict).
    """
    updates = {}
    for m in _MEMORY_RE.finditer(text):
        first_key = m.group(1).lower()
        raw_val = m.group(2).strip()
        
        # Split by comma explicitly preceding "MEMORY:" (insulates natural commas in text values)
        parts = re.split(r',\s*MEMORY:', raw_val, flags=re.IGNORECASE)
        
        # Process the first value belonging to first_key
        main_val = parts[0].strip()
        if main_val.lower() in ("true", "yes"): main_val = True
        elif main_val.lower() in ("false", "no"): main_val = False
        updates[first_key] = main_val
        
        # Process subsequent key=value pairs extracted from raw_val
        for part in parts[1:]:
            if '=' in part:
                k, v = part.split('=', 1)
                k = k.strip().lower()
                v = v.strip()
                if v.lower() in ("true", "yes"): v = True
                elif v.lower() in ("false", "no"): v = False
                updates[k] = v

    clean = _MEMORY_RE.sub("", text).strip()
    return clean, updates


class GroqHandler:
    def __init__(self):
        load_dotenv()
        
        self.model_name = "llama-3.3-70b-versatile"
        
        # Load Groq API keys
        self.clients = []
        for i in range(1, 8):
            key = os.getenv(f'GROQ_API_KEY_{i}')
            if key:
                self.clients.append(AsyncGroq(api_key=key))
                
        if not self.clients:
            logger.warning("No GROQ_API_KEY_x found in environment variables. Groq features will not work.")
            
        # Load system prompt
        system_prompt_file = os.getenv("SYSTEM_PROMPT_FILE", "system_prompt.txt")
        try:
            with open(system_prompt_file, 'r', encoding='utf-8') as f:
                system_content = f.read().strip()
            self._base_system_content = system_content
        except FileNotFoundError:
            logger.warning(f"Error: {system_prompt_file} not found. Using default prompt.")
            self._base_system_content = "You are a helpful assistant."
            
        # User sessions storage (Key: thread_id, Value: list of messages)
        self.sessions = {}
        self.processing_threads = {}

    def _build_system_prompt(self, user_context: str = "") -> dict:
        """Build system prompt, optionally injecting per-user context."""
        content = self._base_system_content
        if user_context:
            content = f"{content}\n\n--- User Context ---\n{user_context}"
        return {"role": "system", "content": content}

    async def handle(
        self,
        user_text: str,
        thread_id: str,
        sender_username: str = None,
        reply_cb=None,
        user_context: str = "",   # injected from UserMemory.build_context()
    ):
        """Process AI response. Returns (clean_reply, action, memory_updates)."""
        if not self.clients:
            logger.error("No AI API keys configured.")
            return "Error: No AI API keys configured.", None, {}
            
        # Prevent concurrent processing per thread
        if self.processing_threads.get(thread_id):
            logger.debug(f"Already processing a message for thread {thread_id}, ignoring.")
            return None, None, {}
            
        self.processing_threads[thread_id] = True
            
        try:
            # Build system prompt with user context injected
            system_prompt = self._build_system_prompt(user_context)

            # Initialize session if new thread
            if thread_id not in self.sessions:
                self.sessions[thread_id] = [system_prompt]
            else:
                # Always refresh the system prompt at position 0 with latest user context
                self.sessions[thread_id][0] = system_prompt
                
            # Add user message to history
            msg_content = f"{sender_username} says: {user_text}" if sender_username else user_text
            
            # Combine consecutive user messages to prevent Llama-3 API 400 Bad Request
            if len(self.sessions[thread_id]) > 1 and self.sessions[thread_id][-1]["role"] == "user":
                self.sessions[thread_id][-1]["content"] += f"\n\n{msg_content}"
            else:
                self.sessions[thread_id].append({"role": "user", "content": msg_content})
            
            # Simulate typing delay removed for faster responses            
            # Shuffle clients to load balance across API keys
            clients_shuffled = list(self.clients)
            random.shuffle(clients_shuffled)
            
            # Try each client until success
            for i, client in enumerate(clients_shuffled):
                try:
                    completion = await client.chat.completions.create(
                        model=self.model_name,
                        messages=self.sessions[thread_id],
                        temperature=0.7,
                        max_tokens=300,  # slightly more room for memory tags
                    )
                    logger.debug(f"Successfully generated response using API key {i+1}")
                    
                    ai_response = completion.choices[0].message.content

                    # 1. Strip [ACTION:xxx] tag
                    after_action, action = parse_action(ai_response)

                    # 2. Strip [MEMORY:key=value] tags
                    clean_reply, memory_updates = parse_memory_updates(after_action)
                    
                    # Add CLEAN response to history
                    self.sessions[thread_id].append({"role": "assistant", "content": clean_reply})
                    
                    # Keep history short (last 10 messages + system prompt)
                    if len(self.sessions[thread_id]) > 11:
                        self.sessions[thread_id] = [system_prompt] + self.sessions[thread_id][-10:]
                        
                    return clean_reply, action, memory_updates
                    
                except Exception as api_err:
                    logger.warning(f"API key failed ({type(api_err).__name__}), trying next...")
                    if i == len(clients_shuffled) - 1:
                        raise api_err
                    continue

        except RateLimitError as e:
            logger.error(f"All Groq API keys rate limited: {e}")
            return _to_small_caps("I'm a little overwhelmed rn, try again in a sec"), None, {}
        except Exception as e:
            logger.error(f"Error generating AI response: {e}", exc_info=True)
            return _to_small_caps("some internal shit happened wait a sec 🥀"), None, {}
        finally:
            self.processing_threads[thread_id] = False
            
        return None, None, {}
