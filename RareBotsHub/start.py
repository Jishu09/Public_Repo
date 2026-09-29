import random

from pyrogram import Client, filters
from pyrogram.enums import ParseMode
from pyrogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from config import (
    ADMINS,
    DEVELOPER_URL,
    HELP_TEXT,
    LOG_CHANNEL,
    START_PICS,
    START_TEXT,
    UPDATE_CHANNEL_URL,
)
from database.database import db
from helper_func import error_handler, fsub_buttons, fsub_caption, get_missing_channels


# -------------------------------------------------------------------- #
#                    SAFE PHOTO SENDING (fixes                          #
#                    WEBPAGE_CURL_FAILED crashes)                       #
# -------------------------------------------------------------------- #
# Telegram's servers fetch external image URLs themselves - if a host
# is slow/blocked/dead, `reply_photo(photo=<url>)` raises
# WebpageCurlFailed and crashes the handler. This helper tries every
# configured pic (shuffled), skips any that fail, and as soon as one
# succeeds caches the resulting file_id so every future send reuses
# that (fast, and immune to the source URL ever going down again). If
# literally every pic fails, it falls back to a text-only reply so the
# user is never left with a crashed, silent bot.
_photo_file_id_cache: dict[str, str] = {}


async def send_start_photo(message: Message, caption: str, reply_markup=None):
    pics = START_PICS.copy()
    random.shuffle(pics)

    for pic in pics:
        media = _photo_file_id_cache.get(pic, pic)
        try:
            sent = await message.reply_photo(
                photo=media,
                caption=caption,
                parse_mode=ParseMode.HTML,
                reply_markup=reply_markup,
            )
            if pic not in _photo_file_id_cache and sent.photo:
                _photo_file_id_cache[pic] = sent.photo.file_id
            return sent
        except Exception:
            continue  # try the next pic

    # Every photo failed (bad URLs / Telegram couldn't fetch any of
    # them) -> still answer the user, just without a picture.
    return await message.reply_text(caption, parse_mode=ParseMode.HTML, reply_markup=reply_markup)


# -------------------------------------------------------------------- #
#                              KEYBOARDS                                #
# -------------------------------------------------------------------- #
def start_buttons() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("Hᴇʟᴘ", callback_data="help_menu"),
                InlineKeyboardButton("Dᴇᴠᴇʟᴏᴘᴇʀ", url=DEVELOPER_URL),
            ],
            [InlineKeyboardButton("Uᴘᴅᴀᴛᴇ Cʜᴀɴɴᴇʟ", url=UPDATE_CHANNEL_URL)],
        ]
    )


def help_buttons() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("‣ Bᴀᴄᴋ ‣", callback_data="start_menu")]])


# -------------------------------------------------------------------- #
#                                /start                                 #
# -------------------------------------------------------------------- #
@Client.on_message(filters.command("start") & filters.private)
@error_handler
async def start_cmd(client: Client, message: Message):
    user = message.from_user
    is_new = await db.add_user(user.id, user.username, user.first_name)

    if is_new and LOG_CHANNEL:
        try:
            await client.send_message(
                LOG_CHANNEL,
                f"<b><blockquote>#Nᴇᴡ_Usᴇʀ\n\n"
                f"‣ Nᴀᴍᴇ : {user.mention}\n"
                f"‣ Iᴅ : <code>{user.id}</code>\n"
                f"‣ Usᴇʀɴᴀᴍᴇ : @{user.username}</blockquote></b>",
                parse_mode=ParseMode.HTML,
            )
        except Exception:
            pass

    # Admins/owner always bypass force-sub.
    missing = [] if user.id in ADMINS else await get_missing_channels(client, user.id)
    if missing:
        return await send_start_photo(message, fsub_caption(missing), fsub_buttons(missing))

    await send_start_photo(
        message, START_TEXT.format(mention=user.mention), start_buttons()
    )


# -------------------------------------------------------------------- #
#                           CALLBACK QUERIES                            #
# -------------------------------------------------------------------- #
@Client.on_callback_query(filters.regex("^fsub_recheck$"))
@error_handler
async def fsub_recheck_cb(client: Client, query: CallbackQuery):
    user = query.from_user
    missing = [] if user.id in ADMINS else await get_missing_channels(client, user.id)

    if missing:
        return await query.answer("Yᴏᴜ ʜᴀᴠᴇɴ'ᴛ ᴊᴏɪɴᴇᴅ ᴀʟʟ ᴄʜᴀɴɴᴇʟs ʏᴇᴛ!", show_alert=True)

    await query.answer("Tʜᴀɴᴋs ғᴏʀ ᴊᴏɪɴɪɴɢ! Access granted.", show_alert=True)
    try:
        await query.message.edit_caption(
            caption=START_TEXT.format(mention=user.mention),
            parse_mode=ParseMode.HTML,
            reply_markup=start_buttons(),
        )
    except Exception:
        # Original message had no photo (all pics failed earlier) -> it's text, not caption.
        await query.message.edit_text(
            text=START_TEXT.format(mention=user.mention),
            parse_mode=ParseMode.HTML,
            reply_markup=start_buttons(),
        )


@Client.on_callback_query(filters.regex("^help_menu$"))
@error_handler
async def help_menu_cb(client: Client, query: CallbackQuery):
    try:
        await query.message.edit_caption(
            caption=HELP_TEXT, parse_mode=ParseMode.HTML, reply_markup=help_buttons()
        )
    except Exception:
        await query.message.edit_text(
            text=HELP_TEXT, parse_mode=ParseMode.HTML, reply_markup=help_buttons()
        )
    await query.answer()


@Client.on_callback_query(filters.regex("^start_menu$"))
@error_handler
async def back_start_cb(client: Client, query: CallbackQuery):
    user = query.from_user
    try:
        await query.message.edit_caption(
            caption=START_TEXT.format(mention=user.mention),
            parse_mode=ParseMode.HTML,
            reply_markup=start_buttons(),
        )
    except Exception:
        await query.message.edit_text(
            text=START_TEXT.format(mention=user.mention),
            parse_mode=ParseMode.HTML,
            reply_markup=start_buttons(),
        )
    await query.answer()
