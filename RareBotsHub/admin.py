import asyncio
import time

from pyrogram import Client, filters
from pyrogram.enums import ParseMode
from pyrogram.errors import FloodWait, RPCError
from pyrogram.types import Message

from database.database import db
from helper_func import error_handler, is_owner_or_admin

BOT_START_TIME = time.time()


def get_readable_time(seconds: int) -> str:
    periods = [("d", 86400), ("h", 3600), ("m", 60), ("s", 1)]
    result = ""
    for name, secs in periods:
        if seconds >= secs:
            value, seconds = divmod(seconds, secs)
            result += f"{int(value)}{name} "
    return result.strip() or "0s"


# -------------------------------------------------------------------- #
#                               /status                                 #
# -------------------------------------------------------------------- #
@Client.on_message(filters.command("status") & is_owner_or_admin)
@error_handler
async def status_cmd(client: Client, message: Message):
    total_users = await db.total_users_count()
    uptime = get_readable_time(int(time.time() - BOT_START_TIME))

    await message.reply_text(
        "<b><blockquote>📊 Bᴏᴛ Sᴛᴀᴛᴜs\n\n"
        f"‣ Tᴏᴛᴀʟ Usᴇʀs : <code>{total_users}</code>\n"
        f"‣ Uᴘᴛɪᴍᴇ : <code>{uptime}</code></blockquote></b>",
        parse_mode=ParseMode.HTML,
    )


# -------------------------------------------------------------------- #
#                                /users                                 #
# -------------------------------------------------------------------- #
@Client.on_message(filters.command("users") & is_owner_or_admin)
@error_handler
async def users_cmd(client: Client, message: Message):
    total_users = await db.total_users_count()
    await message.reply_text(
        f"<b><blockquote>👥 Tᴏᴛᴀʟ Usᴇʀs : <code>{total_users}</code></blockquote></b>",
        parse_mode=ParseMode.HTML,
    )


# -------------------------------------------------------------------- #
#                              /broadcast                               #
# -------------------------------------------------------------------- #
@Client.on_message(filters.command("broadcast") & is_owner_or_admin)
@error_handler
async def broadcast_cmd(client: Client, message: Message):
    if not message.reply_to_message:
        return await message.reply_text(
            "<b><blockquote>Rᴇᴘʟʏ ᴛᴏ ᴀ ᴍᴇssᴀɢᴇ ᴡɪᴛʜ <code>/broadcast</code> "
            "ᴛᴏ sᴇɴᴅ ɪᴛ ᴛᴏ ᴇᴠᴇʀʏ ʙᴏᴛ ᴜsᴇʀ.</blockquote></b>",
            parse_mode=ParseMode.HTML,
        )

    total = await db.total_users_count()
    status = await message.reply_text(
        f"<b><blockquote>📢 Bʀᴏᴀᴅᴄᴀsᴛɪɴɢ ᴛᴏ <code>{total}</code> ᴜsᴇʀs...</blockquote></b>",
        parse_mode=ParseMode.HTML,
    )

    success = 0
    failed = 0
    deleted = 0
    start_time = time.time()

    async for user in db.get_all_users():
        user_id = user["_id"]
        try:
            await message.reply_to_message.copy(chat_id=user_id)
            success += 1
        except FloodWait as e:
            await asyncio.sleep(e.value)
            try:
                await message.reply_to_message.copy(chat_id=user_id)
                success += 1
            except Exception:
                failed += 1
        except RPCError:
            failed += 1
            await db.delete_user(user_id)
            deleted += 1
        except Exception:
            failed += 1

        await asyncio.sleep(0.05)

    total_time = round(time.time() - start_time, 2)
    await status.edit_text(
        "<b><blockquote>✅ Bʀᴏᴀᴅᴄᴀsᴛ Cᴏᴍᴘʟᴇᴛᴇᴅ!\n\n"
        f"‣ Sᴜᴄᴄᴇss : <code>{success}</code>\n"
        f"‣ Fᴀɪʟᴇᴅ : <code>{failed}</code>\n"
        f"‣ Rᴇᴍᴏᴠᴇᴅ (ʙʟᴏᴄᴋᴇᴅ/ᴅᴇʟᴇᴛᴇᴅ) : <code>{deleted}</code>\n"
        f"‣ Tɪᴍᴇ Tᴀᴋᴇɴ : <code>{total_time}s</code></blockquote></b>",
        parse_mode=ParseMode.HTML,
    )
