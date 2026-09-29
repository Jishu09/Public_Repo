import asyncio
import functools
import logging
import time

from pyrogram import filters
from pyrogram.enums import ChatMemberStatus, ParseMode
from pyrogram.errors import FloodWait, UserNotParticipant
from pyrogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from config import ADMINS, FORCE_SUB_CHANNELS, FSUB_CHANNEL_CACHE_TTL

log = logging.getLogger("RareBotsHub")


# -------------------------------------------------------------------- #
#                        OWNER / ADMIN FILTER                          #
# -------------------------------------------------------------------- #
async def _is_owner_or_admin(_, __, message: Message):
    user = message.from_user
    if not user:
        return False
    return user.id in ADMINS


is_owner_or_admin = filters.create(_is_owner_or_admin)


# -------------------------------------------------------------------- #
#                     GLOBAL ERROR-HANDLING DECORATOR                  #
# -------------------------------------------------------------------- #
def error_handler(func):
    """
    Wrap any @Client.on_message / @Client.on_callback_query handler so
    an unexpected exception:
      1. is logged with a full traceback (visible in `heroku logs`etc.)
      2. is reported back to the user in-chat instead of the command
         just silently "doing nothing" from their point of view.
    Put this directly under the Client decorator, e.g.:

        @Client.on_message(filters.command("foo"))
        @error_handler
        async def foo_cmd(client, message):
            ...
    """

    @functools.wraps(func)
    async def wrapper(client, update, *args, **kwargs):
        try:
            return await func(client, update, *args, **kwargs)
        except Exception as e:
            log.exception(f"Unhandled error in handler '{func.__name__}'")
            error_text = (
                "<b><blockquote>❌ ᴀɴ ᴜɴᴇxᴘᴇᴄᴛᴇᴅ ᴇʀʀᴏʀ ᴏᴄᴄᴜʀʀᴇᴅ!\n"
                f"<code>{type(e).__name__}: {e}</code></blockquote></b>"
            )
            try:
                if isinstance(update, CallbackQuery):
                    await update.answer("Aɴ ᴇʀʀᴏʀ ᴏᴄᴄᴜʀʀᴇᴅ, ᴘʟᴇᴀsᴇ ᴛʀʏ ᴀɢᴀɪɴ.", show_alert=True)
                    if update.message:
                        try:
                            await update.message.reply_text(error_text, parse_mode=ParseMode.HTML)
                        except Exception:
                            pass
                elif isinstance(update, Message):
                    await update.reply_text(error_text, parse_mode=ParseMode.HTML)
            except Exception:
                pass  # don't let error-reporting itself crash the handler

    return wrapper


# -------------------------------------------------------------------- #
#            MULTI FORCE-SUBSCRIBE (LIVE CHECK - NO STALE CACHE)       #
# -------------------------------------------------------------------- #
# Per-channel cache: channel -> (timestamp, resolved_info | None).
# This is metadata (is the bot admin here? what's the invite link?)
# which almost never changes, so it's safe and fast to cache. Actual
# per-user MEMBERSHIP is intentionally never cached - see note below.
_channel_info_cache: dict = {}


async def _resolve_channel(client, channel):
    cached = _channel_info_cache.get(channel)
    if cached and (time.time() - cached[0]) < FSUB_CHANNEL_CACHE_TTL:
        return cached[1]

    info = None
    try:
        chat = await client.get_chat(channel)
        me = await client.get_me()
        my_member = await client.get_chat_member(chat.id, me.id)

        if my_member.status not in (ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER):
            log.warning(f"Force-sub channel {channel} skipped: bot is not an admin there.")
            _channel_info_cache[channel] = (time.time(), None)
            return None

        invite_url = f"https://t.me/{chat.username}" if chat.username else None

        if not invite_url:
            can_invite = True
            privileges = getattr(my_member, "privileges", None)
            if privileges is not None:
                can_invite = getattr(privileges, "can_invite_users", True)

            if can_invite:
                invite_url = getattr(chat, "invite_link", None)
                if not invite_url:
                    try:
                        invite_url = await client.export_chat_invite_link(chat.id)
                    except Exception:
                        invite_url = None
            else:
                log.warning(
                    f"Force-sub channel {channel}: bot lacks 'invite users' "
                    "permission, join button will be hidden for this channel."
                )

        info = {
            "chat_id": chat.id,
            "title": chat.title or chat.username or str(chat.id),
            "invite_url": invite_url,
        }
    except Exception as e:
        log.warning(f"Force-sub channel {channel} skipped: {e}")
        info = None

    _channel_info_cache[channel] = (time.time(), info)
    return info


