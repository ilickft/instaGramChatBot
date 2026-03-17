"""
post_handler.py — Story card generator + Instagram post/story uploader.

Story card: Renders a "chat screenshot" image using Pillow showing the
conversation participants' usernames and messages on a dark background.
No avatars, no AI — just clean formatted text.
Posts the result to Instagram story or feed via instagrapi.
"""

import asyncio
import logging
import tempfile
from pathlib import Path
from typing import Optional
from collections import deque

logger = logging.getLogger("post_handler")

# ── Story card dimensions (portrait vertical for IG story) ─────────────────
CARD_W  = 1080
CARD_H  = 1920

# ── Colours ────────────────────────────────────────────────────────────────
BG_TOP      = (10,  10,  14)   # near-black top
BG_BOT      = (18,  12,  28)   # deep purple-black bottom
ACCENT_1    = (185, 130, 255)  # soft lavender — other users' names
ACCENT_BOT  = (255, 105, 160)  # pink — Arya's name
TEXT_WHITE  = (240, 240, 245)  # message body
TEXT_DIM    = (140, 130, 155)  # dimmed / branding
BUBBLE_OTH  = (38,  30,  52)   # other users' bubble bg
BUBBLE_ARY  = (58,  22,  60)   # Arya's bubble bg

# ── Typography ─────────────────────────────────────────────────────────────
# Try several Windows/Linux font paths
_FONT_CANDIDATES = [
    "C:/Windows/Fonts/segoeui.ttf",
    "C:/Windows/Fonts/arial.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/TTF/DejaVuSans.ttf",
]
_BOLD_CANDIDATES = [
    "C:/Windows/Fonts/segoeuib.ttf",
    "C:/Windows/Fonts/arialbd.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
]


def _load_font(size: int, bold: bool = False):
    from PIL import ImageFont
    candidates = _BOLD_CANDIDATES if bold else _FONT_CANDIDATES
    for path in candidates:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


# ── Gradient background helper ─────────────────────────────────────────────
def _draw_gradient(img):
    from PIL import Image
    gradient = Image.new("RGB", (CARD_W, CARD_H))
    for y in range(CARD_H):
        t = y / CARD_H
        r = int(BG_TOP[0] + (BG_BOT[0] - BG_TOP[0]) * t)
        g = int(BG_TOP[1] + (BG_BOT[1] - BG_TOP[1]) * t)
        b = int(BG_TOP[2] + (BG_BOT[2] - BG_TOP[2]) * t)
        for x in range(CARD_W):
            gradient.putpixel((x, y), (r, g, b))
    img.paste(gradient)


# ── Text wrapping helper ────────────────────────────────────────────────────
def _wrap_text(text: str, font, max_width: int, draw) -> list[str]:
    """Break text into lines that fit within max_width."""
    words = text.split()
    lines, current = [], ""
    for word in words:
        test = (current + " " + word).strip()
        bbox = draw.textbbox((0, 0), test, font=font)
        if bbox[2] - bbox[0] <= max_width:
            current = test
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines or [""]


# ── Rounded rectangle ──────────────────────────────────────────────────────
def _rounded_rect(draw, xy, radius, fill):
    from PIL import ImageDraw
    x0, y0, x1, y1 = xy
    draw.rectangle([x0 + radius, y0, x1 - radius, y1], fill=fill)
    draw.rectangle([x0, y0 + radius, x1, y1 - radius], fill=fill)
    draw.ellipse([x0, y0, x0 + 2*radius, y0 + 2*radius], fill=fill)
    draw.ellipse([x1 - 2*radius, y0, x1, y0 + 2*radius], fill=fill)
    draw.ellipse([x0, y1 - 2*radius, x0 + 2*radius, y1], fill=fill)
    draw.ellipse([x1 - 2*radius, y1 - 2*radius, x1, y1], fill=fill)


