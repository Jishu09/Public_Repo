import asyncio
import re
import time

from pyrogram import Client, filters
from pyrogram.enums import ChatType, ParseMode
from pyrogram.errors import FloodWait, RPCError
from pyrogram.types import (
    InputMediaAnimation,
    InputMediaAudio,
    InputMediaDocument,
    InputMediaPhoto,
    InputMediaVideo,
    Message,
)

from helper_func import enforce_fsub, error_handler


# -------------------------------------------------------------------- #
#                             LINK PARSING                              #
# -------------------------------------------------------------------- #
def parse_link(link: str):
    link = link.strip()

    c_match = re.search(r"t\.me/c/(\d+)/(\d+)(?:-(\d+))?", link)
    if c_match:
        chat_id = int("-100" + c_match.group(1))
        msg_id = int(c_match.group(2))
        end_id = int(c_match.group(3)) if c_match.group(3) else None
        return chat_id, msg_id, end_id

    u_match = re.search(r"t\.me/([a-zA-Z0-9_]+)/(\d+)(?:-(\d+))?", link)
    if u_match:
        chat_id = u_match.group(1)
        msg_id = int(u_match.group(2))
        end_id = int(u_match.group(3)) if u_match.group(3) else None
        return chat_id, msg_id, end_id

    return None, None, None


def get_forward_origin_info(msg: Message):
    """
    Resolve (chat_id, message_id) that a message was forwarded from,
    WITHOUT using the deprecated `forward_from_chat` /
    `forward_from_message_id` properties. Uses `forward_origin` instead,
    as recommended by Pyrogram/Pyrofork.
    """
    origin = getattr(msg, "forward_origin", None)
    if not origin:
        return None, None

    chat = getattr(origin, "chat", None) or getattr(origin, "sender_chat", None)
    origin_msg_id = getattr(origin, "message_id", None)

    if chat:
        return chat.id, origin_msg_id
    return None, None


def get_input_media(msg: Message):
    caption = msg.caption if msg.caption else ""
    entities = msg.caption_entities if msg.caption else None

    if msg.photo:
        has_spoiler = bool(getattr(msg.photo, "has_spoiler", False))
        return InputMediaPhoto(
            media=msg.photo.file_id,
            caption=caption,
            caption_entities=entities,
            has_spoiler=has_spoiler,
        )
    elif msg.video:
        has_spoiler = bool(getattr(msg.video, "has_spoiler", False))
        return InputMediaVideo(
            media=msg.video.file_id,
            caption=caption,
            caption_entities=entities,
            width=getattr(msg.video, "width", 0),
            height=getattr(msg.video, "height", 0),
            duration=getattr(msg.video, "duration", 0),
            supports_streaming=getattr(msg.video, "supports_streaming", True),
            has_spoiler=has_spoiler,
        )
    elif msg.document:
        return InputMediaDocument(
            media=msg.document.file_id,
            caption=caption,
            caption_entities=entities,
        )
    elif msg.audio:
        return InputMediaAudio(
            media=msg.audio.file_id,
            caption=caption,
            caption_entities=entities,
            duration=getattr(msg.audio, "duration", 0),
            performer=getattr(msg.audio, "performer", None),
            title=getattr(msg.audio, "title", None),
        )
    elif msg.animation:
        has_spoiler = bool(getattr(msg.animation, "has_spoiler", False))
        return InputMediaAnimation(
            media=msg.animation.file_id,
            caption=caption,
            caption_entities=entities,
            width=getattr(msg.animation, "width", 0),
            height=getattr(msg.animation, "height", 0),
            duration=getattr(msg.animation, "duration", 0),
            has_spoiler=has_spoiler,
        )
    return None


async def replace_message(client: Client, target_chat, target_msg_id: int, source_msg: Message):
    input_media = get_input_media(source_msg)

    if input_media:
        await client.edit_message_media(
            chat_id=target_chat,
            message_id=target_msg_id,
            media=input_media,
            reply_markup=source_msg.reply_markup,
        )
        return True
    elif source_msg.text:
        await client.edit_message_text(
            chat_id=target_chat,
            message_id=target_msg_id,
            text=source_msg.text,
            entities=source_msg.entities,
            reply_markup=source_msg.reply_markup,
        )
        return True
    return False


