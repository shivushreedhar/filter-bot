from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from pyrogram.errors.exceptions.bad_request_400 import MessageTooLong
from info import ADMINS, LOG_CHANNEL, USERNAME
from database.users_chats_db import db
from database.ia_filterdb import Media, get_files_db_size
from utils import get_size, temp
from Script import script
import psutil
import time


def is_real_channel(chat_id):
    return isinstance(chat_id, int) and str(chat_id).startswith("-100")


@Client.on_message(filters.new_chat_members & filters.group)
async def save_group(bot, message):
    check = [u.id for u in message.new_chat_members]
    if temp.ME in check:
        if not await db.get_chat(message.chat.id):
            total = await bot.get_chat_members_count(message.chat.id)
            user = message.from_user.mention if message.from_user else "Dear"
            group_link = await message.chat.export_invite_link()
            await bot.send_message(
                LOG_CHANNEL,
                script.NEW_GROUP_TXT.format(
                    temp.B_LINK,
                    message.chat.title,
                    message.chat.id,
                    message.chat.username,
                    group_link,
                    total,
                    user,
                ),
                disable_web_page_preview=True,
            )
            await db.add_chat(message.chat.id, message.chat.title)
            btn = [[InlineKeyboardButton("⚡️ sᴜᴘᴘᴏʀᴛ ⚡️", url=USERNAME)]]
            reply_markup = InlineKeyboardMarkup(btn)
            await bot.send_message(
                chat_id=message.chat.id,
                text=(
                    f"<b>☤ ᴛʜᴀɴᴋ ʏᴏᴜ ꜰᴏʀ ᴀᴅᴅɪɴɢ ᴍᴇ ɪɴ {message.chat.title}\n\n"
                    "🤖 ᴅᴏɴ’ᴛ ꜰᴏʀɢᴇᴛ ᴛᴏ ᴍᴀᴋᴇ ᴍᴇ ᴀᴅᴍɪɴ 🤖</b>"
                ),
                reply_markup=reply_markup,
            )


@Client.on_message(filters.command("leave") & filters.user(ADMINS))
async def leave_a_chat(bot, message):
    r = message.text.split(None)
    if len(message.command) == 1:
        return await message.reply(
            "<b>Use like: `/leave -100xxxxxxxxxx`</b>"
        )

    chat = message.command[1]
    reason = message.text.split(None, 2)[2] if len(r) > 2 else "No reason provided"

    try:
        chat = int(chat)
    except:
        pass

    try:
        await bot.leave_chat(chat)
        await db.delete_chat(chat)
        await message.reply(f"<b>Left chat `{chat}` successfully</b>")
    except Exception as e:
        await message.reply(f"<b>Error: `{e}`</b>")


@Client.on_message(filters.command("groups") & filters.user(ADMINS))
async def groups_list(bot, message):
    msg = await message.reply("<b>Searching...</b>")
    chats = await db.get_all_chats()

    out = "Groups saved in the database:\n\n"
    count = 1

    async for chat in chats:
        cid = chat.get("id")

        # 🔑 FIX: only real channels / supergroups
        if not is_real_channel(cid):
            continue

        try:
            chat_info = await bot.get_chat(cid)
            members = chat_info.members_count or "Unknown"
        except Exception:
            continue

        out += (
            f"<b>{count}. Title - `{chat['title']}`\n"
            f"ID - `{cid}`\n"
            f"Members - `{members}`</b>\n\n"
        )
        count += 1

    try:
        if count > 1:
            await msg.edit_text(out)
        else:
            await msg.edit_text("<b>No valid groups found</b>")
    except MessageTooLong:
        with open("chats.txt", "w+") as f:
            f.write(out)
        await message.reply_document("chats.txt", caption="<b>Groups list</b>")


@Client.on_message(filters.command("stats") & filters.user(ADMINS) & filters.incoming)
async def get_stats(bot, message):
    users = await db.total_users_count()
    groups = await db.total_chat_count()
    size = get_size(await db.get_db_size())
    free = get_size(536870912)
    files = await Media.count_documents()
    db2_size = get_size(await get_files_db_size())
    db2_free = get_size(536870912)
    uptime = time.strftime("%Hh %Mm %Ss", time.gmtime(0))
    ram = psutil.virtual_memory().percent
    cpu = psutil.cpu_percent()

    await message.reply_text(
        script.STATUS_TXT.format(
            users, groups, size, free, files, db2_size, db2_free, uptime, ram, cpu
        )
    )


@Client.on_message(filters.command("invite") & filters.private & filters.user(ADMINS))
async def invite(client, message):
    toGenInvLink = message.command[1]
    if len(toGenInvLink) != 14:
        return await message.reply(
            "Invalid chat id. Add -100 before chat id."
        )
    try:
        link = await client.export_chat_invite_link(int(toGenInvLink))
        await message.reply(link)
    except Exception as e:
        await message.reply(f"Error: `{e}`")
