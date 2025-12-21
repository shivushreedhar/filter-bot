# ==========================================================
#  FINAL CHANNEL.PY
#  Title-before-year | Auto Group | Auto Edit
#  KOYEB FRIENDLY & STABLE
# ==========================================================

import re
import asyncio
import logging
from collections import defaultdict

from pyrogram import Client, filters, enums
from database.ia_filterdb import save_file, unpack_new_file_id
from info import *

# ==========================================================
# LOGGING (KOYEB FRIENDLY)
# ==========================================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | CHANNEL | %(message)s"
)
log = logging.getLogger("channel")

# ==========================================================
# CONFIG
# ==========================================================
GROUP_WAIT = 25
MEDIA_FILTER = filters.video | filters.document | filters.audio

# ==========================================================
# MEMORY
# ==========================================================
movie_buffer = defaultdict(list)
processing_movies = set()
posted_messages = {}  # title -> message_id

# ==========================================================
# HELPERS
# ==========================================================
def clean_name(text: str) -> str:
    text = re.sub(r"http\S+|@\w+|#\w+", "", text)
    text = re.sub(r"[._\-()\[\]{}!:@;']", " ", text)
    return re.sub(r"\s+", " ", text).strip()

def extract_title_year(text: str):
    text = clean_name(text)
    match = re.search(r"\b(19|20)\d{2}\b", text)
    if match:
        year = match.group(0)
        title = text.split(year)[0].strip()
        return title, year
    return text, ""

def extract_languages(text: str):
    langs = {
        "kannada": "Kan",
        "tamil": "Tam",
        "telugu": "Tel",
        "malayalam": "Mal",
        "hindi": "Hin",
        "english": "Eng"
    }
    found = [v for k, v in langs.items() if k in text.lower()]
    return " + ".join(sorted(set(found))) if found else "Unknown"

def extract_quality(text: str):
    for q in ["2160p", "1080p", "720p", "480p"]:
        if q.lower() in text.lower():
            return q
    return "720p"

def format_size(size):
    for unit in ["B", "KB", "MB", "GB"]:
        if size < 1024:
            return f"{size:.2f} {unit}"
        size /= 1024
    return f"{size:.2f} TB"

def extract_episode(text: str):
    m = re.search(r"(S\d{1,2}E\d{1,2})", text, re.I)
    return m.group(1).upper() if m else None

# ==========================================================
# CAPTION BUILDER
# ==========================================================
def build_caption(title, year, audio, files):
    lines = []

    # Header
    header = f"📺 <b>{title} ({year})</b>" if year else f"📺 <b>{title}</b>"
    lines.append(header)
    lines.append(f"🎧 <b>Audio :</b> {audio}")
    lines.append("📀 <b>Source :</b> WEB-DL\n")

    is_series = any(f["episode"] for f in files)

    if is_series:
        lines.append("⬇️ <b>Episodes</b>\n")
        for f in sorted(files, key=lambda x: (x["episode"], x["quality"])):
            link = f"<a href='https://t.me/{BOT_USERNAME}?start=file_0_{f['file_id']}'>Download</a>"
            lines.append(
                f"{f['episode']} - {f['quality']} ({f['size']}) | {link}"
            )
    else:
        lines.append("⬇️ <b>Available Qualities</b>\n")
        for f in sorted(files, key=lambda x: x["quality"]):
            link = f"<a href='https://t.me/{BOT_USERNAME}?start=file_0_{f['file_id']}'>Download</a>"
            lines.append(
                f"{f['quality']} ({f['size']}) | {link}"
            )

    lines.append("\n〽️ <b>Powered by @BSHEGDE5</b>")
    return "\n".join(lines)

# ==========================================================
# MEDIA HANDLER
# ==========================================================
@Client.on_message(filters.chat(CHANNELS) & MEDIA_FILTER)
async def media_handler(bot, message):
    media = getattr(message, message.media.value, None)
    if not media:
        return

    log.info("FILE RECEIVED")

    status = await save_file(media)
    if status != "suc":
        log.error("FILE SAVE FAILED")
        return

    log.info("FILE SAVED")

    file_id, _ = unpack_new_file_id(media.file_id)
    raw_text = media.file_name or message.caption or ""

    title, year = extract_title_year(raw_text)
    episode = extract_episode(raw_text)

    movie_buffer[title].append({
        "file_id": file_id,
        "quality": extract_quality(raw_text),
        "size": format_size(media.file_size),
        "episode": episode,
        "audio": extract_languages(raw_text),
        "year": year
    })

    log.info(f"GROUP ADD → {title}")

    if title in processing_movies:
        return

    processing_movies.add(title)

    log.info(f"GROUP WAIT {GROUP_WAIT}s → {title}")
    await asyncio.sleep(GROUP_WAIT)

    await send_or_edit_post(bot, title)

    processing_movies.remove(title)

# ==========================================================
# POST / AUTO-EDIT LOGIC
# ==========================================================
async def send_or_edit_post(bot, title):
    files = movie_buffer.get(title)
    if not files:
        return

    year = files[0]["year"]
    audio = " + ".join(sorted({
        f["audio"] for f in files if f["audio"] != "Unknown"
    })) or "Unknown"

    caption = build_caption(title, year, audio, files)

    # EDIT EXISTING POST
    if title in posted_messages:
        try:
            await bot.edit_message_caption(
                chat_id=MOVIE_UPDATE_CHANNEL,
                message_id=posted_messages[title],
                caption=caption,
                parse_mode=enums.ParseMode.HTML
            )
            log.info(f"POST EDITED → {title}")
            return
        except Exception as e:
            log.error(f"POST EDIT FAILED → {e}")

    # CREATE NEW POST
    try:
        msg = await bot.send_message(
            chat_id=MOVIE_UPDATE_CHANNEL,
            text=caption,
            parse_mode=enums.ParseMode.HTML,
            disable_web_page_preview=True
        )
        posted_messages[title] = msg.id
        log.info(f"POST CREATED → {title}")
    except Exception as e:
        log.error(f"POST CREATION FAILED → {e}")

    movie_buffer.pop(title, None)