# ── Main card generator ────────────────────────────────────────────────────
def generate_convo_card(
    messages: list[dict],   # [{"username": str, "text": str, "is_bot": bool}]
    bot_username: str = "aryaa.kiu",
) -> Optional[Path]:
    """
    Renders a conversation card as a PNG image.
    Returns a Path to a temp PNG file (caller deletes).
    Returns None on error.

    messages: list of dicts with keys 'username', 'text', 'is_bot'
    """
    try:
        from PIL import Image, ImageDraw

        img  = Image.new("RGB", (CARD_W, CARD_H))
        draw = ImageDraw.Draw(img)
        _draw_gradient(img)

        pad        = 72         # outer horizontal padding
        inner_pad  = 28         # bubble inner padding
        bubble_pad = 32         # gap between bubbles
        inner_w    = CARD_W - 2 * pad

        font_name = _load_font(38, bold=True)
        font_msg  = _load_font(44)
        font_brand = _load_font(36)

        # ── Header ─────────────────────────────────────────────────────────
        y = 120
        header = "funny convo 💀"
        bbox = draw.textbbox((0, 0), header, font=font_name)
        hw = bbox[2] - bbox[0]
        draw.text(((CARD_W - hw) // 2, y), header, font=font_name, fill=ACCENT_1)
        y += 70

        # Thin separator line
        draw.rectangle([pad, y, CARD_W - pad, y + 2], fill=(80, 60, 100))
        y += 40

        # ── Conversation bubbles ────────────────────────────────────────────
        for msg in messages:
            username = msg.get("username", "unknown")
            text     = msg.get("text", "")
            is_bot   = msg.get("is_bot", False)

            name_color   = ACCENT_BOT if is_bot else ACCENT_1
            bubble_color = BUBBLE_ARY if is_bot else BUBBLE_OTH
            display_name = f"@{username}"

            # Wrap message text
            lines = _wrap_text(text, font_msg, inner_w - 2 * inner_pad, draw)

            # Compute bubble height
            name_h  = 48
            msg_h   = len(lines) * 60
            bubble_h = inner_pad + name_h + msg_h + inner_pad

            # Draw bubble
            _rounded_rect(draw, (pad, y, CARD_W - pad, y + bubble_h), 24, bubble_color)

            # Username inside bubble
            draw.text((pad + inner_pad, y + inner_pad), display_name, font=font_name, fill=name_color)

            # Message lines
            ty = y + inner_pad + name_h + 8
            for line in lines:
                draw.text((pad + inner_pad, ty), line, font=font_msg, fill=TEXT_WHITE)
                ty += 60

            y += bubble_h + bubble_pad

            # Stop if we've run out of vertical space
            if y > CARD_H - 200:
                break

        # ── Branding at the bottom ──────────────────────────────────────────
        brand_text = f"@{bot_username}  ✦"
        bbox = draw.textbbox((0, 0), brand_text, font=font_brand)
        bw = bbox[2] - bbox[0]
        draw.text((CARD_W - pad - bw, CARD_H - 120), brand_text, font=font_brand, fill=TEXT_DIM)

        # Save to temp PNG
        tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False, prefix="arya_story_")
        tmp_path = Path(tmp.name)
        tmp.close()
        img.save(str(tmp_path), "PNG")
        logger.debug("Story card saved → %s", tmp_path.name)
        return tmp_path

    except Exception as exc:
        logger.error("Story card generation failed: %s", exc, exc_info=True)
        return None


# ── Instagram media helpers ─────────────────────────────────────────────────
async def post_to_story(client, image_path: Path) -> bool:
    """Upload a photo to Instagram story. Returns True on success."""
    try:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            lambda: client.photo_upload_to_story(str(image_path))
        )
        logger.info("Posted story: %s", image_path.name)
        return True
    except Exception as exc:
        logger.error("Story upload failed: %s", exc)
        return False


async def post_to_feed(client, image_path: Path, caption: str = "") -> bool:
    """Upload a photo to Instagram feed. Returns True on success."""
    try:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            lambda: client.photo_upload(str(image_path), caption=caption)
        )
        logger.info("Posted to feed with caption: %r", caption[:60])
        return True
    except Exception as exc:
        logger.error("Feed upload failed: %s", exc)
        return False
