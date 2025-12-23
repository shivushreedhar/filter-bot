# --| This code created by: Jisshu_bots & SilentXBotz |--#

import re
import asyncio
import aiohttp

from collections import defaultdict
from pyrogram import Client, filters, enums

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

    # 🔹 LOG incoming media
    print(f"[MEDIA] Received | chat_id={message.chat.id} | type={message.chat.type}")

    # ✅ 1. ONLY CHANNEL POSTS
    if message.chat.type != enums.ChatType.CHANNEL:
        print("[SKIP] Not a channel message")
        return

    # ✅ 2. ONLY DATABASE CHANNELS
    if message.chat.id not in CHANNELS:
        print(f"[SKIP] Channel {message.chat.id} not in DATABASE CHANNELS")
        return

    print(f"[OK] Database channel detected: {message.chat.id}")

    media = getattr(message, message.media.value, None)
    if not media:
        print("[SKIP] No media found")
        return

    if media.mime_type not in ["video/mp4", "video/x-matroska", "document/mp4"]:
        print(f"[SKIP] Unsupported mime type: {media.mime_type}")
        return

    media.file_type = message.media.value
    media.caption = message.caption

    print(f"[SAVE] Saving file: {media.file_name}")

    success_sts = await save_file(media)

    print(f"[SAVE] Status: {success_sts}")

    if success_sts == "suc" and await db.get_send_movie_update_status(bot.me.id):
        print("[QUEUE] Movie queued for posting")
        await queue_movie_file(bot, media)
    else:
        print("[QUEUE] Movie update posting disabled")


# ================= QUEUE ================= #

async def queue_movie_file(bot, media):
    try:
        file_name = await movie_name_format(media.file_name)
        caption = await movie_name_format(media.caption or "")

        print(f"[QUEUE] Processing movie: {file_name}")

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
            "language": language,
            "year": year,
        })

        if file_name in processing_movies:
            print(f"[QUEUE] Already processing: {file_name}")
            return

        processing_movies.add(file_name)
        print(f"[WAIT] Waiting {POST_DELAY}s to group files")
        await asyncio.sleep(POST_DELAY)

        if file_name in movie_files:
            print(f"[POST] Sending movie update: {file_name}")
            await send_movie_update(bot, file_name, movie_files[file_name])
            del movie_files[file_name]

        processing_movies.discard(file_name)

    except Exception as e:
        processing_movies.discard(file_name)
        print(f"[ERROR] Queue error: {e}")
        await bot.send_message(LOG_CHANNEL, f"Movie Queue Error:\n<code>{e}</code>")


# ================= POST ================= #

async def send_movie_update(bot, file_name, files):
    try:
        if file_name in notified_movies:
            print(f"[SKIP] Already posted: {file_name}")
            return

        notified_movies.add(file_name)

        imdb = await get_imdb(file_name)
        title = imdb.get("title", file_name)
        kind = imdb.get("kind", "MOVIE").upper().replace(" ", "_")
        year = imdb.get("year", "")

        print(f"[POST] Fetching poster for: {title}")

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

        print(f"[SEND] Posting to MUC: {channel_id}")

        await bot.send_photo(
            chat_id=channel_id,
            photo=poster or "https://te.legra.ph/file/88d845b4f8a024a71465d.jpg",
            caption=caption,
            parse_mode=enums.ParseMode.HTML
        )

        print(f"[DONE] Movie posted successfully: {title}")

    except Exception as e:
        print(f"[ERROR] Post error: {e}")
        await bot.send_message(LOG_CHANNEL, f"Post Error:\n<code>{e}</code>")


# ================= HELPERS ================= #

async def get_imdb(name):
    try:
        return await get_poster(name) or {}
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