async def _check_single_channel(client, user_id: int, channel):
    """Live membership check for ONE channel. No caching - always asks
    Telegram directly, so a user who just left is caught immediately."""
    info = await _resolve_channel(client, channel)
    if not info:
        return None  # bot can't enforce this channel -> skip it entirely

    try:
        member = await client.get_chat_member(info["chat_id"], user_id)
        if member.status in (ChatMemberStatus.LEFT, ChatMemberStatus.BANNED):
            return {"title": info["title"], "url": info["invite_url"]}
        return None  # currently a member -> passes this channel
    except UserNotParticipant:
        return {"title": info["title"], "url": info["invite_url"]}
    except FloodWait as e:
        await asyncio.sleep(e.value)
        return await _check_single_channel(client, user_id, channel)
    except Exception as e:
        log.warning(f"Fsub live-check failed for {channel}: {e}")
        return None  # fail OPEN on transient errors - never block everyone over a glitch


async def get_missing_channels(client, user_id: int) -> list:
    """
    Returns a list of {"title": str, "url": str|None} for every
    force-sub channel this user currently has NOT joined - checked
    live against Telegram, in parallel across all channels for speed.
    Channels the bot cannot manage (not added, or not an admin there)
    are skipped automatically and never block anyone.
    """
    if not FORCE_SUB_CHANNELS:
        return []

    results = await asyncio.gather(
        *[_check_single_channel(client, user_id, channel) for channel in FORCE_SUB_CHANNELS]
    )
    return [r for r in results if r is not None]


# -------------------------------------------------------------------- #
#                    SHARED FORCE-SUB UI (used by /start,               #
#                    /replace, /batch - any public command)            #
# -------------------------------------------------------------------- #
def fsub_buttons(missing: list) -> InlineKeyboardMarkup:
    buttons = []
    for ch in missing:
        if ch["url"]:
            buttons.append([InlineKeyboardButton(f"‣ Jᴏɪɴ {ch['title']} ‣", url=ch["url"])])
    buttons.append([InlineKeyboardButton("‣ Tʀʏ Aɢᴀɪɴ ‣", callback_data="fsub_recheck")])
    return InlineKeyboardMarkup(buttons)


def fsub_caption(missing: list) -> str:
    lines = [
        "<b><blockquote>⚠️ Yᴏᴜ ᴍᴜsᴛ ᴊᴏɪɴ ᴏᴜʀ ᴄʜᴀɴɴᴇʟ(s) ʙᴇғᴏʀᴇ ᴜsɪɴɢ ᴛʜɪs ʙᴏᴛ!</blockquote></b>"
    ]
    no_link = [ch["title"] for ch in missing if not ch["url"]]
    if no_link:
        joined = ", ".join(no_link)
        lines.append(
            f"<b><blockquote>ᴀʟsᴏ ᴊᴏɪɴ : {joined} (ᴀsᴋ ᴀɴ ᴀᴅᴍɪɴ ғᴏʀ ᴛʜᴇ ʟɪɴᴋ)</blockquote></b>"
        )
    lines.append("<b><blockquote>Aғᴛᴇʀ ᴊᴏɪɴɪɴɢ, ᴛᴀᴘ Tʀʏ Aɢᴀɪɴ ʙᴇʟᴏᴡ.</blockquote></b>")
    return "\n".join(lines)


async def enforce_fsub(client, message: Message) -> bool:
    """
    Drop-in force-sub gate for any PUBLIC command (e.g. /replace,
    /batch). Admins/owner always bypass. Returns True if the command
    should continue, False if it was blocked (a message was already
    sent to the user).
    """
    user = message.from_user
    if not user or user.id in ADMINS:
        return True

    missing = await get_missing_channels(client, user.id)
    if not missing:
        return True

    await message.reply_text(
        fsub_caption(missing), parse_mode=ParseMode.HTML, reply_markup=fsub_buttons(missing)
    )
    return False
