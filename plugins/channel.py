# --| UI Modified & Logs Added |--#
# --| Title + Year Detection Added |--#
# --| Original Logic Intact |--#

import re
import hashlib
import asyncio
from info import *
from utils import *
from pyrogram import Client, filters, enums
from database.users_chats_db import db
from database.ia_filterdb import save_file, unpack_new_file_id
import aiohttp
from typing import Optional
from collections import defaultdict

print("✅ Channel.py Loaded Successfully")

CAPTION_LANGUAGES = [
    "Bhojpuri","Hindi","Bengali","Tamil","English","Bangla","Telugu",
    "Malayalam","Kannada","Marathi","Punjabi","Gujarati","Korean",
    "Spanish","French","German","Chinese","Arabic","Portuguese",
    "Russian","Japanese","Odia","Assamese","Urdu",
]

# ================= UI CAPTION ================= #

UPDATE_CAPTION = """<b>🎬 NEW {}</b>

<b>📀 Title :</b> {} {}
<b>🎧 Audio :</b> {}
<b>📺 Source :</b> {}

━━━━━━━━━━━━━━━━━━
<b>📦 Available Files</b>
━━━━━━━━━━━━━━━━━━

{}

<blockquote>⚡ Powered by @BSHEGDE5</blockquote>
"""

QUALITY_CAPTION = "• {} ➜ {}\n"

# ================= GLOBALS ================= #

notified_movies = set()
movie_files = defaultdict(list)
processing_movies = set()
POST_DELAY = 10

media_filter = filters.document | filters.video | filters.audio

# ================= MEDIA HANDLER ================= #

@Client.on_message(filters.chat(CHANNELS) & media_filter)
async def media(bot, message):
    print("📥 File received")

    media = getattr(message, message.media.value, None)

    if media.mime_type in ["video/mp4", "video/x-matroska", "document/mp4"]:
        media.file_type = message.media.value
        media.caption = message.caption

        success_sts = await save_file(media)

        if success_sts == "suc":
            print("💾 File saved in database")

            if await db.get_send_movie_update_status(bot.me.id):
                await queue_movie_file(bot, media)

# ================= QUEUE ================= #

async def queue_movie_file(bot, media):
    try:
        print("⏳ Group wait started")

        raw_name = await movie_name_format(media.file_name)
        caption = await movie_name_format(media.caption)

        # 🎯 TITLE + YEAR DETECTION
        year_match = re.search(r"\b(19|20)\d{2}\b", raw_name)
        year = year_match.group(0) if year_match else None

        if year:
            title = raw_name.split(year)[0].strip()
        else:
            title = raw_name

        quality = await get_qualities(caption) or "HDRip"
        j_quality = await Jisshu_qualities(caption, media.file_name)

        language = (
            ", ".join([l for l in CAPTION_LANGUAGES if l.lower() in caption.lower()])
            or "Unknown"
        )

        file_size = format_file_size(media.file_size)
        file_id, _ = unpack_new_file_id(media.file_id)

        movie_files[title].append({
            "file_id": file_id,
            "quality": j_quality,
            "size": file_size,
            "language": language,
            "year": year,
            "caption": caption
        })

        if title in processing_movies:
            return

        processing_movies.add(title)
        await asyncio.sleep(POST_DELAY)

        await send_movie_update(bot, title, movie_files[title])
        del movie_files[title]
        processing_movies.remove(title)

    except Exception as e:
        print(f"❌ Queue Error : {e}")

# ================= POST ================= #

async def send_movie_update(bot, title, files):
    try:
        if title in notified_movies:
            return

        notified_movies.add(title)
        print("📝 Post created")

        imdb_data = await get_imdb(title)
        imdb_title = imdb_data.get("title", title)
        kind = imdb_data.get("kind", "Movie").upper()

        year = files[0]["year"] or imdb_data.get("year") or ""

        poster = await fetch_movie_poster(imdb_title, year)
        poster = poster or "https://te.legra.ph/file/88d845b4f8a024a71465d.jpg"

        quality_text = ""
        for f in files:
            link = (
                f"<a href='https://t.me/{temp.U_NAME}?start=file_0_{f['file_id']}'>"
                f"{f['quality']} ({f['size']})</a>"
            )
            quality_text += QUALITY_CAPTION.format(f["quality"], link)

        caption = UPDATE_CAPTION.format(
            kind,
            imdb_title,
            year,
            files[0]["language"],
            "WEB-DL",
            quality_text
        )

        channel = await db.movies_update_channel_id() or MOVIE_UPDATE_CHANNEL

        await bot.send_photo(
            chat_id=channel,
            photo=poster,
            caption=caption,
            parse_mode=enums.ParseMode.HTML
        )

        print("✏️ Post sent successfully")

    except Exception as e:
        print(f"❌ Post Error : {e}")

# ================= HELPERS (UNCHANGED) ================= #

async def get_imdb(name):
    try:
        imdb = await get_poster(name)
        return imdb or {}
    except:
        return {}

async def fetch_movie_poster(title: str, year: Optional[int] = None):
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(
                f"https://jisshuapis.vercel.app/api.php?query={title.replace(' ', '+')}",
                timeout=5
            ) as r:
                if r.status != 200:
                    return None
                data = await r.json()
                for k in ["jisshu-2","jisshu-3","jisshu-4"]:
                    if data.get(k):
                        return data[k][0]
        except:
            return None

async def get_qualities(text):
    for q in ["480p","720p","1080p","2160p","WEB-DL","HDRip"]:
        if q.lower() in text.lower():
            return q
    return "720p"

async def Jisshu_qualities(text, file_name):
    text = (text + file_name).lower()
    for q in ["2160p","1080p","720p","480p"]:
        if q in text:
            return q
    return "720p"

async def movie_name_format(name):
    return re.sub(r"[^A-Za-z0-9 ]+", " ", name).strip()

def format_file_size(size):
    for unit in ["B","KB","MB","GB","TB"]:
        if size < 1024:
            return f"{size:.2f} {unit}"
        size /= 1024
