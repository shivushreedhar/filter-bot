import logging
from pyrogram import Client, filters, enums
from info import DELETE_CHANNELS, LOG_CHANNEL
from database.ia_filterdb import Media, unpack_new_file_id

logger = logging.getLogger(__name__)

media_filter = filters.document | filters.video | filters.audio


@Client.on_message(filters.chat(DELETE_CHANNELS) & media_filter)
async def deletemultiplemedia(bot, message):
    # extra safety: allow only channel messages
    if message.chat.type != enums.ChatType.CHANNEL:
        return

    media = getattr(message, message.media.value, None)
    if not media:
        return

    if media.mime_type not in ("video/mp4", "video/x-matroska"):
        return

    file_id, _ = unpack_new_file_id(media.file_id)

    try:
        result = await Media.find_one({"file_id": file_id})
        if result:
            await result.delete()
            logger.info(
                f"File deleted from DB | name={media.file_name} | id={file_id}"
            )
        else:
            logger.warning(
                f"File not found in DB | name={media.file_name} | id={file_id}"
            )
    except Exception as e:
        logger.error(f"Delete error | {e}")
        await bot.send_message(
            LOG_CHANNEL,
            f"<b>Delete Error</b>\n<code>{e}</code>",
        )
