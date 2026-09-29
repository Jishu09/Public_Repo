import logging

from pyrogram import Client, idle
from pyrogram.types import BotCommand, BotCommandScopeChat

from config import ADMINS, API_HASH, API_ID, BOT_TOKEN
from database.database import db

# -------------------------------------------------------------------- #
#                                LOGGING                                #
# -------------------------------------------------------------------- #
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s - %(levelname)s] - %(name)s - %(message)s",
    datefmt="%d-%b-%y %H:%M:%S",
)
logging.getLogger("pyrogram").setLevel(logging.WARNING)
log = logging.getLogger("RareBotsHub")


# -------------------------------------------------------------------- #
#                           TELEGRAM CLIENT                             #
# -------------------------------------------------------------------- #
app = Client(
    "RareBotsHubFileReplaceBot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    plugins=dict(root="RareBotsHub"),
)


# -------------------------------------------------------------------- #
#                    AUTO-REGISTER BOT COMMANDS                        #
#   No need to add these one by one via @BotFather - the bot sets its  #
#   own command list on every startup.                                 #
# -------------------------------------------------------------------- #
# Public commands - shown to EVERY user in the "/" menu, since
# /replace & /batch are now open to all users (force-sub gated).
PUBLIC_COMMANDS = [
    BotCommand("start", "Sᴛᴀʀᴛ ᴛʜᴇ ʙᴏᴛ"),
    BotCommand("replace", "Rᴇᴘʟᴀᴄᴇ ᴀ sɪɴɢʟᴇ ᴘᴏsᴛ"),
    BotCommand("batch", "Rᴇᴘʟᴀᴄᴇ ᴍᴜʟᴛɪᴘʟᴇ ᴘᴏsᴛs ᴀᴛ ᴏɴᴄᴇ"),
]

# Extra commands shown ONLY in an admin/owner's own chat with the bot.
ADMIN_ONLY_COMMANDS = [
    BotCommand("status", "Bᴏᴛ & ᴜsᴇʀ sᴛᴀᴛs"),
    BotCommand("users", "Tᴏᴛᴀʟ ᴜsᴇʀ ᴄᴏᴜɴᴛ"),
    BotCommand("broadcast", "Bʀᴏᴀᴅᴄᴀsᴛ ᴀ ᴍᴇssᴀɢᴇ ᴛᴏ ᴀʟʟ ᴜsᴇʀs"),
]


async def register_commands():
    # Default menu -> every user, everywhere (private chats, groups, etc.)
    await app.set_bot_commands(PUBLIC_COMMANDS)

    # Admin/owner private chats -> the full list on top of the public ones.
    for admin_id in ADMINS:
        try:
            await app.set_bot_commands(
                PUBLIC_COMMANDS + ADMIN_ONLY_COMMANDS,
                scope=BotCommandScopeChat(chat_id=admin_id),
            )
        except Exception as e:
            log.warning(f"Could not set admin command scope for {admin_id}: {e}")


# -------------------------------------------------------------------- #
#                                  MAIN                                 #
# -------------------------------------------------------------------- #
async def main():
    async with app:
        await db.ensure_indexes()
        await register_commands()
        me = await app.get_me()
        log.info(f"{me.first_name} started successfully as @{me.username}")
        await idle()
    log.info("Bot stopped. Bye!")


if __name__ == "__main__":
    app.run(main())
