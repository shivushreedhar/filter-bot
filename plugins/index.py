import asyncio
import time
from pyrogram import Client, filters, enums
from pyrogram.errors import FloodWait
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from info import ADMINS, CHANNELS
from database.ia_filterdb import save_file
from utils import temp, get_readable_time

lock = asyncio.Lock()


def is_real_channel(chat_id):
    return isinstance(chat_id, int) and str(chat_id).startswith("-100")


@Client.on_callback_query(filters.regex(r"^index"))
async def index_files(bot, query):
    _, ident, chat, lst_msg_id, skip = query.data.split("#")
    if ident == "yes":
        msg = query.message
        await msg.edit("<b>Indexing started...</b>")
        try:
            chat = int(chat)
        except:
            pass
        await index_files_to_db(int(lst_msg_id), chat, msg, bot, int(skip))
    elif ident == "cancel":
        temp.CANCEL = True
        await query.message.edit("Trying to cancel Indexing...")


@Client.on_message(
    filters.command("index") & filters.private & filters.incoming & filters.user(ADMINS)
)
async def send_for_index(bot, message):
    if lock.locked():
        return await message.reply("Wait until previous process complete.")

    i = await message.reply("Forward last message or send last message link.")
    msg = await bot.listen(chat_id=message.chat.id, user_id=message.from_user.id)
    await i.delete()

    if msg.text and msg.text.startswith("https://t.me"):
        try:
            msg_link = msg.text.split("/")
            last_msg_id = int(msg_link[-1])
            chat_id = msg_link[-2]
            if chat_id.isnumeric():
                chat_id = int("-100" + chat_id)
        except:
            return await message.reply("Invalid message link!")
    elif msg.forward_from_chat and msg.forward_from_chat.type == enums.ChatType.CHANNEL:
        last_msg_id = msg.forward_from_message_id
        chat_id = msg.forward_from_chat.username or msg.forward_from_chat.id
    else:
        return await message.reply("This is not forwarded message or link.")

    try:
        chat = await bot.get_chat(chat_id)
    except Exception as e:
        return await message.reply(f"Error: {e}")

    if chat.type != enums.ChatType.CHANNEL:
        return await message.reply("I can index only channels.")

    s = await message.reply("Send skip message number.")
    msg = await bot.listen(chat_id=message.chat.id, user_id=message.from_user.id)
    await s.delete()

    try:
        skip = int(msg.text)
    except:
        return await message.reply("Number is invalid.")

    buttons = [
        [
            InlineKeyboardButton(
                "YES", callback_data=f"index#yes#{chat_id}#{last_msg_id}#{skip}"
            )
        ],
        [InlineKeyboardButton("CLOSE", callback_data="close_data")],
    ]

    await message.reply(
        f"Do you want to index {chat.title} channel?\nTotal Messages: <code>{last_msg_id}</code>",
        reply_markup=InlineKeyboardMarkup(buttons),
    )


@Client.on_message(filters.command("channel"))
async def channel_info(bot, message):
    if message.from_user.id not in ADMINS:
        return await message.reply("Only bot owner can use this command.")

    safe_channels = [ch for ch in CHANNELS if is_real_channel(ch)]

    if not safe_channels:
        return await message.reply("No valid database channels configured.")

    text = "**Indexed Channels:**\n\n"

    for ch in safe_channels:
        try:
            chat = await bot.get_chat(ch)
            text += f"• {chat.title}\n"
        except Exception as e:
            text += f"• {ch} (invalid / inaccessible)\n"

    text += f"\n**Total:** {len(safe_channels)}"
    await message.reply(text)


async def index_files_to_db(lst_msg_id, chat, msg, bot, skip):
    start_time = time.time()
    total_files = duplicate = errors = deleted = no_media = unsupported = 0
    current = skip

    async with lock:
        try:
            async for message in bot.iter_messages(chat, lst_msg_id, skip):
                if temp.CANCEL:
                    temp.CANCEL = False
                    time_taken = get_readable_time(time.time() - start_time)
                    await msg.edit(
                        f"Cancelled!\nCompleted in {time_taken}\nSaved: {total_files}"
                    )
                    return

                current += 1

                if message.empty:
                    deleted += 1
                    continue
                if not message.media:
                    no_media += 1
                    continue
                if message.media not in (
                    enums.MessageMediaType.VIDEO,
                    enums.MessageMediaType.DOCUMENT,
                ):
                    unsupported += 1
                    continue

                media = getattr(message, message.media.value, None)
                if not media or media.mime_type not in (
                    "video/mp4",
                    "video/x-matroska",
                ):
                    unsupported += 1
                    continue

                media.caption = message.caption
                sts = await save_file(media)

                if sts == "suc":
                    total_files += 1
                elif sts == "dup":
                    duplicate += 1
                else:
                    errors += 1

        except FloodWait as e:
            await asyncio.sleep(e.x)
        except Exception as e:
            await msg.reply(f"Index canceled due to error: {e}")
        else:
            time_taken = get_readable_time(time.time() - start_time)
            await msg.edit(
                f"Completed in {time_taken}\nSaved: {total_files}\nDuplicates: {duplicate}\nErrors: {errors}"
            )
