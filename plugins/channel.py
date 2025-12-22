# --| FINAL FIXED channel.py |--
# --| Pyrogram v2 SAFE |--
# --| Document Caption BUG FIXED |--

import re
import asyncio
import aiohttp
from collections import defaultdict

from pyrogram import Client, filters, enums

from info import CHANNELS, MOVIE_UPDATE_CHANNEL, LOG_CHANNEL
from utils import get_poster
from database.ia_filterdb import save_file, unpack_new_file_id


POST_DELAY = 10
movie_files = defaultdict(list)
processing_movies = set()

CAPTION_LANGUAGES = [
    "Hindi", "Tamil", "Telugu", "Malayalam", "Kannada",
    "English", "Bengali", "Marathi", "Punjabi", "Gujarati"
]

UPDATE_CAPTION = """<b>𝖭𝖤𝖶 {} 𝖠𝖣𝖣𝖤𝖣 ✅</b>

🎬 <b>{} {}</b>
🔰 <b>Quality:</b> {}
🎧 <b>Audio:</b> {}

<b>✨ Telegram Files ✨</b>

{}

<blockquote>〽️ Powered by @BSHEGDE5</blockquote>
"""

media_filter = filters.document | filters.video | filters.audio


@Client.on_message(filters.chat(CHANNELS) & media_filter)
async def media_handler(bot, message):
    try:
        print("📥 MEDIA RECEIVED FROM:", message.chat.id)

        # ✅ SAFE MEDIA PICK
        media = message.document or message.video or message.audio
        if not media or not media.file_name:
            return

        # ✅ SAVE FILE
        sts = await save_file(media)
        if sts != "suc":
            return

        # ✅ ALWAYS USE message.caption
        caption = message.caption or media.file_name

        await queue_movie(bot, media, caption)

    except Exception as e:
        print("❌ MEDIA HANDLER ERROR:", e)
        await bot.send_message(LOG_CHANNEL, f"MEDIA HANDLER ERROR:\n{e}")


async def queue_movie(bot, media, caption):
    file_name = clean_name(media.file_name)

    year = re.search(r"\b(19|20)\d{2}\b", caption)
    year = year.group(0) if year else ""

    quality = detect_quality(caption + media.file_name)

    language = ", ".join(
        l for l in CAPTION_LANGUAGES if l.lower() in caption.lower()
    ) or "Unknown"

    file_id, _ = unpack_new_file_id(media.file_id)
    size = format_size(media.file_size)

    movie_files[file_name].append({
        "file_id": file_id,
        "quality": quality,
        "size": size,
        "language": language,
        "year": year,
    })

    if file_name in processing_movies:
        return

    processing_movies.add(file_name)
    await asyncio.sleep(POST_DELAY)

    try:
        await send_movie_update(bot, file_name, movie_files[file_name])
    finally:
        movie_files.pop(file_name, None)
        processing_movies.discard(file_name)


async def send_movie_update(bot, movie_name, files):
    imdb = await safe_imdb(movie_name)
    title = imdb.get("title", movie_name)
    kind = imdb.get("kind", "MOVIE").upper()

    poster = await fetch_movie_poster(title)
    poster = poster or "https://te.legra.ph/file/88d845b4f8a024a71465d.jpg"

    links = []
    for f in files:
        link = (
            f"<a href='https://t.me/{bot.me.username}"
            f"?start=file_0_{f['file_id']}'>"
            f"{f['size']}</a>"
        )
        links.append(f"📦 {f['quality']} : {link}")

    caption = UPDATE_CAPTION.format(
        kind,
        title,
        files[0]["year"],
        files[0]["quality"],
        files[0]["language"],
        "\n".join(links),
    )

    await bot.send_photo(
        chat_id=MOVIE_UPDATE_CHANNEL,
        photo=poster,
        caption=caption,
        parse_mode=enums.ParseMode.HTML
    )

    print("✅ POSTED TO MUC:", movie_name)


async def safe_imdb(name):
    try:
        data = await get_poster(name)
        return data or {}
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


def clean_name(text):
    return re.sub(r"[^\w\s]", " ", text).replace("_", " ").strip()


def format_size(size):
    for unit in ["B", "KB", "MB", "GB"]:
        if size < 1024:
            return f"{size:.2f} {unit}"
        size /= 1024
    return f"{size:.2f} TB"
