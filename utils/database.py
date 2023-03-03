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

from typing_extensions import Self

import asyncpg

__all__ = (
    'SimpUser',
)


pool: asyncpg.Pool = None  # pyright: ignore


class SimpUser:
    """
    A user who is simping for another user within a guild.
    """

    __slots__ = (
        'guild_id',
        'user_id',
        'simping_for',
    )
    __table__ = "simping_users"
    _table_create = """
        CREATE TABLE IF NOT EXISTS {table} (
            guild_id BIGINT,
            user_id BIGINT,
            simping_for BIGINT,
            PRIMARY KEY (guild_id, user_id, simping_for)
        );
    """.format(table=__table__)

    guild_id: int
    user_id: int
    simping_for: int

    def __init__(
            self,
            *,
            guild_id: int,
            user_id: int,
            simping_for: int):
        self.guild_id = guild_id
        self.user_id = user_id
        self.simping_for = simping_for

    @classmethod
    def from_record(cls, r: asyncpg.Record) -> Self:
        """
        Create an instance from a record.
        """

        return cls(
            guild_id=r["guild_id"],
            user_id=r["user_id"],
            simping_for=r["simping_for"],
        )

    @classmethod
    async def fetch(
            cls,
            *,
            guild_id: int,
            user_id: int | None = None,
            simping_for: int | None = None) -> list[Self]:
        """
        Get a user from the database.

        Parameters
        ----------
        guild_id : int
            The ID of the guild that you want to fetch the user from.
        user_id : int | None
            The ID of the user that you want to fetch.
        simping_for : int | None
            The ID of the user who you want to get who people are simping for.

        Returns
        -------
        list[SimpUser]
            A list of users that match the given criteria.
        """

        # Build the query
        table = cls.__table__
        where: list[str] = [
            f"{table}.guild_id = $1",
        ]
        if user_id is not None and simping_for is not None:
            where.append(f"{table}.user_id = $2")
            where.append(f"{table}.simping_for = $3")
        elif user_id is not None:
            where.append(f"{table}.user_id = $2")
        elif simping_for is not None:
            where.append(f"{table}.simping_for = $2")
        args = [i for i in [guild_id, user_id, simping_for] if i is not None]

        # Run the query
        conn: asyncpg.Connection
        async with pool.acquire() as conn:
            rows: list[asyncpg.Record] = await conn.fetch(
                (
                    """SELECT * FROM {table} WHERE {where}"""
                    .format(table=table, where=" AND ".join(where))
                ),
                *args,
            )
        return [cls.from_record(i) for i in rows]

    @classmethod
    async def create(
            cls,
            *,
            guild_id: int,
            user_id: int,
            simping_for: int) -> Self:
        """
        Create a simp user object.

        Parameters
        ----------
        guild_id : int
            The guild in which the simping is taking place.
        user_id : int
            The base user who is simping for another user.
        simping_for : int
            Who the base user is simping for.

        Returns
        -------
        SimpUser
            The created simp user instance.

        Raises
        ------
        ValueError
            The base user is already simping for the given target.
        """

        conn: asyncpg.Connection
        async with pool.acquire() as conn:
            try:
                rows: list[asyncpg.Record] = await conn.fetch(
                    """
                    INSERT INTO
                        {table}
                        (
                            guild_id,
                            user_id,
                            simping_for
                        )
                    VALUES
                        (
                            $1,
                            $2,
                            $3
                        )
                    RETURNING *
                    """.format(table=cls.__table__),
                    guild_id, user_id, simping_for,
                )
            except asyncpg.UniqueViolationError:
                raise ValueError()
        return [cls.from_record(i) for i in rows][0]

    @classmethod
    async def delete(
            cls,
            *,
            guild_id: int,
            user_id: int,
            simping_for: int) -> Self | None:
        """
        Delete a simp.

        Parameters
        ----------
        guild_id : int
            The guild in which the simping is taking place.
        user_id : int
            The base user who is simping for another user.
        simping_for : int
            Who the base user is simping for.

        Returns
        -------
        SimpUser | None
            The deleted simp user instance.
        """

        conn: asyncpg.Connection
        async with pool.acquire() as conn:
            rows: list[asyncpg.Record] = await conn.fetch(
                """
                DELETE FROM
                    {table}
                WHERE
                    guild_id = $1
                AND
                    user_id = $2
                AND
                    simping_for = $3
                RETURNING *
                """.format(table=cls.__table__),
                guild_id, user_id, simping_for,
            )
        try:
            return [cls.from_record(i) for i in rows][0]
        except IndexError:
            return None
