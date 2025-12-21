# --| This code created by: Jisshu_bots & SilentXBotz |--#

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

# ================= LOG HELPER =================
def log(msg):
    print(f"[KOYEB] {msg}")

# ================= UI =================
MOVIE_UI = """🎬 <b>{title} ({year})</b>

🔊 <b>Audio :</b> {language}
📀 <b>Source :</b> WEB-DL

⬇️ <b>Available Qualities</b>
━━━━━━━━━━━━━━
{links}

<blockquote>⚡ Powered by @BSHEGDE5</blockquote>
"""

SERIES_UI = """📺 <b>{title} ({year})</b>

🔊 <b>Audio :</b> {language}
📀 <b>Source :</b> WEB-DL

⬇️ <b>Episodes</b>
━━━━━━━━━━━━━━
{links}

<blockquote>⚡ Powered by @BSHEGDE5</blockquote>
"""

CAPTION_LANGUAGES = [
    "Hindi","Tamil","Telugu","Malayalam","Kannada","English",
    "Bengali","Marathi","Punjabi","Gujarati","Spanish","French"
]

notified_movies = set()
movie_files = defaultdict(list)
POST_DELAY = 25
processing_movies = set()

media_filter = filters.document | filters.video | filters.audio


@Client.on_message(filters.chat(CHANNELS) & media_filter)
async def media(bot, message):
    log("FILE RECEIVED")

    media = getattr(message, message.media.value, None)
    if media.mime_type in ["video/mp4", "video/x-matroska", "document/mp4"]:
        media.file_type = message.media.value
        media.caption = message.caption

        success = await save_file(media)
        if success == "suc":
            log("FILE SAVED")

        if success == "suc" and await db.get_send_movie_update_status(bot.me.id):
            await queue_movie_file(bot, media)


async def queue_movie_file(bot, media):
    file_name = await movie_name_format(media.file_name)
    caption = await movie_name_format(media.caption)

    log(f"GROUP ADD → {file_name}")

    quality = await Jisshu_qualities(caption, media.file_name)
    language = ", ".join(
        [l for l in CAPTION_LANGUAGES if l.lower() in caption.lower()]
    ) or "Kan"

    file_id, _ = unpack_new_file_id(media.file_id)
    movie_files[file_name].append({
        "file_id": file_id,
        "quality": quality,
        "size": format_file_size(media.file_size),
        "caption": caption,
        "language": language
    })

    if file_name in processing_movies:
        return

    processing_movies.add(file_name)
    log("GROUP WAIT 25s")

    await asyncio.sleep(POST_DELAY)

    await send_movie_update(bot, file_name, movie_files[file_name])
    movie_files.pop(file_name, None)
    processing_movies.remove(file_name)


async def send_movie_update(bot, file_name, files):
    if file_name in notified_movies:
        return

    notified_movies.add(file_name)
    log("POST CREATE")

    imdb = await get_imdb(file_name)
    title = imdb.get("title", file_name)
    year = imdb.get("year", "")
    kind = imdb.get("kind", "MOVIE").upper()

    poster = await fetch_movie_poster(title, year)

    links = ""
    for f in files:
        links += f"⭐ {f['quality']} – <a href='https://t.me/{temp.U_NAME}?start=file_0_{f['file_id']}'>{f['size']}</a>\n"

    caption = (
        SERIES_UI if kind == "TV_SERIES" else MOVIE_UI
    ).format(
        title=title,
        year=year,
        language=files[0]["language"],
        links=links
    )

    await bot.send_photo(
        chat_id=MOVIE_UPDATE_CHANNEL,
        photo=poster,
        caption=caption,
        parse_mode=enums.ParseMode.HTML
    )

    log("POST EDITED")


# ================= HELPERS (UNCHANGED) =================

async def get_imdb(name):
    imdb = await get_poster(name)
    if not imdb:
        return {}
    return imdb


async def fetch_movie_poster(title, year=None):
    async with aiohttp.ClientSession() as s:
        async with s.get(
            f"https://jisshuapis.vercel.app/api.php?query={title.replace(' ','+')}"
        ) as r:
            if r.status == 200:
                j = await r.json()
                for k in ["jisshu-2","jisshu-3","jisshu-4"]:
                    if j.get(k):
                        return j[k][0]
    return "https://te.legra.ph/file/88d845b4f8a024a71465d.jpg"


async def movie_name_format(name):
    return re.sub(r"[^a-zA-Z0-9 ]"," ",name).strip()


def format_file_size(size):
    for u in ["B","KB","MB","GB"]:
        if size < 1024:
            return f"{size:.2f}{u}"
        size /= 1024
