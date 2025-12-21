# ==========================================================
# CHANNEL.PY – FINAL STABLE VERSION
# FILE_RECEIVED → FILE_SAVED → GROUP_ADD
# ==========================================================

import re
import asyncio
import logging
from collections import defaultdict
import aiohttp

from pyrogram import Client, filters, enums
from database.ia_filterdb import save_file, unpack_new_file_id
from info import CHANNELS, MOVIE_UPDATE_CHANNEL

# ==========================================================
# LOGGING (KOYEB FRIENDLY)
# ==========================================================
logging.basicConfig(
    level=logging.INFO,
    format="[CHANNEL] [%(levelname)s] %(message)s"
)
log = logging.getLogger("channel")

# ==========================================================
# CONFIG
# ==========================================================
GROUP_WAIT = 25
MEDIA_FILTER = filters.video | filters.document | filters.audio
POWERED_BY = "@BSHEGDE5"

# ==========================================================
# MEMORY
# ==========================================================
movie_buffer = defaultdict(list)
processing_movies = set()
posted_messages = {}

# ==========================================================
# HELPERS
# ==========================================================

def clean_text(text):
    text = re.sub(r"http\S+|@\w+|#\w+", "", text)
    text = re.sub(r"[._\-()\[\]{}!:@;']", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def extract_title_year(text):
    text = clean_text(text)
    m = re.search(r"\b(19|20)\d{2}\b", text)
    if m:
        year = m.group(0)
        title = text.split(year)[0].strip()
        return title.title(), year
    return text.title(), ""


def extract_quality(text):
    for q in ["2160p", "1080p", "720p", "520p", "480p"]:
        if q.lower() in text.lower():
            return q.upper()
    return "720P"


def extract_episode(text):
    m = re.search(r"(S\d{1,2}E\d{1,2})", text, re.I)
    return m.group(1).upper() if m else None


def extract_audio(text):
    audio_map = {
        "kannada": "Kan",
        "tamil": "Tam",
        "telugu": "Tel",
        "malayalam": "Mal",
        "hindi": "Hin",
        "english": "Eng"
    }
    found = [v for k, v in audio_map.items() if k in text.lower()]
    return " + ".join(sorted(set(found))) if found else "Unknown"


def extract_source(text):
    text = text.lower()
    source_map = {
        "bluray": "BluRay",
        "bdrip": "BluRay",
        "web-dl": "WEB-DL",
        "webdl": "WEB-DL",
        "webrip": "WEBRip",
        "hdrip": "HDRip",
        "dvdrip": "DVDRip",
        "hdcam": "HDCAM",
        "camrip": "CAMRip",
        "cam": "CAM"
    }
    for k, v in source_map.items():
        if k in text:
            return v
    return "WEB-DL"


def format_size(size):
    for unit in ["B", "KB", "MB", "GB"]:
        if size < 1024:
            return f"{size:.2f} {unit}"
        size /= 1024
    return f"{size:.2f} TB"


async def fetch_jisshu_poster(title):
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"https://api.jisshu.me/poster?query={title}", timeout=10
            ) as r:
                if r.status != 200:
                    return None
                data = await r.json()
                return data.get("poster")
    except Exception:
        return None

# ==========================================================
# CAPTION BUILDER
# ==========================================================

def build_caption(title, year, audio, source, files):
    lines = []
    header = f"🎬 <b>{title} ({year})</b>" if year else f"🎬 <b>{title}</b>"
    lines.append(header)
    lines.append(f"🔊 <b>Audio :</b> {audio}")
    lines.append(f"💿 <b>Source :</b> {source}\n")

    is_series = any(f["episode"] for f in files)

    if is_series:
        lines.append("⬇️ <b>Episodes</b>")
        lines.append("━━━━━━━━━━━━━━━━━━")
        for f in sorted(files, key=lambda x: x["episode"]):
            lines.append(f"{f['episode']} – {f['quality']}")
    else:
        lines.append("⬇️ <b>Available Qualities</b>")
        lines.append("━━━━━━━━━━━━━━━━━━")
        for f in sorted(files, key=lambda x: x["quality"]):
            lines.append(f"✨ {f['quality']} – {f['size']}")

    lines.append(f"\n〽️ <b>Powered by {POWERED_BY}</b>")
    return "\n".join(lines)

# ==========================================================
# MEDIA HANDLER (ORDER FIXED)
# ==========================================================

@Client.on_message(filters.chat(CHANNELS) & MEDIA_FILTER)
async def media_handler(bot, message):

    log.info("FILE_RECEIVED")

    media = message.document or message.video or message.audio
    if not media:
        return

    # ✅ FILE SAVED FIRST
    if await save_file(media) != "suc":
        log.error("FILE_SAVE_FAILED")
        return

    log.info("FILE_SAVED")

    file_id, _ = unpack_new_file_id(media.file_id)
    raw_text = media.file_name or message.caption or ""

    title, year = extract_title_year(raw_text)
    episode = extract_episode(raw_text)

    movie_buffer[title].append({
        "file_id": file_id,
        "quality": extract_quality(raw_text),
        "size": format_size(media.file_size),
        "episode": episode,
        "audio": extract_audio(raw_text),
        "source": extract_source(raw_text),
        "year": year
    })

    log.info(f"GROUP_ADD | title={title}")

    if title in processing_movies:
        return

    processing_movies.add(title)
    log.info(f"GROUP_WAIT | {GROUP_WAIT}s | title={title}")

    await asyncio.sleep(GROUP_WAIT)
    await send_or_edit_post(bot, title)
    processing_movies.remove(title)

# ==========================================================
# POST CREATE / AUTO EDIT
# ==========================================================

async def send_or_edit_post(bot, title):
    files = movie_buffer.get(title)
    if not files:
        return

    year = files[0]["year"]
    source = files[0]["source"]
    audio = " + ".join(
        sorted({f["audio"] for f in files if f["audio"] != "Unknown"})
    ) or "Unknown"

    caption = build_caption(title, year, audio, source, files)

    if title in posted_messages:
        await bot.edit_message_caption(
            MOVIE_UPDATE_CHANNEL,
            posted_messages[title],
            caption,
            parse_mode=enums.ParseMode.HTML
        )
        log.info(f"POST_EDITED | title={title}")
    else:
        poster = await fetch_jisshu_poster(title)
        if poster:
            msg = await bot.send_photo(
                MOVIE_UPDATE_CHANNEL,
                poster,
                caption=caption,
                parse_mode=enums.ParseMode.HTML
            )
            log.info(f"POST_CREATED_WITH_POSTER | title={title}")
        else:
            msg = await bot.send_message(
                MOVIE_UPDATE_CHANNEL,
                caption,
                parse_mode=enums.ParseMode.HTML
            )
            log.info(f"POST_CREATED_NO_POSTER | title={title}")

        posted_messages[title] = msg.id

    movie_buffer.pop(title, None)
