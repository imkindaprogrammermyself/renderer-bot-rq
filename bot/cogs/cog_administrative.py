import json
import pickle
import time
import zlib
from io import BytesIO, StringIO
from os import getenv

from Cryptodome.Cipher import AES
from discord import (Attachment, DiscordException, Embed, File, Guild, Member,
                     Message, Permissions, TextChannel)
from discord.ext import commands
from discord.ext.commands import Bot, Cog, CommandError, Context
from discord.ext.commands.errors import (CheckFailure, MissingPermissions,
                                         MissingRequiredArgument)
from dotenv import load_dotenv
from utils.constants import GREEN, ORANGE, RED
from utils.helpers import check_environ_vars
from utils.logger import LOGGER_BOT, command_logger, logger_extra
from utils.redisconn import ASYNC_REDIS, REDIS
from utils.strings import *

from ..checks import check_is_authorized
from ..message import MSG_ERROR, MSG_OK, MSG_WARN, create_bot_message

check_environ_vars(LOGGER_BOT, 'BACKUP_KEY',
                   'BOT_REQUIRED_PERM', 'SETTINGS_PREFIX')
VALID_SETTINGS = {'FPS': (int, 15, 60), 'QUALITY': (int, 1, 10)}
SETTINGS_PREFIX = getenv("SETTINGS_PREFIX")


