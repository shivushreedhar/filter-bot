# --| FINAL CHANNEL.PY (STABLE & DB SAFE) |--#

import re
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

UPDATE_CAPTION = """<b>🎬 NEW {}</b>

<b>📀 Title :</b> {} {}
<b>🎧 Audio :</b> {}
<b>📺 Source :</b> WEB-DL

━━━━━━━━━━━━━━━━━━
<b>📦 Available Files</b>
━━━━━━━━━━━━━━━━━━

{}

<blockquote>⚡ Powered by @BSHEGDE5</blockquote>
"""

QUALITY_LINE = "• {} ➜ {}\n"

POST_DELAY = 10
media_filter = filters.document | filters.video | filters.audio

movie_files = defaultdict(list)
processing_movies = set()

# title|year → message_id (runtime cache)
posted_messages = {}


# ================= MEDIA ================= #

@Client.on_message(filters.chat(CHANNELS) & media_filter)
async def media(bot, message):
    print("📥 File received")

    media = getattr(message, message.media.value, None)

    if media.mime_type in ("video/mp4", "video/x-matroska", "document/mp4"):
        media.file_type = message.media.value
        media.caption = message.caption

        if await save_file(media) == "suc":
            print("💾 File saved in database")
            await queue_movie_file(bot, media)


# ================= QUEUE ================= #

async def queue_movie_file(bot, media):
    try:
        print("⏳ Group wait started")

        raw_name = await movie_name_format(media.file_name)
        caption = await movie_name_format(media.caption)

        year_match = re.search(r"\b(19|20)\d{2}\b", raw_name)
        year = year_match.group(0) if year_match else None
        title = raw_name.split(year)[0].strip() if year else raw_name

        quality = await Jisshu_qualities(caption, media.file_name)
        language = ", ".join(
            l for l in CAPTION_LANGUAGES if l.lower() in caption.lower()
        ) or "Unknown"

        size = format_file_size(media.file_size)

        # ✅ Keep BOTH for DB safety
        file_id, file_ref = unpack_new_file_id(media.file_id)

        movie_files[title].append({
            "file_id": file_id,
            "file_ref": file_ref,
            "quality": quality,
            "size": size,
            "language": language,
            "year": year
        })

        if title in processing_movies:
            return

        processing_movies.add(title)
        await asyncio.sleep(POST_DELAY)

        await send_movie_update(bot, title, movie_files[title])

        del movie_files[title]
        processing_movies.remove(title)

    except Exception as e:
        print(f"❌ Queue Error: {e}")


# ================= POST / EDIT ================= #

async def send_movie_update(bot, title, files):
    try:
        imdb = await get_imdb(title)
        movie_title = imdb.get("title", title)
        kind = imdb.get("kind", "Movie").upper()
        year = files[0]["year"] or imdb.get("year") or ""

        key = f"{movie_title}|{year}"

        poster = await fetch_movie_poster(movie_title, year)
        poster = poster or "https://te.legra.ph/file/88d845b4f8a024a71465d.jpg"

        # ✅ WORKING DEEP LINK (OLD FORMAT)
        quality_text = ""
        for f in files:
            link = (
                f"<a href='https://t.me/{temp.U_NAME}"
                f"?start=file_0_{f['file_id']}'>"
                f"{f['quality']} ({f['size']})</a>"
            )
            quality_text += QUALITY_LINE.format(f["quality"], link)

        caption = UPDATE_CAPTION.format(
            kind,
            movie_title,
            year,
            files[0]["language"],
            quality_text
        )

        channel = await db.movies_update_channel_id()
        if not channel or channel == 0:
            channel = MOVIE_UPDATE_CHANNEL
        channel = int(channel)

        # 🔥 Meet peer to avoid PEER_ID_INVALID
        await bot.get_chat(channel)

        # ✏️ TRY EDIT FIRST
        if key in posted_messages:
            try:
                print("✏️ Editing existing post")
                await bot.edit_message_media(
                    chat_id=channel,
                    message_id=posted_messages[key],
                    media=enums.InputMediaPhoto(
                        media=poster,
                        caption=caption,
                        parse_mode=enums.ParseMode.HTML
                    )
                )
                print("✅ Post edited")
                return
            except Exception as e:
                print(f"⚠️ Edit failed, creating new post: {e}")

        # 🆕 CREATE NEW POST
        print("📝 Creating new post")
        msg = await bot.send_photo(
            chat_id=channel,
            photo=poster,
            caption=caption,
            parse_mode=enums.ParseMode.HTML
        )

        posted_messages[key] = msg.id
        print("✅ Posted successfully")

    except Exception as e:
        print(f"❌ Post Error: {e}")


# ================= HELPERS ================= #

async def get_imdb(name):
    try:
        return await get_poster(name) or {}
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
                for k in ("jisshu-2","jisshu-3","jisshu-4"):
                    if data.get(k):
                        return data[k][0]
        except:
            return None

async def Jisshu_qualities(text, file_name):
    text = (text + file_name).lower()
    for q in ("2160p","1080p","720p","480p"):
        if q in text:
            return q
    return "720p"

async def movie_name_format(name):
    return re.sub(r"[^A-Za-z0-9 ]+", " ", name).strip()

def format_file_size(size):
    for unit in ("B","KB","MB","GB","TB"):
        if size < 1024:
            return f"{size:.2f} {unit}"
        size /= 1024