# ================== 1. Single Replace ================== #
# Open to ALL users (not just admins) - gated by force-sub instead.
# Admins/owner bypass force-sub automatically (see enforce_fsub()).
@Client.on_message(filters.command(["replace"]))
@error_handler
async def replace_single_cmd(client: Client, message: Message):
    if not await enforce_fsub(client, message):
        return

    target_chat = None
    target_msg_id = None
    source_msg = None
    source_chat = None
    source_msg_id = None

    # Method 1: Two links provided directly (/replace <target_link> <source_link>)
    if len(message.command) >= 3:
        target_link = message.command[1]
        source_link = message.command[2]

        t_chat, t_id, _ = parse_link(target_link)
        s_chat, s_id, _ = parse_link(source_link)

        if not t_chat or not t_id:
            return await message.reply_text(
                "<b><blockquote expandable>❌ ɪɴᴠᴀʟɪᴅ ᴛᴀʀɢᴇᴛ ʟɪɴᴋ!</blockquote></b>",
                parse_mode=ParseMode.HTML,
            )
        if not s_chat or not s_id:
            return await message.reply_text(
                "<b><blockquote expandable>❌ ɪɴᴠᴀʟɪᴅ sᴏᴜʀᴄᴇ ʟɪɴᴋ!</blockquote></b>",
                parse_mode=ParseMode.HTML,
            )

        target_chat, target_msg_id = t_chat, t_id
        source_chat, source_msg_id = s_chat, s_id

    # Method 2: One link provided while replying to a message
    elif message.reply_to_message and len(message.command) >= 2:
        link = message.command[1]
        l_chat, l_id, _ = parse_link(link)

        if not l_chat or not l_id:
            return await message.reply_text(
                "<b><blockquote expandable>❌ ɪɴᴠᴀʟɪᴅ ʟɪɴᴋ!</blockquote></b>",
                parse_mode=ParseMode.HTML,
            )

        replied = message.reply_to_message

        # Inside Channel or Supergroup (Replying directly to target message)
        if message.chat.type in [ChatType.CHANNEL, ChatType.SUPERGROUP, ChatType.GROUP]:
            target_chat = message.chat.id
            target_msg_id = replied.id
            source_chat = l_chat
            source_msg_id = l_id

        # Inside Private Chat (PM)
        else:
            # If replied message was forwarded from a channel (Target is forwarded post)
            f_chat, f_msg_id = get_forward_origin_info(replied)
            if f_chat:
                target_chat = f_chat
                target_msg_id = f_msg_id
                source_chat = l_chat
                source_msg_id = l_id
            # If replying to media/file sent in PM (Target is the link, Source is replied message)
            else:
                target_chat = l_chat
                target_msg_id = l_id
                source_msg = replied

    else:
        return await message.reply_text(
            "<b><blockquote expandable>ᴜsᴀɢᴇ:\n\n"
            "1. ᴛᴡᴏ ʟɪɴᴋs ᴍᴇᴛʜᴏᴅ:\n"
            "<code>/replace &lt;target_link&gt; &lt;source_link&gt;</code>\n\n"
            "2. ʀᴇᴘʟʏ ᴛᴏ ᴍᴇᴅɪᴀ ɪɴ ʙᴏᴛ ᴘᴍ:\n"
            "ʀᴇᴘʟʏ ᴛᴏ ʏᴏᴜʀ ᴠɪᴅᴇᴏ/ғɪʟᴇ ᴡɪᴛʜ:\n"
            "<code>/replace &lt;target_channel_link&gt;</code>\n\n"
            "3. ʀᴇᴘʟʏ ᴛᴏ ᴄʜᴀɴɴᴇʟ ᴘᴏsᴛ ɪɴ ᴄʜᴀɴɴᴇʟ:\n"
            "<code>/replace &lt;source_link&gt;</code></blockquote></b>",
            parse_mode=ParseMode.HTML,
        )

    status = await message.reply_text(
        "<b><blockquote expandable>⚡ ʀᴇᴘʟᴀᴄɪɴɢ ɪɴsᴛᴀɴᴛʟʏ...</blockquote></b>",
        parse_mode=ParseMode.HTML,
    )
    start_time = time.time()

    # Resolve target chat
    try:
        await client.get_chat(target_chat)
    except Exception as e:
        return await status.edit_text(
            f"<b><blockquote expandable>❌ ᴄᴀɴɴᴏᴛ ᴀᴄᴄᴇss ᴛᴀʀɢᴇᴛ ᴄʜᴀᴛ (<code>{target_chat}</code>)!\n"
            f"ᴍᴀᴋᴇ sᴜʀᴇ ʙᴏᴛ ɪs ᴀᴅᴅᴇᴅ ᴀs ᴀᴅᴍɪɴ: <code>{e}</code></blockquote></b>",
            parse_mode=ParseMode.HTML,
        )

    # Fetch target message
    try:
        target_msg = await client.get_messages(target_chat, target_msg_id)
        if not target_msg or target_msg.empty:
            return await status.edit_text(
                f"<b><blockquote expandable>❌ ᴛᴀʀɢᴇᴛ ᴍᴇssᴀɢᴇ (<code>{target_msg_id}</code>) ɴᴏᴛ ғᴏᴜɴᴅ ɪɴ ᴛᴀʀɢᴇᴛ ᴄʜᴀᴛ!</blockquote></b>",
                parse_mode=ParseMode.HTML,
            )
    except Exception as e:
        return await status.edit_text(
            f"<b><blockquote expandable>❌ ғᴀɪʟᴇᴅ ᴛᴏ ғᴇᴛᴄʜ ᴛᴀʀɢᴇᴛ ᴍᴇssᴀɢᴇ: <code>{e}</code></blockquote></b>",
            parse_mode=ParseMode.HTML,
        )

    # Fetch source message if not already set
    if not source_msg:
        try:
            await client.get_chat(source_chat)
            source_msg = await client.get_messages(source_chat, source_msg_id)
            if not source_msg or source_msg.empty:
                return await status.edit_text(
                    f"<b><blockquote expandable>❌ sᴏᴜʀᴄᴇ ᴍᴇssᴀɢᴇ (<code>{source_msg_id}</code>) ɴᴏᴛ ғᴏᴜɴᴅ ɪɴ sᴏᴜʀᴄᴇ ᴄʜᴀᴛ!</blockquote></b>",
                    parse_mode=ParseMode.HTML,
                )
        except Exception as e:
            return await status.edit_text(
                f"<b><blockquote expandable>❌ ғᴀɪʟᴇᴅ ᴛᴏ ғᴇᴛᴄʜ sᴏᴜʀᴄᴇ ᴍᴇssᴀɢᴇ: <code>{e}</code></blockquote></b>",
                parse_mode=ParseMode.HTML,
            )

    # Validate type compatibility
    input_media = get_input_media(source_msg)
    if not target_msg.media and input_media:
        return await status.edit_text(
            "<b><blockquote expandable>❌ ᴛᴇʟᴇɢʀᴀᴍ ʟɪᴍɪᴛᴀᴛɪᴏɴ:\n"
            "ʏᴏᴜ ᴄᴀɴɴᴏᴛ ʀᴇᴘʟᴀᴄᴇ ᴀ ᴛᴇxᴛ-ᴏɴʟʏ ᴘᴏsᴛ ᴡɪᴛʜ ᴍᴇᴅɪᴀ!\n"
            "ᴛʜᴇ ᴛᴀʀɢᴇᴛ ᴘᴏsᴛ ᴍᴜsᴛ ᴀʟʀᴇᴀᴅʏ ʙᴇ ᴀ ᴍᴇᴅɪᴀ ᴘᴏsᴛ.</blockquote></b>",
            parse_mode=ParseMode.HTML,
        )
    if target_msg.media and not input_media and source_msg.text:
        return await status.edit_text(
            "<b><blockquote expandable>❌ ᴛᴇʟᴇɢʀᴀᴍ ʟɪᴍɪᴛᴀᴛɪᴏɴ:\n"
            "ʏᴏᴜ ᴄᴀɴɴᴏᴛ ʀᴇᴘʟᴀᴄᴇ ᴀ ᴍᴇᴅɪᴀ ᴘᴏsᴛ ᴡɪᴛʜ ᴘʟᴀɪɴ ᴛᴇxᴛ!</blockquote></b>",
            parse_mode=ParseMode.HTML,
        )

    try:
        await replace_message(client, target_chat, target_msg_id, source_msg)
        elapsed = round(time.time() - start_time, 2)
        await status.edit_text(
            f"<b><blockquote expandable>✅ sᴜᴄᴄᴇssғᴜʟʟʏ ʀᴇᴘʟᴀᴄᴇᴅ!\n⏱ ᴛɪᴍᴇ ᴛᴀᴋᴇɴ: <code>{elapsed}s</code></blockquote></b>",
            parse_mode=ParseMode.HTML,
        )

    except FloodWait as e:
        await asyncio.sleep(e.value)
        await replace_message(client, target_chat, target_msg_id, source_msg)
        await status.edit_text(
            "<b><blockquote expandable>✅ sᴜᴄᴄᴇssғᴜʟʟʏ ʀᴇᴘʟᴀᴄᴇᴅ ᴀғᴛᴇʀ ғʟᴏᴏᴅᴡᴀɪᴛ!</blockquote></b>",
            parse_mode=ParseMode.HTML,
        )
    except RPCError as e:
        await status.edit_text(
            f"<b><blockquote expandable>❌ ᴛᴇʟᴇɢʀᴀᴍ ʀᴘᴄ ᴇʀʀᴏʀ: <code>{e}</code></blockquote></b>",
            parse_mode=ParseMode.HTML,
        )
    except Exception as e:
        await status.edit_text(
            f"<b><blockquote expandable>❌ ᴇʀʀᴏʀ: <code>{e}</code></blockquote></b>",
            parse_mode=ParseMode.HTML,
        )


