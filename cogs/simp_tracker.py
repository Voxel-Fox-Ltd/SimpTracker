import asyncio

import asyncpg
import discord
from discord.ext import commands
import voxelbotutils as utils

from cogs import utils as localutils


class SimpTracker(utils.Cog):

    MAX_SIMPING_USERS = 3

    async def cache_setup(self, db):
        """
        Set up the cache of simpable users
        """

        # Get user settings
        data = await self.bot.get_all_table_data(db, "simping_users")
        for row in data:
            localutils.SimpableUser.get_simpable_user(row['user_id'], row['guild_id']).add_simping_for(row['simping_for'])
            localutils.SimpableUser.get_simpable_user(row['simping_for'], row['guild_id']).add_being_simped_by(row['user_id'])

    @utils.command()
    @commands.bot_has_permissions(send_messages=True)
    @commands.guild_only()
    async def add(self, ctx:utils.Context, user:discord.Member):
        """Sets you as simping for a user"""

        # No pls not yourself
        if user == ctx.author or user == ctx.guild.me:
            return await ctx.send("Well, _obviously_.")
        elif user.bot and ctx.original_author_id not in self.bot.owner_ids:
            return await ctx.send("That's just a bit sad, really.")

        # See if they're already simping for 3 people
        simpable_users_in_guild = [i for i in localutils.SimpableUser.get_simpable_user(ctx.author.id, ctx.guild.id).simping_for if ctx.guild.get_member(i.user_id) is not None]
        if len(simpable_users_in_guild) >= self.MAX_SIMPING_USERS and ctx.original_author_id not in self.bot.owner_ids:
            return await ctx.send(f"You can only simp for **{self.MAX_SIMPING_USERS}** users at once.")

        # Add to db
        async with self.bot.database() as db:
            try:
                await db("INSERT INTO simping_users (user_id, guild_id, simping_for) VALUES ($1, $2, $3)", ctx.author.id, ctx.guild.id, user.id)
            except asyncpg.UniqueViolationError:
                return await ctx.send(f"You're already simping for {user.mention}!", allowed_mentions=discord.AllowedMentions(users=False))

        # Add to cache
        localutils.SimpableUser.get_simpable_user(ctx.author.id, ctx.guild.id).add_simping_for(user.id)
        localutils.SimpableUser.get_simpable_user(user.id, ctx.guild.id).add_being_simped_by(ctx.author.id)

        # Respond
        await ctx.send(f"You're now simping for {user.mention}~", allowed_mentions=discord.AllowedMentions(users=False))

    @utils.command()
    @commands.bot_has_permissions(send_messages=True)
    @commands.guild_only()
    async def remove(self, ctx:utils.Context, user:discord.Member):
        """Removes you from simping for a user"""

        # No pls not yourself
        if user == ctx.author:
            return await ctx.send("Well, _obviously_.")
        elif user == ctx.guild.me:
            return await ctx.send("I won't pretend I'm not offended.")
        elif user.bot and ctx.original_author_id not in self.bot.owner_ids:
            return await ctx.send("Who needs bots, anyway?")

        # Add to db
        async with self.bot.database() as db:
            rows = await db("DELETE FROM simping_users WHERE user_id=$1 AND guild_id=$2 AND simping_for=$3 RETURNING *", ctx.author.id, ctx.guild.id, user.id)
        if not rows:
            return await ctx.send(f"You're not simping for {user.mention}!", allowed_mentions=discord.AllowedMentions(users=False))

        # Add to cache
        localutils.SimpableUser.get_simpable_user(ctx.author.id, ctx.guild.id).remove_simping_for(user.id)
        localutils.SimpableUser.get_simpable_user(user.id, ctx.guild.id).remove_being_simped_by(ctx.author.id)

        # Respond
        await ctx.send(f"You're no longer simping for {user.mention} :<", allowed_mentions=discord.AllowedMentions(users=False))

    @utils.command()
    @commands.bot_has_permissions(send_messages=True)
    @commands.guild_only()
    async def list(self, ctx:utils.Context, user:discord.Member=None):
        """List who's simping for you"""

        user = user or ctx.author
        simp_user = localutils.SimpableUser.get_simpable_user(user.id, ctx.guild.id)
        simping_for = [o for o in [ctx.guild.get_member(i.user_id) for i in simp_user.simping_for] if o]
        being_simped_by = [o for o in [ctx.guild.get_member(i.user_id) for i in simp_user.being_simped_by] if o]
        mutual_simping = [i for i in simping_for if i in being_simped_by]
        with utils.Embed(use_random_colour=True) as embed:
            embed.set_author_to_user(user)

            # Add simping for
            if [i for i in simping_for if i not in mutual_simping]:
                embed.add_field("Simping For", ", ".join([i.mention for i in simping_for if i not in mutual_simping]), inline=False)
            else:
                if not mutual_simping:
                    embed.add_field("Simping For", "Nobody... \N{THINKING FACE}")
                else:
                    embed.add_field("Simping For", "Nobody")

            # Add being simped by
            if [i for i in being_simped_by if i not in mutual_simping]:
                embed.add_field("Being Simped By", ", ".join([i.mention for i in being_simped_by if i not in mutual_simping]), inline=False)
            else:
                if not mutual_simping:
                    embed.add_field("Being Simped By", "Nobody... \N{UNAMUSED FACE}")
                else:
                    embed.add_field("Being Simped By", "Nobody")

            # Add mutuals
            if mutual_simping:
                embed.add_field("Mutual Simping owo", ", ".join([i.mention for i in mutual_simping]), inline=False)

        # And done
        return await ctx.send(embed=embed)

    @commands.command(cls=utils.Command, aliases=['tree', 't', 'st'])
    @utils.cooldown.cooldown(1, 60, commands.BucketType.member)
    @commands.bot_has_permissions(send_messages=True, attach_files=True, embed_links=True)
    @commands.guild_only()
    async def show(self, ctx:utils.Context, user:discord.Member=None):
        """See who's simping for who"""

        # See who we're lookin at
        user = user or ctx.author
        await ctx.trigger_typing()

        # Set up vars for our lines
        lines = []  # lines of dot
        already_added = set()  # user id list
        added_user_ids = set()
        working = [localutils.SimpableUser.get_simpable_user(user.id, ctx.guild.id)]  # people to be looked at

        # Go through each valid user
        while working:

            # Look at the first user
            current = working[0]
            added_user_ids.add(current.user_id)

            # See if we already added them
            if current.user_id in already_added:
                working.remove(current)
                continue

            # Add who they simpin for
            for u in current.simping_for:
                if ctx.guild.get_member(u.user_id) is None:
                    continue
                v = f'{current.user_id}->{u.user_id}'  # note - no semicolon
                if v not in lines:
                    lines.append(v)
                added_user_ids.add(u.user_id)

            # Add who they simpin by
            for u in current.being_simped_by:
                if ctx.guild.get_member(u.user_id) is None:
                    continue
                v = f'{u.user_id}->{current.user_id}'  # note - no semicolon
                if v not in lines:
                    lines.append(v)
                added_user_ids.add(u.user_id)

            # Remove both of those to make it bidirectional
            for u in [i for i in current.simping_for if i in current.being_simped_by]:
                if ctx.guild.get_member(u.user_id) is None:
                    continue
                for x in [f'{current.user_id}->{u.user_id}', f'{u.user_id}->{current.user_id}', f'{current.user_id}->{u.user_id}[dir=both,color=purple];', f'{u.user_id}->{current.user_id}[dir=both,color=purple];']:
                    try:
                        lines.remove(x)
                    except ValueError:
                        pass
                lines.append(f'{current.user_id}->{u.user_id}[dir=both,color=purple];')

            # And add them to the list of users to look at
            already_added.add(current.user_id)
            working.remove(current)

        # Remove people who aren't in the server
        for i in added_user_ids:
            member = ctx.guild.get_member(i)
            if member is not None:
                current_name = str(member).replace('"', '\\"')
                lines.insert(0, f'{i}[label="{current_name}"];')
                continue
            for line in lines:
                if str(i) in line:
                    try:
                        lines.remove(i)
                    except ValueError:
                        pass

        # Colour up some lines
        new_lines = []
        for index, line in enumerate(lines):
            if index == 0 or index == len(lines) - 1 or '[' in line:
                new_lines.append(line)
                continue
            if line.startswith(str(ctx.author.id)):
                new_lines.append(line + '[color=red];')
            else:
                new_lines.append(line + '[color=blue];')
        lines = new_lines

        # Now lets output that
        text = "" if len(lines) > 1 else ":c"
        lines.append("overlap=false;")
        dot_code = ''.join(lines)
        all_dot_code = 'digraph{' + dot_code + '}'
        try:
            with open(f'{self.bot.config["tree_file_location"].rstrip("/")}/{ctx.author.id}.gz', 'w', encoding='utf-8') as a:
                a.write(all_dot_code)
        except Exception as e:
            self.logger.error(f'Could not write to {self.bot.config["tree_file_location"].rstrip("/")}/{ctx.author.id}.gz')
            raise e

        # Convert to an image
        dot = await asyncio.create_subprocess_exec(*[
            'neato',
            '-Tpng:gd',
            f'{self.bot.config["tree_file_location"].rstrip("/")}/{ctx.author.id}.gz',
            '-o',
            f'{self.bot.config["tree_file_location"].rstrip("/")}/{ctx.author.id}.png',
            '-Gcharset=UTF-8',
        ], loop=self.bot.loop)
        await asyncio.wait_for(dot.wait(), 10.0, loop=self.bot.loop)

        # Kill subprocess
        try:
            dot.kill()
        except ProcessLookupError:
            pass  # It already died
        except Exception as e:
            raise e

        # Send file and delete cached
        file = discord.File(fp=f'{self.bot.config["tree_file_location"]}/{ctx.author.id}.png')
        embed = utils.Embed(use_random_colour=True).set_image(f"attachment://{ctx.author.id}.png")
        await ctx.send(text, file=file, embed=embed)


def setup(bot:utils.Bot):
    x = SimpTracker(bot)
    bot.add_cog(x)
