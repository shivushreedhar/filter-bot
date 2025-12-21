# --| This code created by: Jisshu_bots & SilentXBotz |--#

import re
import asyncio
import logging
import aiohttp
from collections import defaultdict
from pyrogram import Client, filters, enums

from info import CHANNELS, MOVIE_UPDATE_CHANNEL
from utils import temp, get_qualities, get_imdb
from database.users_chats_db import db
from database.ia_filterdb import save_file, unpack_new_file_id
from database.post_map_db import get_post, save_post

# ======================================================
# LOGGING (KOYEB SAFE)
# ======================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | channel.py | %(message)s",
)
log = logging.getLogger(__name__)
log.error("CHANNEL.PY LOADED")

# ======================================================
# CONFIG
# ======================================================

POST_DELAY = 25
media_filter = filters.document | filters.video | filters.audio
FALLBACK_POSTER = "https://te.legra.ph/file/88d845b4f8a024a71465d.jpg"

CAPTION_LANGUAGES = [
    "Kannada",
    "Tamil",
    "Telugu",
    "Malayalam",
    "Hindi",
    "English",
]

# ======================================================
# STATE (YOUR LOGIC)
# ======================================================

movie_files = defaultdict(list)
processing_movies = set()

# ======================================================
# HELPERS (TITLE + YEAR ONLY)
# ======================================================

def extract_title_year(text: str):
    year_match = re.search(r"\b(19|20)\d{2}\b", text)
    year = year_match.group(0) if year_match else ""

    text = re.sub(r"\.(mkv|mp4|avi)$", "", text, flags=re.I)
    text = re.sub(r"@\w+|#\w+", "", text)

    if year:
        text = text.split(year)[0]

    text = re.sub(r"S\d{1,2}E\d{1,2}", "", text, flags=re.I)
    text = re.sub(
        r"(WEB[-_. ]DL|HDRip|x264|x265|HEVC|720p|1080p|2160p|Mul|Multi)",
        "",
        text,
        flags=re.I,
    )

    text = re.sub(r"[.\-_()\[\]]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()

    return text, year


def format_size(size):
    for u in ["B", "KB", "MB", "GB", "TB"]:
        if size < 1024:
            return f"{size:.2f} {u}"
        size /= 1024


async def fetch_poster(title):
    async with aiohttp.ClientSession() as s:
        async with s.get(
            f"https://jisshuapis.vercel.app/api.php?query={title.replace(' ', '+')}"
        ) as r:
            if r.status == 200:
                j = await r.json()
                for k in ("jisshu-2", "jisshu-3", "jisshu-4"):
                    if j.get(k):
                        return j[k][0]
    return FALLBACK_POSTER

# ======================================================
# MEDIA HANDLER
# ======================================================

@Client.on_message(filters.chat(CHANNELS) & media_filter)
async def media_handler(bot, message):
    media = getattr(message, message.media.value, None)
    if not media:
        return

    log.info(f"FILE RECEIVED | {media.file_name}")

    if media.mime_type not in [
        "video/mp4",
        "video/x-matroska",
        "document/mp4",
    ]:
        return

    media.file_type = message.media.value
    media.caption = message.caption

    status = await save_file(media)
    if status != "suc":
        log.error("FILE SAVE FAILED")
        return

    log.info("FILE SAVED")

    if not await db.get_send_movie_update_status(bot.me.id):
        log.info("MOVIE UPDATE STATUS OFF")
        return

    await queue_movie_file(bot, media)

# ======================================================
# GROUPING (YOUR LOGIC)
# ======================================================

async def queue_movie_file(bot, media):
    title, year = extract_title_year(media.file_name)
    log.info(f"GROUP ADD | {title}")

    caption = media.caption or media.file_name
    quality = await get_qualities(caption)

    langs = []
    for l in CAPTION_LANGUAGES:
        if l.lower() in caption.lower():
            langs.append(l[:3])
    language = " + ".join(langs) if langs else "Kan"

    file_id, _ = unpack_new_file_id(media.file_id)

    movie_files[title].append({
        "file_id": file_id,
        "quality": quality,
        "size": format_size(media.file_size),
        "language": language,
        "year": year,
    })

    if title in processing_movies:
        return

    processing_movies.add(title)
    log.info("GROUP WAIT 25s")

    await asyncio.sleep(POST_DELAY)
    await send_movie_update(bot, title, movie_files[title])

    movie_files.pop(title, None)
    processing_movies.remove(title)

# ======================================================
# POST CREATE / EDIT (REFERRED TECHNIQUE)
# ======================================================

async def send_movie_update(bot, title, files):
    key = title.lower().replace(" ", "_")
    year = files[0]["year"]
    language = files[0]["language"]

    poster = await fetch_poster(title)

    lines = []
    for f in files:
        link = f"https://t.me/{temp.U_NAME}?start=file_0_{f['file_id']}"
        lines.append(
            f"<b>{f['quality']} – <a href='{link}'>{f['size']}</a></b>"
        )

    body = "\n".join(lines)

    caption = (
        f"<blockquote><b>🎬 {title} ({year})</b></blockquote>\n"
        f"<blockquote><b>🎧 Audio : {language}</b></blockquote>\n"
        f"<blockquote><b>📀 Source : WEB-DL</b></blockquote>\n\n"
        f"<blockquote><b>⬇️ Available</b></blockquote>\n"
        f"<blockquote><b>{body}</b></blockquote>\n\n"
        f"<blockquote><b>〽️ Powered by @BSHEGDE5</b></blockquote>"
    )

    post = await get_post(key)

    if post:
        log.info(f"POST EDIT | {key}")
        await bot.edit_message_caption(
            post["chat_id"],
            post["message_id"],
            caption,
            parse_mode=enums.ParseMode.HTML,
        )
        return

    msg = await bot.send_photo(
        MOVIE_UPDATE_CHANNEL,
        poster,
        caption=caption,
        parse_mode=enums.ParseMode.HTML,
    )
    await save_post(key, MOVIE_UPDATE_CHANNEL, msg.id, "auto")
    log.info(f"POST CREATE | {key}")