# ================== 2. Batch Replace ================== #
# Open to all users too, same force-sub gate. Kept slightly stricter
# (still usable by anyone, but capped at 200/run) since it's heavier.
@Client.on_message(filters.command(["batch"]))
@error_handler
async def batch_replace_cmd(client: Client, message: Message):
    if not await enforce_fsub(client, message):
        return

    if len(message.command) < 3:
        return await message.reply_text(
            "<b><blockquote expandable>ᴜsᴀɢᴇ:\n\n"
            "ᴍᴇᴛʜᴏᴅ 1 (ᴡɪᴛʜ ᴄᴏᴜɴᴛ):\n"
            "<code>/batch &lt;target_link&gt; &lt;source_link&gt; &lt;count&gt;</code>\n"
            "ᴇxᴀᴍᴘʟᴇ: <code>/batch https://t.me/c/123/10 https://t.me/c/456/50 5</code>\n\n"
            "ᴍᴇᴛʜᴏᴅ 2 (ᴡɪᴛʜ ʀᴀɴɢᴇ):\n"
            "<code>/batch https://t.me/c/123/10-15 https://t.me/c/456/50</code></blockquote></b>",
            parse_mode=ParseMode.HTML,
        )

    target_link = message.command[1]
    source_link = message.command[2]

    t_chat, t_start_id, t_end_id = parse_link(target_link)
    s_chat, s_start_id, _ = parse_link(source_link)

    if not t_chat or not t_start_id or not s_chat or not s_start_id:
        return await message.reply_text(
            "<b><blockquote expandable>❌ ɪɴᴠᴀʟɪᴅ ʟɪɴᴋ ғᴏʀᴍᴀᴛ!</blockquote></b>",
            parse_mode=ParseMode.HTML,
        )

    if t_end_id:
        count = (t_end_id - t_start_id) + 1
    elif len(message.command) >= 4:
        try:
            count = int(message.command[3])
        except ValueError:
            return await message.reply_text(
                "<b><blockquote expandable>❌ ɪɴᴠᴀʟɪᴅ ᴄᴏᴜɴᴛ! ᴘʟᴇᴀsᴇ ᴘʀᴏᴠɪᴅᴇ ᴀ ɴᴜᴍʙᴇʀ.</blockquote></b>",
                parse_mode=ParseMode.HTML,
            )
    else:
        return await message.reply_text(
            "<b><blockquote expandable>❌ ᴘʟᴇᴀsᴇ sᴘᴇᴄɪғʏ ʜᴏᴡ ᴍᴀɴʏ ᴘᴏsᴛs ᴛᴏ ʀᴇᴘʟᴀᴄᴇ!</blockquote></b>",
            parse_mode=ParseMode.HTML,
        )

    if count <= 0 or count > 200:
        return await message.reply_text(
            "<b><blockquote expandable>❌ ᴄᴏᴜɴᴛ ᴍᴜsᴛ ʙᴇ ʙᴇᴛᴡᴇᴇɴ 1 ᴀɴᴅ 200.</blockquote></b>",
            parse_mode=ParseMode.HTML,
        )

    status = await message.reply_text(
        f"<b><blockquote expandable>🚀 sᴛᴀʀᴛɪɴɢ ʙᴀᴛᴄʜ ʀᴇᴘʟᴀᴄᴇ...\nᴛᴏᴛᴀʟ ᴘᴏsᴛs: <code>{count}</code></blockquote></b>",
        parse_mode=ParseMode.HTML,
    )

    # Resolve channels once
    try:
        await client.get_chat(t_chat)
        await client.get_chat(s_chat)
    except Exception as e:
        return await status.edit_text(
            f"<b><blockquote expandable>❌ ᴄᴀɴɴᴏᴛ ᴀᴄᴄᴇss ᴄʜᴀɴɴᴇʟs: <code>{e}</code></blockquote></b>",
            parse_mode=ParseMode.HTML,
        )

    success = 0
    failed = 0
    start_time = time.time()

    for i in range(count):
        curr_t_id = t_start_id + i
        curr_s_id = s_start_id + i

        try:
            s_msg = await client.get_messages(s_chat, curr_s_id)
            if not s_msg or s_msg.empty:
                failed += 1
                continue

            t_msg = await client.get_messages(t_chat, curr_t_id)
            if not t_msg or t_msg.empty:
                failed += 1
                continue

            s_media = get_input_media(s_msg)
            if not t_msg.media and s_media:
                failed += 1
                continue
            if t_msg.media and not s_media and s_msg.text:
                failed += 1
                continue

            await replace_message(client, t_chat, curr_t_id, s_msg)
            success += 1
            await asyncio.sleep(0.15)

        except FloodWait as e:
            await asyncio.sleep(e.value)
            try:
                await replace_message(client, t_chat, curr_t_id, s_msg)
                success += 1
            except Exception:
                failed += 1
        except Exception:
            failed += 1

        if (i + 1) % 3 == 0 or (i + 1) == count:
            try:
                await status.edit_text(
                    f"<b><blockquote expandable>⚡ ʙᴀᴛᴄʜ ᴘʀᴏᴄᴇssɪɴɢ ɪɴ ᴘʀᴏɢʀᴇss...\n"
                    f"✅ sᴜᴄᴄᴇss: <code>{success}</code>\n"
                    f"❌ ғᴀɪʟᴇᴅ: <code>{failed}</code>\n"
                    f"📊 ᴘʀᴏɢʀᴇss: <code>{i + 1}/{count}</code></blockquote></b>",
                    parse_mode=ParseMode.HTML,
                )
            except Exception:
                pass

    total_time = round(time.time() - start_time, 2)
    await status.edit_text(
        f"<b><blockquote expandable>🎉 ʙᴀᴛᴄʜ ʀᴇᴘʟᴀᴄᴇ ᴄᴏᴍᴘʟᴇᴛᴇᴅ!\n\n"
        f"✅ sᴜᴄᴄᴇss: <code>{success}</code>\n"
        f"❌ ғᴀɪʟᴇᴅ: <code>{failed}</code>\n"
        f"⏱ ᴛᴏᴛᴀʟ ᴛɪᴍᴇ: <code>{total_time}s</code></blockquote></b>",
        parse_mode=ParseMode.HTML,
    )
