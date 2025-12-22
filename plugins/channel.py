# ================= FINAL channel.py =================
# Pyrogram v2 SAFE
# Document caption bug FIXED permanently
# Saves file + posts to MUC

import re
import asyncio
from collections import defaultdict

from pyrogram import Client, filters, enums

from info import CHANNELS, MOVIE_UPDATE_CHANNEL, LOG_CHANNEL
from database.ia_filterdb import save_file, unpack_new_file_id

print("✅ FINAL FIXED channel.py LOADED")

# --------------------------------------------------
# CONFIG
# --------------------------------------------------

GROUP_DELAY = 25  # seconds to group same movie files
movie_queue = defaultdict(list)
processing = set()

# --------------------------------------------------
# MEDIA HANDLER
# --------------------------------------------------

@Client.on_message(
    filters.chat(CHANNELS)
    & (filters.document | filters.video | filters.audio)
)
async def media_handler(bot, message):
    try:
        print("📥 MEDIA RECEIVED FROM:", message.chat.id)

        media = message.document or message.video or message.audio
        if not media or not media.file_name:
            return

        # ✅ ONLY CORRECT WAY
        caption = message.caption or media.file_name

        status = await save_file(media)
        if status != "suc":
            print("❌ FILE SAVE FAILED")
            return

        print("✅ FILE SAVED")

        await queue_movie(bot, media, caption)

    except Exception as e:
        print("❌ MEDIA HANDLER ERROR:", e)
        try:
            await bot.send_message(LOG_CHANNEL, f"MEDIA HANDLER ERROR:\n{e}")
        except:
            pass

# --------------------------------------------------
# QUEUE & GROUP
# --------------------------------------------------

async def queue_movie(bot, media, caption):
    name = clean_name(media.file_name)

    file_id, _ = unpack_new_file_id(media.file_id)
    size = format_size(media.file_size)
    quality = detect_quality(caption)

    movie_queue[name].append({
        "file_id": file_id,
        "size": size,
        "quality": quality
    })

    if name in processing:
        return

    processing.add(name)
    await asyncio.sleep(GROUP_DELAY)

    try:
        await post_to_muc(bot, name, movie_queue[name])
    finally:
        movie_queue.pop(name, None)
        processing.discard(name)

# --------------------------------------------------
# POST TO MOVIE UPDATE CHANNEL
# --------------------------------------------------

async def post_to_muc(bot, name, files):
    print("🚀 POSTING TO MUC:", name)

    lines = []
    for f in files:
        link = (
            f"<a href='https://t.me/{bot.me.username}"
            f"?start=file_0_{f['file_id']}'>"
            f"{f['size']}</a>"
        )
        lines.append(f"📦 {f['quality']} : {link}")

    caption = (
        f"<b>🎬 NEW MOVIE ADDED</b>\n\n"
        f"<b>{name}</b>\n\n"
        f"{chr(10).join(lines)}\n\n"
        f"<blockquote>〽️ Powered by @BSHEGDE5</blockquote>"
    )

    await bot.send_message(
        chat_id=MOVIE_UPDATE_CHANNEL,
        text=caption,
        parse_mode=enums.ParseMode.HTML
    )

    print("✅ POSTED TO MUC")

# --------------------------------------------------
# HELPERS
# --------------------------------------------------

def detect_quality(text):
    for q in ["2160p", "1080p", "720p", "480p"]:
        if q.lower() in text.lower():
            return q
    return "720p"


def clean_name(text):
    text = re.sub(r"[^\w\s]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def format_size(size):
    for unit in ["B", "KB", "MB", "GB"]:
        if size < 1024:
            return f"{size:.2f} {unit}"
        size /= 1024
    return f"{size:.2f} TB"
