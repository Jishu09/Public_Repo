# RareBotsHub — File Replace Bot

A Pyrofork-based Telegram bot whose main feature is **replacing media/captions
of already-posted channel messages** with new files — instantly, or in bulk —
without losing views/reactions on the original post.

## ✨ Features

- **`/replace`** & **`/batch`** — open to **all users** (not just admins),
  gated by live force-subscribe. Admins/owner always bypass.
- **`/start`** — multi-photo (randomized) welcome message with Help /
  Developer / Update Channel buttons, fully Small-Caps styled.
- **Live Multi Force-Subscribe** — checked straight against Telegram on
  every single gate, in parallel across all configured channels
  (fast, and no stale results):
  - Channels the bot isn't an admin in are **skipped automatically** —
    they never block anyone.
  - Real Telegram invite links (public `t.me/username` when available,
    otherwise an exported invite link).
  - A user who joins, passes, and then **leaves right after** is caught
    on their very next command — there is intentionally **no cached
    "already verified" state** to go stale (a channel-metadata cache
    exists for speed, but never for a user's live membership).
- **`/status`, `/users`, `/broadcast`** — admin-only, backed by
  MongoDB Atlas (broadcast auto-removes users who blocked the bot).
- **Auto command registration** — the bot sets its own command list
  with Telegram on every startup, no need to add them via @BotFather:
  everyone sees `/start`, `/replace`, `/batch`; admins additionally
  see `/status`, `/users`, `/broadcast` in their own chat.
- **Crash-proof photo sending** — `/start`'s welcome photo no longer
  crashes the handler if Telegram can't fetch one of the image URLs
  (`WEBPAGE_CURL_FAILED`). It shuffles through the configured pics,
  skips any that fail, caches the working ones as a `file_id` for
  instant/reliable reuse, and falls back to a text-only message if
  every single pic fails.
- **Global error handling** — every command/callback is wrapped so an
  unexpected exception is logged AND reported back to the user in
  chat, instead of the command silently doing nothing.
- No group-priority (`group=`) used anywhere — every handler runs in the
  default group.
- Fixed the `message.forward_from_chat` deprecation warning — now uses
  `message.forward_origin.chat` as recommended.
- Runs as a pure background **worker** (no web server, no port
  binding) — deploy-ready for **Heroku, Railway, Koyeb, and any VPS**
  (Docker included). See the Render note below.

## 📁 Structure

```
FileReplaceBot/
├── main.py                 # Entry point (client, index cleanup, auto commands)
├── config.py                # ALL variables, read from environment
├── helper_func.py           # Admin filter, live fsub engine, error_handler
├── requirements.txt
├── Procfile                  # worker: python3 main.py
├── app.json                  # Heroku one-click deploy (worker dyno)
├── render.yaml                # Render blueprint (worker service)
├── Dockerfile                 # VPS / Koyeb / any container host
├── runtime.txt
├── .env.sample
├── database/
│   └── database.py          # MongoDB Atlas (motor, async)
└── RareBotsHub/              # Plugins folder (auto-loaded)
    ├── start.py              # /start + force-sub + safe photo sending
    ├── replace.py            # Main feature: /replace & /batch (all users)
    └── admin.py              # /status, /users, /broadcast (admin only)
```

## ⚙️ Environment Variables

All variables live in `config.py` and are read from the environment —
set them on whichever platform you deploy to (see `.env.sample`):

| Variable | Required | Description |
|---|---|---|
| `API_ID` / `API_HASH` | ✅ | From <https://my.telegram.org> |
| `BOT_TOKEN` | ✅ | From [@BotFather](https://t.me/BotFather) |
| `OWNER_ID` | ✅ | Your numeric Telegram user ID |
| `ADMINS` | ❌ | Space-separated extra admin IDs |
| `MONGO_URI` | ✅ | MongoDB Atlas connection string |
| `DB_NAME` | ❌ | Defaults to `RareBotsHub` |
| `FORCE_SUB_CHANNELS` | ❌ | Comma-separated channel usernames/-100 ids |
| `FSUB_CHANNEL_CACHE_TTL` | ❌ | Seconds a resolved channel's admin-status/invite-link is cached (default `1800`) — this is metadata only, never a user's membership |
| `START_PICS` | ❌ | Comma-separated photo URLs for `/start` |
| `LOG_CHANNEL` | ❌ | Channel ID to log new users |

## 🚀 Deploy

### Heroku
Push this repo to GitHub, then create an app from it (or use `app.json`
with the Deploy button) and fill in the config vars. After deploying,
scale the **worker** dyno on (it's off by default on Heroku):
```bash
heroku ps:scale worker=1
```

### Railway
Auto-detects the `Procfile`'s `worker:` line. Just set the environment
variables from the table above and deploy.

### Koyeb
Deploy from the `Dockerfile` as a **Worker Service** (not a Web
Service, since there's no port to bind) and set the environment
variables.

### Render
⚠️ Render's **free tier only supports Web Services**; a true
background Worker (what this bot needs, no port binding) requires a
paid plan. `render.yaml` is included and configured as a `worker`
service — if you're on the free tier, use Railway, Koyeb, or a VPS
instead.

### VPS (Docker or plain)
```bash
git clone <your-repo-url> && cd FileReplaceBot
cp .env.sample .env   # fill it in
pip install -r requirements.txt
python3 main.py
```
or with Docker:
```bash
docker build -t rarebotshub-file-replace-bot .
docker run --env-file .env rarebotshub-file-replace-bot
```

## 🧩 Notes

- The bot must be an **admin** in both the source and target
  channels/groups to read and edit messages there.
- `/replace` and `/batch` are now open to **any Telegram user**, not
  just `OWNER_ID`/`ADMINS` — gated by force-sub instead. Since anyone
  who can get the bot added as admin to a channel can then edit posts
  in it via these commands, treat "who you add the bot to" as your
  real access control. `/status`, `/users`, and `/broadcast` remain
  admin-only.
- For force-sub channels, give the bot **"Invite Users via Link"**
  admin permission if the channel is private, so a real join link can
  be generated automatically. Public channels don't need this — their
  `t.me/username` link is used directly.
- If a configured force-sub channel is missing that permission (or
  the bot isn't an admin there at all), it's logged as a warning and
  either shown without a button (admin, no invite rights) or skipped
  entirely (not an admin) — it will never silently block all users.

---
Maintained by [ʀᴀʀᴇ ʙᴏᴛꜱ ʜᴜʙ](https://t.me/Rare_Bots_Hub) · Developer:
[@Sourov_Nobita](https://t.me/Sourov_Nobita)
