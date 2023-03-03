"""
Copyright (c) Kae Bartlett

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU Affero General Public License as published
by the Free Software Foundation, either version 3 of the License, or
any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
GNU Affero General Public License for more details.

You should have received a copy of the GNU Affero General Public License
along with this program. If not, see <https://www.gnu.org/licenses/>.
"""

from __future__ import annotations

from novus.ext import client
import asyncpg

import utils.database


class Database(client.Plugin):

    CONFIG = {
        "database_dsn": "",
    }

    async def on_load(self):
        if not self.bot.config.database_dsn:
            raise ValueError("Missing database DSN from config.")
        try:
            utils.database.pool = (
                await asyncpg.create_pool(self.bot.config.database_dsn)
            )
        except Exception as e:
            raise ValueError("Failed to create database pool.") from e
        else:
            await self.create_tables()

    async def create_tables(self):
        db: asyncpg.Connection
        async with utils.database.pool.acquire() as db:
            await db.execute(utils.database.SimpUser._table_create)
