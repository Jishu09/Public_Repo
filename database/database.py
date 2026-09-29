from datetime import datetime, timezone

import motor.motor_asyncio
from pymongo.errors import DuplicateKeyError

from config import DB_NAME, MONGO_URI


class Database:
    def __init__(self, uri: str, database_name: str):
        self.client = motor.motor_asyncio.AsyncIOMotorClient(uri)
        self.db = self.client[database_name]
        self.users = self.db.users

    # ------------------------------------------------------------ #
    #                            USERS                             #
    # ------------------------------------------------------------ #
    @staticmethod
    def new_user(user_id: int, username: str = None, first_name: str = None) -> dict:
        return {
            "_id": user_id,
            # Some shared/reused Atlas clusters may already carry a
            # (unique) index on a `user_id` field from another project.
            # We keep it populated with the same value as `_id` so any
            # such legacy index is satisfied instead of colliding on
            # repeated `null` values (see DuplicateKeyError guard below
            # and ensure_indexes()).
            "user_id": user_id,
            "username": username,
            "first_name": first_name,
            "joined_date": datetime.now(timezone.utc),
        }

    async def is_user_exist(self, user_id: int) -> bool:
        found = await self.users.find_one({"_id": user_id})
        return bool(found)

    async def add_user(self, user_id: int, username: str = None, first_name: str = None) -> bool:
        """Inserts the user if new. Returns True if this is a brand new user."""
        if await self.is_user_exist(user_id):
            return False
        try:
            await self.users.insert_one(self.new_user(user_id, username, first_name))
            return True
        except DuplicateKeyError:
            # Already exists (race condition, or a stray legacy index) -
            # never crash the handler over this.
            return False

    async def delete_user(self, user_id: int) -> None:
        await self.users.delete_one({"_id": user_id})

    async def total_users_count(self) -> int:
        return await self.users.count_documents({})

    def get_all_users(self):
        """Returns an async cursor over every stored user document."""
        return self.users.find({})

    async def ensure_indexes(self) -> None:
        """
        Best-effort cleanup: drop any leftover unique index on `user_id`
        that isn't part of this bot's own schema (our real primary key
        is `_id`). Safe to call every startup - silently does nothing if
        the index is absent or the DB user lacks index-management rights.
        """
        try:
            existing = await self.users.index_information()
            for name, info in existing.items():
                if name == "_id_":
                    continue
                keys = info.get("key", [])
                if info.get("unique") and any(k[0] == "user_id" for k in keys):
                    await self.users.drop_index(name)
        except Exception:
            pass


db = Database(MONGO_URI, DB_NAME)
