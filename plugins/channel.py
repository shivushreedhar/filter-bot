# --| This code fixed by ChatGPT |--
# --| Original base: Jisshu_bots & SilentXBotz |--

import re
import hashlib
import asyncio
import aiohttp

from typing import Optional
from collections import defaultdict

from pyrogram import Client, filters, enums

from info import *
from utils import *
from database.users_chats_db import db
from database.ia_filterdb import save_file, unpack_new_file_id


# ================= CONFIG ================= #

POST_DELAY = 5  # seconds (safe)
MOVIE_POST_LOCK = set()

CAPTION_LANGUAGES = [
    "Bhojpuri", "Hindi", "Bengali", "Tamil", "English", "Telugu",
    "Malayalam", "Kannada", "Marathi", "Punjabi", "Gujarati",
    "Korean", "Spanish", "French", "German", "Chinese",
    "Arabic", "Portuguese", "Russian", "Japanese", "Urdu"
]

UPDATE_CAPTION = """<b>𝖭𝖤𝖶 {} 𝖠𝖣𝖣𝖤𝖣 ✅</b>

🎬 <b>{} {}</b>
🔰 <b>Quality:</b> {}
🎧 <b>Audio:</b> {}

<b>✨ Telegram Files ✨</b>

{}

<b>〽️ Powered by @BSHEGDE5</b>
"""

media_filter = filters.document | filters.video | filters.audio

movie_files = defaultdict(list)


# ================= MEDIA HANDLER ================= #

@Client.on_message(filters.chat(CHANNELS) & media_filter)
async def media_handler(bot, message):
    try:
        print("📥 MEDIA RECEIVED FROM:", message.chat.id)

        media = getattr(message, message.media.value, None)
        if not media:
            return

        if media.mime_type not in [
            "video/mp4", "video/x-matroska", "application/octet-stream"
        ]:
            return

        media.file_type = message.media.value
        media.caption = message.caption or ""

        status = await save_file(media)
        print("💾 SAVE STATUS:", status)

        if status == "suc":
            await queue_movie(bot, media)

    except Exception as e:
        print("❌ MEDIA HANDLER ERROR:", e)
        await bot.send_message(LOG_CHANNEL, f"MEDIA HANDLER ERROR:\n{e}")


# ================= QUEUE ================= #

async def queue_movie(bot, media):
    file_name = await movie_name_format(media.file_name)
    caption = await movie_name_format(media.caption or media.file_name)

    year_match = re.search(r"\b(19|20)\d{2}\b", caption)
    year = year_match.group(0) if year_match else ""

    quality = await Jisshu_qualities(caption, media.file_name)
    language = ", ".join([l for l in CAPTION_LANGUAGES if l.lower() in caption.lower()]) or "Unknown"

    file_id, _ = unpack_new_file_id(media.file_id)
    size = format_file_size(media.file_size)

    movie_files[file_name].append({
        "file_id": file_id,
        "quality": quality,
        "size": size,
        "caption": caption,
        "language": language,
        "year": year
    })

    if file_name in MOVIE_POST_LOCK:
        print("⏳ GROUPING:", file_name)
        return

    MOVIE_POST_LOCK.add(file_name)

    await asyncio.sleep(POST_DELAY)

    try:
        await send_movie_update(bot, file_name, movie_files[file_name])
    finally:
        movie_files.pop(file_name, None)
        MOVIE_POST_LOCK.discard(file_name)


# ================= POST ================= #

async def send_movie_update(bot, movie_name, files):
    try:
        print("🚀 POSTING TO MUC:", movie_name)

        imdb = await get_imdb(movie_name)
        title = imdb.get("title", movie_name)
        kind = imdb.get("kind", "MOVIE").upper().replace(" ", "_")

        poster = await fetch_movie_poster(title)
        poster = poster or "https://te.legra.ph/file/88d845b4f8a024a71465d.jpg"

        quality_lines = []
        for f in files:
            link = f"<a href='https://t.me/{temp.U_NAME}?start=file_0_{f['file_id']}'>{f['size']}</a>"
            quality_lines.append(f"📦 {f['quality']} : {link}")

        caption = UPDATE_CAPTION.format(
            kind,
            title,
            files[0]["year"],
            files[0]["quality"],
            files[0]["language"],
            "\n".join(quality_lines)
        )

        await bot.send_photo(
            chat_id=MOVIE_UPDATE_CHANNEL,
            photo=poster,
            caption=caption,
            parse_mode=enums.ParseMode.HTML
        )

        print("✅ POST SUCCESS:", movie_name)

    except Exception as e:
        print("❌ POST FAILED:", e)
        await bot.send_message(LOG_CHANNEL, f"POST FAILED:\n{e}")


# ================= HELPERS ================= #

async def get_imdb(name):
    try:
        data = await get_poster(name)
        if not data:
            return {}
        return {
            "title": data.get("title"),
            "kind": data.get("kind"),
            "year": data.get("year")
        }
    except:
        return {}


async def fetch_movie_poster(title):
    async with aiohttp.ClientSession() as session:
        try:
            url = f"https://jisshuapis.vercel.app/api.php?query={title.replace(' ', '+')}"
            async with session.get(url, timeout=5) as r:
                data = await r.json()
                for k in ("jisshu-2", "jisshu-3", "jisshu-4"):
                    if data.get(k):
                        return data[k][0]
        except:
            return None


async def Jisshu_qualities(text, file):
    for q in ["2160p", "1080p", "720p", "480p"]:
        if q.lower() in (text + file).lower():
            return q
    return "720p"


async def movie_name_format(text):
    return re.sub(r"[^\w\s]", " ", text).replace("_", " ").strip()


def format_file_size(size):
    for unit in ["B", "KB", "MB", "GB"]:
        if size < 1024:
            return f"{size:.2f} {unit}"
        size /= 1024
    return f"{size:.2f} TB"
