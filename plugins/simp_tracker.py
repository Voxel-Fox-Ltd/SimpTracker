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

import random
from typing import cast
import asyncio
import os

import novus
from novus.ext import client

from utils.database import SimpUser


async def get_simp_limit(user_id: int) -> int:
    return {
        704708159901663302: 69,
        958819217984077935: 6,
    }.get(user_id, 5)


class SimpTracker(client.Plugin):

    @client.command(
        name="simp",
        description="Add a person that you're simping for.",
        options=[
            novus.ApplicationCommandOption(
                name="user",
                description="The user who you want to simp for.",
                type=novus.ApplicationOptionType.user,
            ),
        ],
        dm_permission=False,
        default_member_permissions=novus.Permissions(send_messages=True),
    )
    async def add(self, ctx: novus.types.CommandI, user: novus.User) -> None:
        """
        Allow a user to simp for another user.
        """

        # Disable yourself
        if ctx.user.id == user.id:
            return await ctx.send(
                "There's \"self love\" and then there's whatever _this_ is :/",
            )

        # Get the guild ID
        guild_id: int
        try:
            guild_id = ctx.data.guild.id  # pyright: ignore
        except AttributeError:
            return await ctx.send("This command cannot be run in DMs.")

        # See if they're already simping for that user.
        current_simping = await SimpUser.fetch(
            guild_id=guild_id,
            user_id=ctx.user.id,
        )
        if [i for i in current_simping if i.simping_for == user.id]:
            return await ctx.send(
                (
                    "This is very sweet and all, but {0}, you're _already_ "
                    "simping for {1} :/"
                ).format(ctx.user.mention, user.mention),
            )

        # Get their current simp count
        if (current := len(current_simping)) >= await get_simp_limit(ctx.user.id):
            return await ctx.send(
                (
                    "Sorry, {0}, you're already simping for **{1}** people - "
                    "you have hit the simp limit."
                ).format(ctx.user.mention, current),
            )

        # Add to database
        await SimpUser.create(
            guild_id=guild_id,
            user_id=ctx.user.id,
            simping_for=user.id,
        )
        await ctx.send(
            f"You are now simping for **{user.mention}**!",
            allowed_mentions=novus.AllowedMentions.none(),
        )

    @client.command(
        name="unsimp",
        description="Stop simping for a person.",
        dm_permission=False,
        default_member_permissions=novus.Permissions(send_messages=True),
    )
    async def remove(self, ctx: novus.types.CommandI) -> None:
        """
        Allow a user to stop simping for another user.
        """

        # Get the guild ID
        guild_id: int
        try:
            guild_id = ctx.data.guild.id  # pyright: ignore
        except AttributeError:
            return await ctx.send("This command cannot be run in DMs.")
        await ctx.defer(ephemeral=True)
        guild = ctx.data.guild
        assert guild
        guild = cast(novus.Guild, guild)

        # See if they're already simping for that user.
        current_simping = await SimpUser.fetch(
            guild_id=guild_id,
            user_id=ctx.user.id,
        )
        if not current_simping:
            return await ctx.send("You are not simping for anyone at the moment.")
        requested_users = await guild.chunk_members(
            user_ids=[i.simping_for for i in current_simping],
            wait=True,
        )
        users: dict[int, novus.GuildMember] = {}
        for ru in requested_users:
            users[ru.id] = ru

        # Send yes/no button for that user
        components = [
            novus.ActionRow([
                novus.StringSelectMenu(
                    options=[
                        novus.SelectOption(
                            label=(
                                str(users[i.simping_for])
                                if i.simping_for in users
                                else f"User ID {i.simping_for}"
                            ),
                            value=str(i.simping_for),
                        )
                        for i in current_simping
                    ],
                    custom_id="SIMP_REMOVE",
                ),
            ]),
        ]
        await ctx.send(
            f"Which user do you want to stop simping for?",
            components=components,
            ephemeral=True,
        )

    @client.event.filtered_component(r"SIMP_REMOVE")
    async def simp_remove_button_pressed(self, ctx: novus.types.ComponentI):
        """
        Remove a user from a user's list of simping.
        """

        selected_user = ctx.data.values[0]
        target = int(selected_user.value)
        try:
            guild_id: int = ctx.guild.id  # pyright: ignore
        except AttributeError:
            return await ctx.send("Missing guild ID from interaction.")
        d = await SimpUser.delete(
            guild_id=guild_id,
            user_id=ctx.user.id,
            simping_for=target,
        )
        if d is None:
            return await ctx.update(
                content=f"You're not simping for <@{target}> anyway :/",
                components=[],
            )
        else:
            return await ctx.update(
                content=f"You are no longer simping for <@{target}> :<",
                components=[],
            )

    @client.command(
        name="list",
        description="Show who is simping for whom.",
        options=[
            novus.ApplicationCommandOption(
                name="user",
                type=novus.ApplicationOptionType.user,
                description="The user who you want to check out.",
                required=False,
            ),
        ],
        dm_permission=False,
        default_member_permissions=novus.Permissions(send_messages=True),
    )
    async def simp_list_command(
            self,
            ctx: novus.types.CommandI,
            user: novus.User | novus.GuildMember | None = None):
        """
        Give the users list of who is simping for whom.
        """

        # Get the guild ID
        guild_id: int
        try:
            guild_id = ctx.data.guild.id  # pyright: ignore
        except AttributeError:
            return await ctx.send("This command cannot be run in DMs.")
        await ctx.defer()

        # Check out who they're simping for
        user = user or ctx.user
        simping_for: list[SimpUser] = [
            i
            for i in await SimpUser.fetch(
                guild_id=guild_id,
                user_id=user.id,
            )
        ]
        simped_by: list[SimpUser] = [
            i
            for i in await SimpUser.fetch(
                guild_id=guild_id,
                simping_for=user.id,
            )
        ]

        # Build up our embed
        embed = novus.Embed(color=random.randint(1, 0xffffff))
        if simping_for:
            val = f"{user.mention} is simping for **{len(simping_for)}** users:\n"
            for i in simping_for:
                ts = novus.utils.format_timestamp(
                    i.simp_start,
                    novus.TimestampFormat.relative,
                )
                val += f"<@{i.simping_for}> ({ts})\n"
            embed.add_field("Simping", val, inline=False)
        else:
            val = f"{user.mention} is not simping for anyone."
            embed.add_field("Simping", val, inline=False)
        if simped_by:
            val = f"{user.mention} is being simped by **{len(simped_by)}** users:\n"
            for i in simped_by:
                ts = novus.utils.format_timestamp(
                    i.simp_start,
                    novus.TimestampFormat.relative,
                )
                val += f"<@{i.user_id}> ({ts})\n"
            embed.add_field("Simped", val, inline=False)
        else:
            val = f"{user.mention} is not simped by anyone."
            embed.add_field("Simped", val, inline=False)

        # And done
        await ctx.send(embeds=[embed])

    @client.command(
        name="map",
        description="Show who is simping for whom - now with visuals!",
        options=[
            novus.ApplicationCommandOption(
                name="user",
                type=novus.ApplicationOptionType.user,
                description="The user who you want to check out.",
                required=False,
            ),
        ],
        dm_permission=False,
        default_member_permissions=novus.Permissions(send_messages=True),
    )
    async def map(
            self,
            ctx: novus.types.CommandI,
            user: novus.User | novus.GuildMember | None = None):
        """
        Map a user's simping.
        """

        # Get the guild ID
        guild_id: int
        try:
            guild_id = ctx.data.guild.id  # pyright: ignore
        except AttributeError:
            return await ctx.send("This command cannot be run in DMs.")
        await ctx.defer()
        guild = ctx.data.guild
        assert guild
        guild = cast(novus.Guild, guild)

        # Get the users to map
        user = user or ctx.user
        simping_for = [
            i.simping_for
            for i in await SimpUser.fetch(guild_id=guild_id, user_id=user.id)
        ]
        simped_by = [
            i.user_id
            for i in await SimpUser.fetch(guild_id=guild_id, simping_for=user.id)
        ]
        users = {
            user.id: user,
        }
        requested_users = await guild.chunk_members(
            user_ids=[*simping_for, *simped_by],
            wait=True,
        )
        for ru in requested_users:
            users[ru.id] = ru

        def escape_username(user: novus.User | novus.GuildMember) -> str:
            username = str(user)
            return username.replace('"', r'\"')

        # Build our relation mapping
        graphviz_lines: list[str] = [
            "digraph{",
            "overlap=false;",
            "bgcolor=transparent;",
            'node[fillcolor="white",style="filled",fontname="DejaVu Sans"];',
        ]
        for uid, usr in users.items():
            graphviz_lines.append(f'{uid}[label="{escape_username(usr)}"];')
        for simp in simping_for:
            graphviz_lines.append(f'{user.id}->{simp}[color="#AC393B"];')
        for simp in simped_by:
            graphviz_lines.append(f'{simp}->{user.id}[color="#6896CD"];')
        graphviz_lines.append("}")
        with open(f"{ctx.id}.gz", "w") as fp:
            fp.write("".join(graphviz_lines))

        # Run code
        dot = await asyncio.create_subprocess_exec(
            "neato",
            # '-Tpng:gd',
            "-Tpng",
            f"{ctx.id}.gz",
            "-o",
            f"{ctx.id}.png",
            "-Gcharset=UTF-8",
        )
        await dot.wait()
        file = novus.File(f"{ctx.id}.png", "image.png")
        embed = novus.Embed().set_image(f"attachment://image.png")
        await ctx.send(
            embeds=[embed],
            files=[file],
        )
        os.remove(f"{ctx.id}.gz")
        os.remove(f"{ctx.id}.png")
