import os

# ==================================================================== #
#                         TELEGRAM API CREDENTIALS                     #
#            Get API_ID / API_HASH from https://my.telegram.org        #
#              Get BOT_TOKEN from https://t.me/BotFather                #
# ==================================================================== #
API_ID = int(os.environ.get("API_ID", ""))
API_HASH = os.environ.get("API_HASH", "")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")

# ==================================================================== #
#                          OWNER / ADMINS                              #
# ==================================================================== #
OWNER_ID = int(os.environ.get("OWNER_ID", "6163647625"))

_admin_env = os.environ.get("ADMINS", "")
ADMINS = [int(x) for x in _admin_env.split()] if _admin_env else []
if OWNER_ID and OWNER_ID not in ADMINS:
    ADMINS.append(OWNER_ID)

# ==================================================================== #
#                         MONGODB ATLAS DATABASE                       #
# ==================================================================== #
MONGO_URI = os.environ.get("MONGO_URI", "")
DB_NAME = os.environ.get("DB_NAME", "RareBotsHub")

# ==================================================================== #
#                    MULTI FORCE SUBSCRIBE CHANNELS                    #
#   Comma separated usernames or -100 chat ids.                        #
#   Example: -1001234567890,MyChannelUsername,-1009876543210           #
#                                                                        #
#   IMPORTANT: numeric ids are parsed as real Python `int`s below -     #
#   passing a -100 id as a plain string to Pyrogram breaks chat         #
#   resolution (it gets misread as a username).                        #
# ==================================================================== #
def _parse_channel(value: str):
    value = value.strip()
    if not value:
        return None
    if value.lstrip("-").isdigit():
        return int(value)
    return value.lstrip("@")


FORCE_SUB_CHANNELS = [
    ch
    for ch in (
        _parse_channel(x)
        for x in os.environ.get("FORCE_SUB_CHANNELS", "").split(",")
    )
    if ch is not None
]

# NOTE: there is intentionally NO per-user "verified/joined" cache
# anymore. Membership is checked live, straight from Telegram, on
# every single force-sub gate. A cached "joined" result was exactly
# what let people leave a channel right after passing and keep using
# the bot undetected until the cache expired. Only channel-level
# metadata (is the bot an admin there, what's its invite link) is
# cached, since that almost never changes:
FSUB_CHANNEL_CACHE_TTL = int(os.environ.get("FSUB_CHANNEL_CACHE_TTL", "1800"))

# ==================================================================== #
#                             START MESSAGE                            #
#      Comma separated image URLs -> one is picked randomly each time   #
# ==================================================================== #
_start_pics_env = os.environ.get("START_PICS", "")
START_PICS = [x.strip() for x in _start_pics_env.split(",") if x.strip()] or [
    ""
]

START_TEXT = """Hᴇʏ ᴛʜᴇʀᴇ, {mention}!

Wᴇʟᴄᴏᴍᴇ ᴛᴏ ᴛʜᴇ <b>Fɪʟᴇ Rᴇᴘʟᴀᴄᴇ Bᴏᴛ</b> ⚡️

Yᴏᴜ ᴄᴀɴ ᴇᴀsɪʟʏ ʀᴇᴘʟᴀᴄᴇ ᴍᴇssᴀɢᴇs ɪɴ ʏᴏᴜʀ ᴄʜᴀɴɴᴇʟ ᴡɪᴛʜ ɴᴇᴡ ғɪʟᴇs & ᴄᴀᴘᴛɪᴏɴs — ɪɴsᴛᴀɴᴛʟʏ, sɪɴɢʟʏ ᴏʀ ɪɴ ʙᴜʟᴋ!

<b><blockquote>‣ ᴍᴀɪɴᴛᴀɪɴᴇᴅ ʙʏ : <a href='https://t.me/Rare_Bots_Hub'>ʀᴀʀᴇ ʙᴏᴛꜱ ʜᴜʙ</a></blockquote></b>"""

HELP_TEXT = """<b>Hᴇʟᴘ Gᴜɪᴅᴇ</b>

<b><blockquote expandable>‣ /replace ‣
Rᴇᴘʟᴀᴄᴇs ᴀ sɪɴɢʟᴇ ᴘᴏsᴛ.

‣ Mᴇᴛʜᴏᴅ 1 (ᴛᴡᴏ ʟɪɴᴋs) :
<code>/replace &lt;target_link&gt; &lt;source_link&gt;</code>

‣ Mᴇᴛʜᴏᴅ 2 (ʀᴇᴘʟʏ ɪɴ ʙᴏᴛ ᴘᴍ) :
Rᴇᴘʟʏ ᴛᴏ ʏᴏᴜʀ ɴᴇᴡ ғɪʟᴇ ᴡɪᴛʜ
<code>/replace &lt;target_channel_link&gt;</code>

‣ Mᴇᴛʜᴏᴅ 3 (ɪɴsɪᴅᴇ ᴄʜᴀɴɴᴇʟ/ɢʀᴏᴜᴘ) :
Rᴇᴘʟʏ ᴛᴏ ᴛʜᴇ ᴘᴏsᴛ ᴡɪᴛʜ
<code>/replace &lt;source_link&gt;</code></blockquote></b>

<b><blockquote expandable>‣ /batch ‣
Rᴇᴘʟᴀᴄᴇs ᴍᴜʟᴛɪᴘʟᴇ ᴘᴏsᴛs ᴀᴛ ᴏɴᴄᴇ.

‣ Wɪᴛʜ ᴄᴏᴜɴᴛ :
<code>/batch &lt;target_link&gt; &lt;source_link&gt; &lt;count&gt;</code>

‣ Wɪᴛʜ ʀᴀɴɢᴇ :
<code>/batch &lt;target_link_start-end&gt; &lt;source_link&gt;</code></blockquote></b>

<b><blockquote expandable>‣ Aᴅᴍɪɴ Oɴʟʏ ‣
/status - ʙᴏᴛ & ᴜsᴇʀ sᴛᴀᴛs
/users - ᴛᴏᴛᴀʟ ᴜsᴇʀ ᴄᴏᴜɴᴛ
/broadcast - ʀᴇᴘʟʏ ᴛᴏ ᴀ ᴍsɢ ᴛᴏ ʙʀᴏᴀᴅᴄᴀsᴛ ɪᴛ ᴛᴏ ᴀʟʟ ᴜsᴇʀs</blockquote></b>"""

DEVELOPER_URL = "https://t.me/Sourov_Nobita"
UPDATE_CHANNEL_URL = "https://t.me/Rare_Bots_Hub"

# Optional: channel id (as int, e.g. -1001234567890) where new-user /
# broadcast logs are sent. Leave 0 to disable.
LOG_CHANNEL = int(os.environ.get("LOG_CHANNEL", "0"))
