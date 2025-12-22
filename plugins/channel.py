# --| FINAL channel.py |--
# --| BIN_CHANNEL not required |--
# --| Posting to MUC FIXED |--

import re
import asyncio
import aiohttp
from collections import defaultdict

from pyrogram import Client, filters, enums

from info import CHANNELS, MOVIE_UPDATE_CHANNEL, LOG_CHANNEL
from utils import get_poster
from database.ia_filterdb import save_file, unpack_new_file_id


# ================= CONFIG ================= #

POST_DELAY = 5  # seconds
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

media_filter = filters.document | filters.video
movie_files = defaultdict(list)


# ================= MEDIA HANDLER ================= #
# 🔥 Listens to CHANNELS from info.py

@Client.on_message(filters.chat(CHANNELS) & media_filter)
async def media_handler(bot, message):
    try:
        print("📥 MEDIA RECEIVED FROM:", message.chat.id)

        # ✅ SAFE MEDIA PICK
        if message.document:
            media = message.document
        elif message.video:
            media = message.video
        else:
            return

        if not media.file_name:
            return

        # ✅ SAVE TO DB
        status = await save_file(media)
        print("💾 SAVE STATUS:", status)

        if status == "suc":
            await queue_movie(bot, message, media)

    except Exception as e:
        print("❌ MEDIA HANDLER ERROR:", e)
        try:
            await bot.send_message(LOG_CHANNEL, f"MEDIA ERROR:\n{e}")
        except:
            pass


# ================= QUEUE / GROUP ================= #

async def queue_movie(bot, message, media):
    file_name = movie_name_format(media.file_name)

    # ✅ FIXED: caption comes from message, NOT media
    caption_src = message.caption or media.file_name

    year_match = re.search(r"\b(19|20)\d{2}\b", caption_src)
    year = year_match.group(0) if year_match else ""

    quality = detect_quality(caption_src + media.file_name)

    language = ", ".join(
        l for l in CAPTION_LANGUAGES if l.lower() in caption_src.lower()
    ) or "Unknown"

    file_id, _ = unpack_new_file_id(media.file_id)
    size = format_file_size(media.file_size)

    movie_files[file_name].append({
        "file_id": file_id,
        "quality": quality,
        "size": size,
        "language": language,
        "year": year,
        "source": message.chat.id,   # 🔥 IMPORTANT
    })

    if file_name in MOVIE_POST_LOCK:
        return

    MOVIE_POST_LOCK.add(file_name)
    await asyncio.sleep(POST_DELAY)

    try:
        await send_movie_update(bot, file_name, movie_files[file_name])
    finally:
        movie_files.pop(file_name, None)
        MOVIE_POST_LOCK.discard(file_name)


# ================= POST TO MUC ================= #

async def send_movie_update(bot, movie_name, files):
    print("🚀 POSTING TO MUC:", movie_name)

    imdb = await safe_imdb(movie_name)
    title = imdb.get("title", movie_name)
    kind = imdb.get("kind", "MOVIE").upper()

    poster = await fetch_movie_poster(title)
    poster = poster or "https://te.legra.ph/file/88d845b4f8a024a71465d.jpg"

    quality_lines = []

    for f in files:
        link = (
            f"<a href='https://t.me/{bot.me.username}"
            f"?start=file_{f['source']}_{f['file_id']}'>"
            f"{f['size']}</a>"
        )
        quality_lines.append(f"📦 {f['quality']} : {link}")

    caption = UPDATE_CAPTION.format(
        kind,
        title,
        files[0]["year"],
        files[0]["quality"],
        files[0]["language"],
        "\n".join(quality_lines),
    )

    await bot.send_photo(
        chat_id=MOVIE_UPDATE_CHANNEL,
        photo=poster,
        caption=caption,
        parse_mode=enums.ParseMode.HTML,
    )

    print("✅ POSTED TO MUC:", movie_name)


# ================= HELPERS ================= #

async def safe_imdb(name):
    try:
        data = await get_poster(name)
        return {
            "title": data.get("title"),
            "kind": data.get("kind"),
            "year": data.get("year"),
        } if data else {}
    except:
        return {}


async def fetch_movie_poster(title):
    try:
        async with aiohttp.ClientSession() as session:
            url = f"https://jisshuapis.vercel.app/api.php?query={title.replace(' ', '+')}"
            async with session.get(url, timeout=6) as r:
                data = await r.json()
                for k in ("jisshu-2", "jisshu-3", "jisshu-4"):
                    if data.get(k):
                        return data[k][0]
    except:
        return None


def detect_quality(text):
    for q in ["2160p", "1080p", "720p", "480p"]:
        if q.lower() in text.lower():
            return q
    return "720p"


def movie_name_format(text):
    return re.sub(r"[^\w\s]", " ", text).replace("_", " ").strip()


def format_file_size(size):
    for unit in ["B", "KB", "MB", "GB"]:
        if size < 1024:
            return f"{size:.2f} {unit}"
        size /= 1024
    return f"{size:.2f} TB"