class Administrative(Cog):
    def __init__(self, bot):
        self._bot: Bot = bot
        self._channel_controller: TextChannel = self._bot.get_channel(
            int(REDIS.get(f"{SETTINGS_PREFIX}.BOT_CONTROL_CHANNEL")))
        LOGGER_BOT.info("Administrative cog loaded.")

    @commands.command("broadcast")
    @commands.check(check_is_authorized)
    @command_logger(color=0x990099)
    async def _broadcast(self, ctx: Context, *args):
        """
        Broadcast a message to each channels.
        :param ctx: Context
        :param args: Messages
        """
        message = ' '.join(args)

        try:
            async for guild_key in ASYNC_REDIS.scan_iter("guild.*.render-channels"):
                guild_key = guild_key.decode()
                guild: Guild = self._bot.get_guild(
                    int(guild_key.split('.')[1]))

                async for channel_id in ASYNC_REDIS.sscan_iter(guild_key):
                    channel_id = int(channel_id.decode())

                    if channel := guild.get_channel(channel_id):
                        channel: TextChannel
                        permissions: Permissions = channel.permissions_for(
                            guild.get_member(self._bot.user.id))
                        try:
                            if permissions.send_messages and permissions.embed_links:
                                await channel.send(embed=create_bot_message(message, GREEN))
                            elif permissions.send_messages and not permissions.embed_links:
                                await channel.send(content=message)
                            else:
                                LOGGER_BOT.error(msg="No permission to send or embed a message.",
                                                 extra=logger_extra(channel))
                        except Exception as e:
                            LOGGER_BOT.error(e, exc_info=e)
        except Exception as e:
            LOGGER_BOT.error(e, exc_info=e)

    ##########
    # EVENTS #
    ##########

    @Cog.listener()
    async def on_command_error(self, ctx: Context, error: CommandError):
        """
        Catches all the bot errors and logs it or display the error to the user.
        :param ctx: Context.
        :param error: Thrown error.
        """
        try:
            await ctx.message.delete()
        except Exception:
            pass

        if isinstance(error, (CheckFailure, MissingPermissions)):
            embed = create_bot_message(
                f"{MSG_WVL344} {ctx.author.mention}", MSG_ERROR)
        elif isinstance(error, MissingRequiredArgument):
            embed = create_bot_message(
                f"{MSG_GDX897} {ctx.author.mention}", MSG_ERROR)
        else:
            embed = create_bot_message(
                f"{MSG_IBK358} {ctx.author.mention}", MSG_ERROR)

        exception_message = f"{error.__class__.__name__}: {embed.description}"

        try:
            await ctx.send(embed=embed)
        except Exception:
            pass

        extra_data = logger_extra(ctx, command=ctx.message.content)
        LOGGER_BOT.warning(msg=exception_message,
                           exc_info=error, extra=extra_data)

    def _get_messageable_channels(self, guild: Guild) -> list[TextChannel]:
        """
        Gets messageable channels. Checks each channels if it is messageable by the bot and put it in a list.
        :param guild: Guild
        :return:
        """
        valid_channels: list[TextChannel] = []
        member: Member = guild.get_member(self._bot.user.id)

        for channel in guild.channels:
            channel: TextChannel
            permissions: Permissions = channel.permissions_for(member)
            if permissions.send_messages and isinstance(channel, TextChannel):
                valid_channels.append(channel)

        return valid_channels

    @Cog.listener()
    async def on_guild_join(self, guild: Guild):
        """
        Called when a bot joins a guild.
        Automatically leaves the guild if the guild is in the banned list.
        Automatically leaves the guild if the guild is not in whitelist.
        :param guild: Guild.
        """

        valid_channels: list[TextChannel] = self._get_messageable_channels(
            guild)

        try:
            if await ASYNC_REDIS.sismember(f"{SETTINGS_PREFIX}.BANNED_SERVERS", guild.id):
                if valid_channels:
                    picked_channel = random.choice(valid_channels)
                    await picked_channel.send(content=MSG_ZPI560)
                else:
                    if owner := guild.owner:
                        try:
                            await owner.send(content=MSG_TRN372.format(guild.name))
                        except Exception as e:
                            LOGGER_BOT.error(exc_info=e)
                await guild.leave()
        except Exception as e:
            await guild.leave()
            LOGGER_BOT.error(e, exc_info=e)

        try:
            if not await ASYNC_REDIS.sismember(f"{SETTINGS_PREFIX}.BOT_SERVER_WHITELIST", guild.id):
                LOGGER_BOT.info(
                    f"Bot has joined {guild.name}({guild.id}) server. (Not whitelisted)")
                try:
                    if valid_channels:
                        picked_channel = random.choice(valid_channels)
                        await picked_channel.send(content=MSG_TAW064)
                    else:
                        if owner := guild.owner:
                            try:
                                await owner.send(content=MSG_SLJ122.format(guild.name))
                            except Exception as e:
                                LOGGER_BOT.error(exc_info=e)
                    await guild.leave()
                except Exception as e:
                    LOGGER_BOT.error(exc_info=e)
                    await guild.leave()
            else:
                LOGGER_BOT.info(
                    f"Bot has joined {guild.name}({guild.id}) server.")
        except Exception as e:
            LOGGER_BOT.error(e, exc_info=e)

    @Cog.listener()
    async def on_guild_remove(self, guild: Guild):
        """
        Called when removed from a guild.
        Deletes the guild and its channels in db.
        :param guild: Guild.
        """
        try:
            whitelist_key = f"{SETTINGS_PREFIX}.BOT_SERVER_WHITELIST"
            await ASYNC_REDIS.delete(f"guild.{guild.id}.render-channels")
            await ASYNC_REDIS.delete(f"guild.{guild.id}.extract-channels")
            await ASYNC_REDIS.srem(whitelist_key, guild.id)
        except Exception as e:
            LOGGER_BOT.error(e, exc_info=e)
        else:
            LOGGER_BOT.info(f"Bot has left {guild.name}({guild.id}) server.")

    ##############
    # LISTENHERE #
    ##############

    @commands.command(name="renderhere")
    @commands.has_permissions(manage_channels=True)
    @command_logger(color=0x990099)
    async def _render_here(self, ctx: Context):
        """
        Tells the bot to listen here for render commands.
        :param ctx: Context.
        :return: None.
        """

        channel_id: int = ctx.channel.id

        embed: Embed = Embed(title=MSG_OIJ303, color=GREEN)
        embed.set_thumbnail(url=MSG_YSL748)
        guild_channels_key = f"guild.{ctx.guild.id}.render-channels"

        try:
            if not await self._bot_has_required_perm(ctx):
                return

            if await ASYNC_REDIS.sismember(guild_channels_key, channel_id):
                embed.description = MSG_BYY733
                await ctx.send(embed=embed)
                return

            embed.description = MSG_OTZ736
            await ctx.send(embed=embed)

            await ASYNC_REDIS.sadd(guild_channels_key, channel_id)
            LOGGER_BOT.info(f"(Renderer) Bot now renders to {ctx.guild.name}({ctx.guild.id})'s "
                            f"{ctx.channel.name}({ctx.channel.id})")
        except Exception as e:
            LOGGER_BOT.error(e, exc_info=e)
        return

    @commands.command(name="dontrenderhere")
    @commands.has_permissions(manage_channels=True)
    @command_logger(color=0x990099)
    async def _dont_render_here(self, ctx: Context):
        """
        Tells the bot not to listen here for render commands.
        :param ctx: Context.
        :return: None.
        """

        channel_id: int = ctx.channel.id

        embed: Embed = Embed(title=MSG_OIJ303, color=ORANGE)
        embed.set_thumbnail(url=MSG_YSL748)
        guild_channels_key = f"guild.{ctx.guild.id}.render-channels"

        try:
            if not await ASYNC_REDIS.sismember(guild_channels_key, channel_id):
                embed.description = MSG_SRW302
                await ctx.send(embed=embed)
                return

            embed.description = MSG_CWD754
            await ctx.send(embed=embed)

            await ASYNC_REDIS.srem(guild_channels_key, channel_id)
            LOGGER_BOT.info(f"(Renderer) Bot will not render to {ctx.guild.name}({ctx.guild.id})'s "
                            f"{ctx.channel.name}({ctx.channel.id})")
        except Exception as e:
            LOGGER_BOT.error(e, exc_info=e)
        return

    @commands.command(name="extracthere")
    @commands.has_permissions(manage_channels=True)
    @command_logger(color=0x990099)
    async def _extract_here(self, ctx: Context):
        """
        Tells the bot to listen here for extract commands.
        :param ctx: Context.
        :return: None.
        """

        channel_id: int = ctx.channel.id

        embed: Embed = Embed(title=MSG_OIJ303, color=GREEN)
        embed.set_thumbnail(url=MSG_YSL748)
        guild_channels_key = f"guild.{ctx.guild.id}.extract-channels"

        try:
            if not await self._bot_has_required_perm(ctx):
                return

            if await ASYNC_REDIS.sismember(guild_channels_key, channel_id):
                embed.description = MSG_MBO040
                await ctx.send(embed=embed)
                return

            embed.description = MSG_IBJ760
            await ctx.send(embed=embed)

            await ASYNC_REDIS.sadd(guild_channels_key, channel_id)
            LOGGER_BOT.info(f"(Renderer) Bot now extracts chat messages to {ctx.guild.name}({ctx.guild.id})'s "
                            f"{ctx.channel.name}({ctx.channel.id})")
        except Exception as e:
            LOGGER_BOT.error(e, exc_info=e)
        return

    @commands.command(name="dontextracthere")
    @commands.has_permissions(manage_channels=True)
    @command_logger(color=0x990099)
    async def _dont_extract_here(self, ctx: Context):
        """
        Tells the bot not to listen here for extract commands.
        :param ctx: Context.
        :return: None.
        """

        channel_id: int = ctx.channel.id

        embed: Embed = Embed(title=MSG_OIJ303, color=ORANGE)
        embed.set_thumbnail(url=MSG_YSL748)
        guild_channels_key = f"guild.{ctx.guild.id}.extract-channels"

        try:
            if not await ASYNC_REDIS.sismember(guild_channels_key, channel_id):
                embed.description = MSG_SBJ866
                await ctx.send(embed=embed)
                return

            embed.description = MSG_OXK728
            await ctx.send(embed=embed)

            await ASYNC_REDIS.srem(guild_channels_key, channel_id)
            LOGGER_BOT.info(f"(Renderer) Bot will not extract messages to {ctx.guild.name}({ctx.guild.id})'s "
                            f"{ctx.channel.name}({ctx.channel.id})")
        except Exception as e:
            LOGGER_BOT.error(e, exc_info=e)
        return

    @commands.command("whitelist")
    @commands.check(check_is_authorized)
    @command_logger(color=0x990099)
    async def _whitelist(self, ctx: Context, guild_id: str):
        """
        Add the guild to the whitelist.
        :param ctx:
        :param guild_id:
        :return:
        """
        try:
            int_guild_id = int(guild_id)
        except ValueError:
            await ctx.send(embed=create_bot_message("Invalid guild id.", RED))
            return

        whitelist_key = f"{SETTINGS_PREFIX}.BOT_SERVER_WHITELIST"
        await ASYNC_REDIS.sadd(whitelist_key, int_guild_id)
        await ctx.send(embed=create_bot_message(f"Guild id: `{int_guild_id}` is now added to the whitelist.", GREEN))

    @commands.command("unwhitelist")
    @commands.check(check_is_authorized)
    @command_logger(color=0x990099)
    async def _unwhitelist(self, ctx: Context, guild_id: str):
        """
        Remove the guild from the whitelist.
        :param ctx:
        :param guild_id:
        :return:
        """
        try:
            int_guild_id = int(guild_id)
        except ValueError:
            await ctx.send(embed=create_bot_message("Invalid guild id.", RED))
            return

        whitelist_key = f"{SETTINGS_PREFIX}.BOT_SERVER_WHITELIST"
        if await ASYNC_REDIS.srem(whitelist_key, int_guild_id):
            embed = create_bot_message(f"Guild id: `{int_guild_id}` was now removed from the whitelist.",
                                       GREEN)
        else:
            embed = create_bot_message(f"Guild id: `{int_guild_id}` wasn't even in the whitelist.",
                                       ORANGE)

        await ctx.send(embed=embed)
        LOGGER_BOT.info(embed.description)

    async def _bot_has_required_perm(self, ctx: Context):
        """
        Check if the bot has required permissions. Then logs it if it doesn't meet all required permissions.
        Tries to send a message to the channel too to tell what permission(s) is missing.
        :param ctx: Context.
        :return: Bool.
        """
        guild: Guild = ctx.guild
        channel: TextChannel = ctx.channel
        perms_obj: Permissions = channel.permissions_for(
            guild.get_member(self._bot.user.id))
        permissions = json.loads(getenv('BOT_REQUIRED_PERM'))
        dict_resolved_perms = {' '.join(p.split('_')).capitalize(): getattr(
            perms_obj, p) for p in permissions}

        if not all(dict_resolved_perms.values()):
            lines = [MSG_SPS820, "```"]

            for perm_name, have_perm in dict_resolved_perms.items():
                spaced_perm_name = f"{perm_name}{' ' * (len(max(permissions, key=len)) - len(perm_name))}"
                lines.append(
                    f"{spaced_perm_name}{' : '}{'✔️' if have_perm else '❌'}")

            lines.append('```')
            lines.append(MSG_ZLD216)
            joined_lines = '\n'.join(lines)
            try:
                embed = Embed(title=MSG_OIJ303, color=ORANGE)
                embed.set_thumbnail(url=MSG_YSL748)
                embed.description = joined_lines
                await ctx.send(embed=embed)
            except DiscordException:
                await ctx.send(content='\n'.join(lines))

            extra = logger_extra(
                ctx, command=ctx.message.content, desc=joined_lines)
            LOGGER_BOT.warning(
                msg="Permission requirements not met.", extra=extra)
            return False
        return True

    ############
    # SETTINGS #
    ############

    @commands.group(name="settings")
    @commands.check(check_is_authorized)
    @command_logger(color=0x990099)
    async def settings(self, ctx: Context):
        """
        Base command.
        :param ctx: Context.
        """
        if ctx.invoked_subcommand is None:
            await ctx.send(embed=create_bot_message(MSG_RAR548, MSG_WARN))

    @settings.command(name="set")
    @command_logger(color=0x990099)
    async def _settings_set(self, ctx: Context, key: str, value: str):
        """
        Sets a setting value.
        :param ctx: Context.
        :param key: Setting name.
        :param value: Setting value.
        :return: None
        """
        key = key.upper()

        try:
            if key not in VALID_SETTINGS:
                await ctx.send(embed=create_bot_message(
                    f"You can only set {', '.join(f'`{s}`' for s in VALID_SETTINGS)} settings.", MSG_WARN))
                return

            value = VALID_SETTINGS[key][0](value)
            min_value = VALID_SETTINGS[key][1]
            max_value = VALID_SETTINGS[key][2]

            if not min_value <= value <= max_value:
                raise ValueError("range", min_value, max_value)

            await ASYNC_REDIS.set(f"{SETTINGS_PREFIX}.{key}", value)
            await ctx.send(embed=create_bot_message(MSG_RLV149.format(key, value), MSG_OK))
        except ValueError as e:
            msg_val = (MSG_VNJ492.format(
                *e.args[1:]), MSG_ERROR) if e.args[0] == "range" else (MSG_KND322, MSG_ERROR)
            await ctx.send(embed=create_bot_message(*msg_val))

        except Exception as e:
            LOGGER_BOT.error(e, exc_info=e)
            await ctx.send(embed=create_bot_message(MSG_OTK071, MSG_ERROR))
        return

    @settings.command(name="get")
    @command_logger(color=0x990099)
    async def _settings_get(self, ctx: Context, key: str):
        """
        Gets the setting value.
        :param ctx: Context.
        :param key: Setting name.
        :return: None.
        """
        key_upper = key.upper()

        try:
            if key_upper not in VALID_SETTINGS:
                await ctx.send(
                    embed=create_bot_message(MSG_SOR600.format(', '.join(f'`{s}`' for s in VALID_SETTINGS)), MSG_WARN))
                return

            setting_value = await ASYNC_REDIS.get(f"{SETTINGS_PREFIX}.{key_upper}")
            setting_value = setting_value.decode()
            await ctx.send(embed=create_bot_message(MSG_DSQ832.format(key_upper, setting_value), MSG_OK))
        except Exception as e:
            LOGGER_BOT.error(e, exc_info=e)
            await ctx.send(embed=create_bot_message(MSG_OTK071, MSG_ERROR))

    ############
    # CHANNELS #
    ############

    @commands.group("renderchannels")
    @commands.check(check_is_authorized)
    @command_logger(color=0x990099)
    async def _render_channels(self, ctx: Context):
        """
        Gets all the render channels' info and put it in a text file.
        :param ctx: Context.
        """
        try:
            channels: list[TextChannel] = []

            async for guild_channel_keys in ASYNC_REDIS.scan_iter("guild.*.render-channels"):
                async for channel in ASYNC_REDIS.sscan_iter(guild_channel_keys):
                    try:
                        if ch := self._bot.get_channel(int(channel)):
                            channels.append(ch)
                    except Exception:
                        pass

            messages: list[str] = []

            for ch in channels:
                try:
                    messages.append(MSG_JDU141.format(
                        ch.guild.name, ch.guild.id, ch.name, ch.id))
                except Exception:
                    pass

            messages_compiled = "".join(messages)

            with StringIO(messages_compiled) as reader:
                await ctx.send(file=File(reader, "render_channels.txt"))

        except Exception as e:
            LOGGER_BOT.error(e, exc_info=e)

    @commands.group("extractchannels")
    @commands.check(check_is_authorized)
    @command_logger(color=0x990099)
    async def _extract_channels(self, ctx: Context):
        """
        Gets all the extract channels' info and put it in a text file.
        :param ctx: Context.
        """
        try:
            channels: list[TextChannel] = []

            async for guild_channel_keys in ASYNC_REDIS.scan_iter("guild.*.extract-channels"):
                async for channel in ASYNC_REDIS.sscan_iter(guild_channel_keys):
                    try:
                        if ch := self._bot.get_channel(int(channel)):
                            channels.append(ch)
                    except Exception:
                        pass

            messages: list[str] = []

            for ch in channels:
                try:
                    messages.append(MSG_JDU141.format(
                        ch.guild.name, ch.guild.id, ch.name, ch.id))
                except Exception:
                    pass

            messages_compiled = "".join(messages)

            with StringIO(messages_compiled) as reader:
                await ctx.send(file=File(reader, "extract_channels.txt"))

        except Exception as e:
            LOGGER_BOT.error(e, exc_info=e)

    ##########
    # GUILDS #
    ##########

    @commands.group(name="guilds")
    @commands.check(check_is_authorized)
    @command_logger(color=0x990099)
    async def _guilds(self, ctx: Context):
        """
        Base command.
        :param ctx: Context.
        """
        if ctx.invoked_subcommand is None:
            await ctx.send(embed=create_bot_message(MSG_RAR548, MSG_WARN))

    @_guilds.group(name="list")
    @command_logger(color=0x990099)
    async def _guilds_list(self, ctx: Context):
        """
        Lists the joined guilds and put it in a text file.
        :param ctx: Context.
        """
        joined_guilds = '\n'.join(MSG_ESG543.format(
            guild.name, guild.id) for guild in self._bot.guilds)

        with StringIO(joined_guilds) as f:
            await ctx.send(file=File(f, filename="guilds.txt"))

    @_guilds.group(name="leave")
    @command_logger(color=0x990099)
    async def _guild_leave(self, ctx: Context, guild_id):
        """
        Leaves the guild specified by the guild id.
        :param ctx: Context.
        :param guild_id: Guild id.
        """
        try:
            if guild := self._bot.get_guild(int(guild_id)):
                guild: Guild
                await guild.leave()
            else:
                await ctx.send(embed=create_bot_message(MSG_YDV932.format(guild_id), MSG_ERROR))
        except Exception as e:
            LOGGER_BOT.error(e, exc_info=e)

    @_guilds.group(name="ban")
    @command_logger(color=0x990099)
    async def _guild_ban(self, ctx: Context, guild_id):
        """
        Bands the guild specified by the guild id.
        :param ctx: Context.
        :param guild_id: Guild id.
        """
        try:
            if guild := self._bot.get_guild(int(guild_id)):
                guild: Guild
                await ASYNC_REDIS.sadd(f"{SETTINGS_PREFIX}.BANNED_SERVERS", guild_id)
                await ctx.send(embed=create_bot_message(MSG_CEO189.format(guild.name), MSG_OK))
                await guild.leave()
        except ValueError as e:
            await ctx.send(embed=create_bot_message(MSG_VKI313, MSG_ERROR))
            LOGGER_BOT.error(e, exc_info=e)
        except Exception as e:
            await ctx.send(embed=create_bot_message(MSG_OTK071, MSG_ERROR))
            LOGGER_BOT.error(e, exc_info=e)

    @_guilds.group(name="unban")
    @command_logger(color=0x990099)
    async def _guild_unban(self, ctx: Context, guild_id):
        """
        Unbans the guild specified by the guild id.
        :param ctx: Context.
        :param guild_id: Guild id.
        """
        try:
            if ASYNC_REDIS.srem(f"{SETTINGS_PREFIX}.BANNED_SERVERS", guild_id):
                await ctx.send(embed=create_bot_message(MSG_PHL602.format(guild_id), MSG_OK))
            else:
                await ctx.send(embed=create_bot_message(MSG_FAF070.format(guild_id), MSG_OK))
        except Exception as e:
            LOGGER_BOT.error(e, exc_info=e)

    @commands.command("backup")
    @commands.check(check_is_authorized)
    @command_logger(color=0x990099)
    async def _backup(self, ctx: Context):
        """
        Backups the guilds, banned guilds and the .env file, encrypts it then put it in a file.
        :param ctx: Context.
        """
        try:
            filename = f"backup_{int(time.time())}.backup"

            backup = {
                "guilds_render_channels": [],
                "guilds_extract_channels": [],
                "banned_guilds": [],
                "whitelisted_guilds": [],
                "env": ""
            }

            try:
                with open('.env', 'r') as f:
                    backup['env'] = f.read()
            except Exception as e:
                LOGGER_BOT.warning(e, exc_info=e, extra=logger_extra(
                    ctx, result="Error at loading .env file."))

            # WHITELISTED GUILDS:
            async for whitelisted_guild_id in ASYNC_REDIS.sscan_iter(f"{SETTINGS_PREFIX}.BOT_SERVER_WHITELIST"):
                backup["whitelisted_guilds"].append(
                    whitelisted_guild_id.decode("utf-8"))

            # GUILDS' CHANNELS
            async for guild_channel_keys in ASYNC_REDIS.scan_iter("guild.*.render-channels"):
                try:
                    guild_info = {}
                    guild_channel_keys = guild_channel_keys.decode("utf-8")
                    guild: Guild = self._bot.get_guild(
                        int(guild_channel_keys.split('.')[1]))
                    guild_info["id"] = guild.id
                    channels = []

                    async for channel_id in ASYNC_REDIS.sscan_iter(guild_channel_keys):
                        try:
                            channel_info = {}
                            channel_id = channel_id.decode()
                            channel: TextChannel = guild.get_channel(
                                int(channel_id))

                            if channel:
                                channel_info['id'] = channel.id
                                channels.append(channel_info)
                        except Exception:
                            pass

                    guild_info['channels'] = channels
                    if guild_info:
                        backup['guilds_render_channels'].append(guild_info)
                except Exception:
                    pass

            # GUILDS' EXTRACT CHANNELS
            async for guild_channel_keys in ASYNC_REDIS.scan_iter("guild.*.extract-channels"):
                try:
                    guild_info = {}
                    guild_channel_keys = guild_channel_keys.decode("utf-8")
                    guild: Guild = self._bot.get_guild(
                        int(guild_channel_keys.split('.')[1]))
                    guild_info["id"] = guild.id
                    channels = []

                    async for channel_id in ASYNC_REDIS.sscan_iter(guild_channel_keys):
                        try:
                            channel_info = {}
                            channel_id = channel_id.decode()
                            channel: TextChannel = guild.get_channel(
                                int(channel_id))

                            if channel:
                                channel_info['id'] = channel.id
                                channels.append(channel_info)
                        except Exception:
                            pass

                    guild_info['channels'] = channels
                    if guild_info:
                        backup['guilds_extract_channels'].append(guild_info)
                except Exception:
                    pass

            # BANNED GUILDS

            async for banned_guild_ids in ASYNC_REDIS.sscan_iter(f"{SETTINGS_PREFIX}.BANNED_SERVERS"):
                banned_guild_ids = banned_guild_ids.decode()
                backup['banned_guilds'].append(int(banned_guild_ids))

            cipher = AES.new(
                getenv('BACKUP_KEY').encode('utf-8'), AES.MODE_EAX)
            encoded = pickle.dumps(backup)
            data_compressed = zlib.compress(encoded)
            data_encrypted, tag = cipher.encrypt_and_digest(data_compressed)

            with BytesIO() as f:
                f.write(cipher.nonce)
                f.write(tag)
                f.write(data_encrypted)
                f.seek(0)
                await ctx.send(file=File(f, filename))
        except Exception as e:
            LOGGER_BOT.error(e, exc_info=e)

    @commands.command("restore")
    @commands.check(check_is_authorized)
    @command_logger(color=0x990099)
    async def _restore(self, ctx: Context):
        """
        Restores the uploaded backup file.
        :param ctx:
        :return:
        """
        message: Message = ctx.message
        try:
            if not message.attachments:
                await ctx.send(embed=create_bot_message(MSG_AUR237, MSG_ERROR))
                return

            uploaded_file: Attachment = message.attachments[0]

            with BytesIO() as f:
                await uploaded_file.save(f)
                f.seek(0)
                nonce = f.read(16)
                tag = f.read(16)
                data_encrypted = f.read()

                cipher = AES.new(getenv('BACKUP_KEY').encode(
                    'utf-8'), AES.MODE_EAX, nonce=nonce)
                data_decrypted = cipher.decrypt_and_verify(data_encrypted, tag)
                data_decompressed = zlib.decompress(data_decrypted)
                data: dict = pickle.loads(data_decompressed)

                # guilds
                for guild in data['guilds_render_channels']:
                    await ASYNC_REDIS.sadd(f"guild.{guild['id']}.render-channels",
                                           *[ch['id'] for ch in guild['channels']])

                for guild in data['guilds_extract_channels']:
                    await ASYNC_REDIS.sadd(f"guild.{guild['id']}.extract-channels",
                                           *[ch['id'] for ch in guild['channels']])

                # banned
                if banned_guilds := data['banned_guilds']:
                    await ASYNC_REDIS.sadd(f"{SETTINGS_PREFIX}.BANNED_SERVERS", *banned_guilds)

                if whitelisted_guilds := data['whitelisted_guilds']:
                    await ASYNC_REDIS.sadd(f"{SETTINGS_PREFIX}.BOT_SERVER_WHITELIST", *whitelisted_guilds)

                # env
                with StringIO(data['env']) as env_data:
                    load_dotenv(stream=env_data)

                await ctx.send(embed=create_bot_message(MSG_GOW660, MSG_OK))

        except Exception as e:
            await ctx.send(embed=create_bot_message(MSG_OTK071, MSG_ERROR))
            LOGGER_BOT.exception(None, exc_info=e)

    @commands.command("restoreguilds")
    @commands.check(check_is_authorized)
    @command_logger(color=0x990099)
    async def _restore_guilds(self, ctx: Context):
        message: Message = ctx.message
        try:
            if not message.attachments:
                await ctx.send(embed=create_bot_message(MSG_JMP230, MSG_ERROR))
                return

            uploaded_file: Attachment = message.attachments[0]

            with BytesIO() as f:
                await uploaded_file.save(f)
                f.seek(0)

                guilds_channels: dict = json.load(f)

                for k, v in guilds_channels.items():
                    if v:
                        await ASYNC_REDIS.sadd(f"guild.{k}.render-channels", *v)

                await ASYNC_REDIS.sadd(f"{SETTINGS_PREFIX}.BOT_SERVER_WHITELIST", *list(guilds_channels))

        except Exception as e:
            await ctx.send(embed=create_bot_message(MSG_OTK071, MSG_ERROR))
            LOGGER_BOT.exception(None, exc_info=e)
