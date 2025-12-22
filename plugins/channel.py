# --| This code created by: Jisshu_bots & SilentXBotz |--#

import re
import hashlib
import asyncio
import aiohttp

from typing import Optional
from collections import defaultdict

from pyrogram import Client, filters
from pyrogram import enums

from info import *
from utils import *

from database.users_chats_db import db
from database.ia_filterdb import save_file, unpack_new_file_id


# ================= CONFIG ================= #

CAPTION_LANGUAGES = [
    "Bhojpuri","Hindi","Bengali","Tamil","English","Bangla","Telugu",
    "Malayalam","Kannada","Marathi","Punjabi","Bengoli","Gujrati",
    "Korean","Gujarati","Spanish","French","German","Chinese","Arabic",
    "Portuguese","Russian","Japanese","Odia","Assamese","Urdu",
]

POST_DELAY = 10

media_filter = filters.document | filters.video | filters.audio

notified_movies = set()
movie_files = defaultdict(list)
processing_movies = set()


UPDATE_CAPTION = """<b>𝖭𝖤𝖶 {} 𝖠𝖣𝖣𝖤𝖣 ✅</b>

🎬 <b>{} {}</b>

🔰 <b>Quality:</b> {}
🎧 <b>Audio:</b> {}

<b>✨ Telegram Files ✨</b>

{}

<blockquote>〽️ Powered by @BSHEGDE5</blockquote>
"""


# ================= HANDLER ================= #

@Client.on_message(media_filter)
async def media(bot, message):

    # 🔐 SAFE CHANNEL CHECK (FIX)
    if message.chat.id not in CHANNELS:
        return

    bot_id = bot.me.id
    media = getattr(message, message.media.value, None)

    if not media:
        return

    if media.mime_type not in ["video/mp4", "video/x-matroska", "document/mp4"]:
        return

    media.file_type = message.media.value
    media.caption = message.caption

    success_sts = await save_file(media)

    if success_sts == "suc" and await db.get_send_movie_update_status(bot_id):
        await queue_movie_file(bot, media)


# ================= QUEUE ================= #

async def queue_movie_file(bot, media):
    try:
        file_name = await movie_name_format(media.file_name)
        caption = await movie_name_format(media.caption or "")

        year_match = re.search(r"\b(19|20)\d{2}\b", caption)
        year = year_match.group(0) if year_match else None

        season_match = re.search(r"(?i)(?:s|season)0*(\d{1,2})", caption)

        if year:
            file_name = file_name[:file_name.find(year)+4]
        elif season_match:
            season = season_match.group(1)
            file_name = file_name[:file_name.find(season)+1]

        quality = await get_qualities(caption)
        jisshuquality = await Jisshu_qualities(caption, media.file_name)

        language = ", ".join(
            [l for l in CAPTION_LANGUAGES if l.lower() in caption.lower()]
        ) or "Not Idea"

        file_size = format_file_size(media.file_size)
        file_id, _ = unpack_new_file_id(media.file_id)

        movie_files[file_name].append({
            "quality": quality,
            "jisshuquality": jisshuquality,
            "file_id": file_id,
            "file_size": file_size,
            "caption": caption,
            "language": language,
            "year": year,
        })

        if file_name in processing_movies:
            return

        processing_movies.add(file_name)
        await asyncio.sleep(POST_DELAY)

        if file_name in movie_files:
            await send_movie_update(bot, file_name, movie_files[file_name])
            del movie_files[file_name]

        processing_movies.discard(file_name)

    except Exception as e:
        processing_movies.discard(file_name)
        await bot.send_message(LOG_CHANNEL, f"Movie Queue Error:\n<code>{e}</code>")


# ================= POST ================= #

async def send_movie_update(bot, file_name, files):
    try:
        if file_name in notified_movies:
            return
        notified_movies.add(file_name)

        imdb = await get_imdb(file_name)
        title = imdb.get("title", file_name)
        kind = imdb.get("kind", "MOVIE").upper().replace(" ", "_")
        year = imdb.get("year", "")

        poster = await fetch_movie_poster(title, year)

        quality_text = ""
        for f in files:
            link = f"<a href='https://t.me/{temp.U_NAME}?start=file_0_{f['file_id']}'>{f['file_size']}</a>"
            quality_text += f"📦 {f['jisshuquality']} : {link}\n"

        caption = UPDATE_CAPTION.format(
            kind,
            title,
            year or "",
            files[0]["quality"],
            files[0]["language"],
            quality_text
        )

        channel_id = await db.movies_update_channel_id() or MOVIE_UPDATE_CHANNEL

        await bot.send_photo(
            chat_id=channel_id,
            photo=poster or "https://te.legra.ph/file/88d845b4f8a024a71465d.jpg",
            caption=caption,
            parse_mode=enums.ParseMode.HTML
        )

    except Exception as e:
        await bot.send_message(LOG_CHANNEL, f"Post Error:\n<code>{e}</code>")


# ================= HELPERS ================= #

async def get_imdb(name):
    try:
        data = await get_poster(name)
        return data or {}
    except:
        return {}


async def fetch_movie_poster(title, year=None):
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"https://jisshuapis.vercel.app/api.php?query={title.replace(' ', '+')}",
                timeout=5
            ) as r:
                js = await r.json()
                for k in ["jisshu-2","jisshu-3","jisshu-4"]:
                    if js.get(k):
                        return js[k][0]
    except:
        return None


async def get_qualities(text):
    for q in ["2160p","1080p","720p","480p","HDRip","CAMRip","WEB-DL"]:
        if q.lower() in text.lower():
            return q
    return "HDRip"


async def Jisshu_qualities(text, name):
    for q in ["2160p","1080p","720p","480p"]:
        if q in (text + name):
            return q
    return "720p"


async def movie_name_format(name):
    if not name:
        return ""
    return re.sub(r"[^\w\s]", " ", name).strip()


def format_file_size(size):
    for unit in ["B","KB","MB","GB","TB"]:
        if size < 1024:
            return f"{size:.2f} {unit}"
        size /= 1024
    return "0 MB"
        
