import io
import asyncio

import asyncpg
import discord
from discord.ext import commands

from cogs import utils


class SimpTracker(utils.Cog):

    @commands.command(cls=utils.Command)
    @commands.bot_has_permissions(send_messages=True)
    @commands.guild_only()
    async def add(self, ctx:utils.Context, user:discord.Member):
        """Sets you as simping for a user"""

        # No pls not yourself
        if user == ctx.author:
            return await ctx.send("Well, _obviously_.")

        # Add to db
        async with self.bot.database() as db:
            try:
                await db("INSERT INTO simping_users (user_id, guild_id, simping_for) VALUES ($1, $2, $3)", ctx.author.id, ctx.guild.id, user.id)
            except asyncpg.UniqueViolationError:
                return await ctx.send(f"You're already simping for {user.mention}!", allowed_mentions=discord.AllowedMentions(users=False))

        # Add to cache
        utils.SimpableUser.get_simpable_user(ctx.author.id, ctx.guild.id).add_simping_for(user.id)
        utils.SimpableUser.get_simpable_user(user.id, ctx.guild.id).add_being_simped_by(ctx.author.id)

        # Respond
        await ctx.send(f"You're now simping for {user.mention}~", allowed_mentions=discord.AllowedMentions(users=False))

    @commands.command(cls=utils.Command)
    @commands.bot_has_permissions(send_messages=True)
    @commands.guild_only()
    async def remove(self, ctx:utils.Context, user:discord.Member):
        """Removes you from simping for a user"""

        # No pls not yourself
        if user == ctx.author:
            return await ctx.send("Well, _obviously_.")

        # Add to db
        async with self.bot.database() as db:
            await db("DELETE FROM simping_users WHERE user_id=$1 AND guild_id=$2 AND simping_for=$3", ctx.author.id, ctx.guild.id, user.id)

        # Add to cache
        utils.SimpableUser.get_simpable_user(ctx.author.id, ctx.guild.id).remove_simping_for(user.id)
        utils.SimpableUser.get_simpable_user(user.id, ctx.guild.id).remove_being_simped_by(ctx.author.id)

        # Respond
        await ctx.send(f"You're no longer simping for {user.mention} :<", allowed_mentions=discord.AllowedMentions(users=False))

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
        working = [utils.SimpableUser.get_simpable_user(user.id, ctx.guild.id)]  # people to be looked at

        # Go through each valid user
        while working:

            # Look at the first user
            current = working[0]

            # See if we already added them
            if current.user_id in already_added:
                working.remove(current)
                continue

            # See if they're in the server
            current_member = ctx.guild.get_member(current.user_id)
            if current_member is None:
                already_added.add(current.user_id)
                working.remove(current)
                continue

            # Add their name
            current_name = str(current_member).replace('"', '\\"')
            v = f'{current.user_id}[label="{current_name}"];'
            if v not in lines:
                lines.append(v)

            # Add who they simpin for
            for u in current.simping_for:
                v = f'{current.user_id}->{u.user_id};'
                if v not in lines:
                    lines.append(v)
            for u in current.being_simped_by:
                v = f'{u.user_id}->{current.user_id};'
                if v not in lines:
                    lines.append(v)
            for u in [i for i in current.simping_for if i in current.being_simped_by]:
                for x in [f'{current.user_id}->{u.user_id};', f'{u.user_id}->{current.user_id};', f'{current.user_id}->{u.user_id}[dir=both,color=red];', f'{u.user_id}->{current.user_id}[dir=both,color=red];']:
                    try:
                        lines.remove(x)
                    except ValueError:
                        pass
                lines.append(f'{current.user_id}->{u.user_id}[dir=both,color=red];')

            # And add them to the list of users to look at
            already_added.add(current.user_id)
            working.extend(current.simping_for)
            working.extend(current.being_simped_by)
            working.remove(current)

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
        await ctx.send(text, file=file)


def setup(bot:utils.Bot):
    x = SimpTracker(bot)
    bot.add_cog(x)
