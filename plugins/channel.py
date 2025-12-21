# --| This code created by: Jisshu_bots & SilentXBotz |--#

import re
import asyncio
import aiohttp
from pyrogram import Client, filters, enums
from collections import defaultdict

from info import *
from utils import *
from database.users_chats_db import db
from database.ia_filterdb import save_file, unpack_new_file_id

# ================= KOYEB LOG =================
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

# ================= CONFIG =================
POST_DELAY = 25

CAPTION_LANGUAGES = [
    "Kannada",
    "Tamil",
    "Telugu",
    "Malayalam",
    "Hindi",
    "English",
]

movie_files = defaultdict(list)
processing_movies = set()
notified_movies = set()

media_filter = filters.document | filters.video | filters.audio

# ======================================================
# 🔧 TITLE + YEAR EXTRACTION (FINAL & SAFE)
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


# ================= MAIN HANDLER =================
@Client.on_message(filters.chat(CHANNELS) & media_filter)
async def media_handler(bot, message):
    log("FILE RECEIVED")

    media = getattr(message, message.media.value, None)
    if not media:
        return

    # IMPORTANT: original working mime check
    if media.mime_type not in [
        "video/mp4",
        "video/x-matroska",
        "document/mp4",
    ]:
        return

    media.file_type = message.media.value
    media.caption = message.caption

    success = await save_file(media)
    if success != "suc":
        return

    log("FILE SAVED")

    if not await db.get_send_movie_update_status(bot.me.id):
        return

    await queue_movie_file(bot, media)


# ================= GROUPING =================
async def queue_movie_file(bot, media):
    title, year = extract_title_year(media.file_name)
    log(f"GROUP ADD → {title}")

    caption = media.caption or media.file_name
    quality = await Jisshu_qualities(caption, media.file_name)

    # 🔊 LANGUAGE AUTO-DETECT
    langs = []
    for l in CAPTION_LANGUAGES:
        if l.lower() in caption.lower():
            langs.append(l[:3])

    language = " + ".join(langs) if langs else "Kan"

    file_id, _ = unpack_new_file_id(media.file_id)

    movie_files[title].append({
        "file_id": file_id,
        "quality": quality,
        "size": format_file_size(media.file_size),
        "language": language,
        "year": year,
    })

    if title in processing_movies:
        return

    processing_movies.add(title)
    log("GROUP WAIT 25s")

    await asyncio.sleep(POST_DELAY)
    await send_movie_update(bot, title, movie_files[title])

    movie_files.pop(title, None)
    processing_movies.remove(title)


# ================= POSTING =================
async def send_movie_update(bot, title, files):
    if title in notified_movies:
        log("POST EDITED")
    else:
        log("POST CREATE")

    notified_movies.add(title)

    year = files[0]["year"]
    language = files[0]["language"]

    imdb = await get_imdb(title)
    kind = imdb.get("kind", "MOVIE").upper()

    poster = await fetch_movie_poster(title, year)

    links = ""
    for f in files:
        links += (
            f"⭐ {f['quality']} – "
            f"<a href='https://t.me/{temp.U_NAME}?start=file_0_{f['file_id']}'>{f['size']}</a>\n"
        )

    caption = (
        SERIES_UI if kind == "TV_SERIES" else MOVIE_UI
    ).format(
        title=title,
        year=year,
        language=language,
        links=links,
    )

    await bot.send_photo(
        chat_id=MOVIE_UPDATE_CHANNEL,
        photo=poster,
        caption=caption,
        parse_mode=enums.ParseMode.HTML,
    )


# ================= POSTER =================
async def fetch_movie_poster(title, year=None):
    async with aiohttp.ClientSession() as session:
        async with session.get(
            f"https://jisshuapis.vercel.app/api.php?query={title.replace(' ', '+')}"
        ) as res:
            if res.status == 200:
                data = await res.json()
                for k in ("jisshu-2", "jisshu-3", "jisshu-4"):
                    if data.get(k):
                        return data[k][0]

    return "https://te.legra.ph/file/88d845b4f8a024a71465d.jpg"
