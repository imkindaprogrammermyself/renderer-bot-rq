import pickle
import time
import zlib
import os
import random
from io import BytesIO, StringIO
from os import getenv
from os.path import join

from Cryptodome.Cipher import AES
from discord import (
    Attachment,
    Embed,
    File,
    Guild,
    Member,
    Message,
    Permissions,
    TextChannel,
)
from discord.ext import commands
from discord.ext.commands import Bot, Cog, CommandError, Context
from discord.ext.commands.errors import (
    CheckFailure,
    MissingPermissions,
    MissingRequiredArgument,
    BadArgument,
)
from dotenv import load_dotenv
from utils.constants import GREEN, ORANGE, RED, BOX_MEGA, BOX_BIG, BOX_NORM
from utils.helpers import check_environ_vars
from utils.logger import LOGGER_BOT, command_logger, logger_extra
from utils.redisconn import ASYNC_REDIS, REDIS
from utils.strings import *

from ..checks import check_is_authorized
from ..message import MSG_ERROR, MSG_OK, MSG_WARN, create_bot_message

check_environ_vars(LOGGER_BOT, "BACKUP_KEY", "BOT_REQUIRED_PERM", "SETTINGS_PREFIX")
VALID_SETTINGS = {"FPS": (int, 15, 60), "QUALITY": (int, 1, 10)}
SETTINGS_PREFIX = getenv("SETTINGS_PREFIX")


class Administrative(Cog):
    def __init__(self, bot):
        self._bot: Bot = bot
        LOGGER_BOT.info("Administrative cog loaded.")

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
        embed = None

        if isinstance(error, (CheckFailure, MissingPermissions)):
            embed = create_bot_message(f"{MSG_WVL344} {ctx.author.mention}", MSG_ERROR)

        if isinstance(error, MissingRequiredArgument):
            embed = create_bot_message(f"{MSG_GDX897} {ctx.author.mention}", MSG_ERROR)

        if isinstance(error, BadArgument):
            embed = create_bot_message(
                f"Invalid argument. {ctx.author.mention}", MSG_ERROR
            )

        if embed:
            try:
                await ctx.send(embed=embed)
            except Exception:
                pass

        extra_data = logger_extra(ctx, command=ctx.message.content)
        LOGGER_BOT.warning(error, exc_info=error, extra=extra_data)

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

        valid_channels: list[TextChannel] = self._get_messageable_channels(guild)

        try:
            if await ASYNC_REDIS.sismember(
                f"{SETTINGS_PREFIX}.BANNED_SERVERS", guild.id
            ):
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
            if not await ASYNC_REDIS.sismember(
                f"{SETTINGS_PREFIX}.BOT_SERVER_WHITELIST", guild.id
            ):
                LOGGER_BOT.info(
                    f"Bot has joined {guild.name}({guild.id}) server. (Not whitelisted)"
                )
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
                LOGGER_BOT.info(f"Bot has joined {guild.name}({guild.id}) server.")
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
            await ASYNC_REDIS.srem("guilds.chat_extract", guild.id)
            await ASYNC_REDIS.srem(whitelist_key, guild.id)
        except Exception as e:
            LOGGER_BOT.error(e, exc_info=e)
        else:
            LOGGER_BOT.info(f"Bot has left {guild.name}({guild.id}) server.")

    @commands.command(name="enablechat")
    @commands.has_permissions(manage_channels=True)
    @command_logger(color=0x990099)
    async def _enable_chat_extract(self, ctx: Context):
        """Enables chat extract command to the server

        Args:
            ctx (Context): [Command context]
        """

        embed: Embed = Embed(title=MSG_OIJ303, color=GREEN)
        embed.set_thumbnail(url=MSG_YSL748)
        guild: Guild = ctx.channel.guild

        if await ASYNC_REDIS.sadd("guilds.chat_extract", guild.id):
            embed.description = MSG_ADS530.format(self._bot.command_prefix)
        else:
            embed.description = (
                f"{self._bot.command_prefix}chat is now enabled in this server."
            )
        await ctx.send(embed=embed)
        return

    @commands.command(name="disablechat")
    @commands.has_permissions(manage_channels=True)
    @command_logger(color=0x990099)
    async def _disable_chat_extract(self, ctx: Context):
        """Disables chat extract command to the server"""

        embed: Embed = Embed(title=MSG_OIJ303, color=GREEN)
        embed.set_thumbnail(url=MSG_YSL748)
        guild: Guild = ctx.channel.guild

        if await ASYNC_REDIS.srem("guilds.chat_extract", guild.id):
            embed.description = (
                f"{self._bot.command_prefix}chat is now disabled in this server."
            )
        else:
            embed.description = (
                f"{self._bot.command_prefix}chat is already disabled in this server."
            )

        await ctx.send(embed=embed)
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
        await ctx.send(
            embed=create_bot_message(
                f"Guild id: `{int_guild_id}` is now added to the whitelist.", GREEN
            )
        )

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
        except ValueError as e:
            await ctx.send(embed=create_bot_message("Invalid guild id.", RED))
            LOGGER_BOT.error(e, exc_info=e)
            return

        whitelist_key = f"{SETTINGS_PREFIX}.BOT_SERVER_WHITELIST"
        if await ASYNC_REDIS.srem(whitelist_key, int_guild_id):
            embed = create_bot_message(
                f"Guild id: `{int_guild_id}` was now removed from the whitelist.", GREEN
            )
        else:
            embed = create_bot_message(
                f"Guild id: `{int_guild_id}` wasn't even in the whitelist.", ORANGE
            )

        await ctx.send(embed=embed)
        LOGGER_BOT.info(embed.description)

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
                await ctx.send(
                    embed=create_bot_message(
                        f"You can only set {', '.join(f'`{s}`' for s in VALID_SETTINGS)} settings.",
                        MSG_WARN,
                    )
                )
                return

            value = VALID_SETTINGS[key][0](value)
            min_value = VALID_SETTINGS[key][1]
            max_value = VALID_SETTINGS[key][2]

            if not min_value <= value <= max_value:
                raise ValueError("range", min_value, max_value)

            await ASYNC_REDIS.set(f"{SETTINGS_PREFIX}.{key}", value)
            await ctx.send(
                embed=create_bot_message(MSG_RLV149.format(key, value), MSG_OK)
            )
        except ValueError as e:
            msg_val = (
                (MSG_VNJ492.format(*e.args[1:]), MSG_ERROR)
                if e.args[0] == "range"
                else (MSG_KND322, MSG_ERROR)
            )
            await ctx.send(embed=create_bot_message(*msg_val))

        except Exception as e:
            LOGGER_BOT.error(e, exc_info=e)
            await ctx.send(embed=create_bot_message(MSG_OTK071, MSG_ERROR))
        return

    @settings.command(name="get")
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
                    embed=create_bot_message(
                        MSG_SOR600.format(", ".join(f"`{s}`" for s in VALID_SETTINGS)),
                        MSG_WARN,
                    )
                )
                return

            setting_value = await ASYNC_REDIS.get(f"{SETTINGS_PREFIX}.{key_upper}")
            setting_value = setting_value.decode()
            await ctx.send(
                embed=create_bot_message(
                    MSG_DSQ832.format(key_upper, setting_value), MSG_OK
                )
            )
        except Exception as e:
            LOGGER_BOT.error(e, exc_info=e)
            await ctx.send(embed=create_bot_message(MSG_OTK071, MSG_ERROR))

    ##########
    # GUILDS #
    ##########

    @commands.group(name="guild")
    @commands.check(check_is_authorized)
    @command_logger(color=0x990099)
    async def _guilds(self, ctx: Context):
        """
        Base command.
        :param ctx: Context.
        """
        if ctx.invoked_subcommand is None:
            await ctx.send(embed=create_bot_message(MSG_RAR548, MSG_WARN))

    @_guilds.command(name="chat")
    async def _guilds_chat(self, ctx: Context):
        """
        Gets all the extract guilds' info and put it in a text file.
        :param ctx: Context.
        """
        try:
            messages: list[str] = []

            async for guild_id in ASYNC_REDIS.sscan_iter("guilds.chat_extract"):
                guild_id = int(guild_id)
                guild: Guild = self._bot.get_guild(guild_id)
                if guild:
                    messages.append(f"{guild.name} ({guild.id})")

            messages_compiled = "\n".join(messages) if messages else "Empty."

            with StringIO(messages_compiled) as reader:
                await ctx.send(file=File(reader, "chat_extract_guilds.txt"))

        except Exception as e:
            LOGGER_BOT.error(e, exc_info=e)

    @_guilds.group(name="list")
    async def _guilds_list(self, ctx: Context):
        """
        Lists the joined guilds and put it in a text file.
        :param ctx: Context.
        """
        joined_guilds = "\n".join(
            MSG_ESG543.format(guild.name, guild.id) for guild in self._bot.guilds
        )

        with StringIO(joined_guilds) as f:
            await ctx.send(file=File(f, filename="guilds.txt"))

    @_guilds.group(name="leave")
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
                await ctx.send(
                    embed=create_bot_message(MSG_YDV932.format(guild_id), MSG_ERROR)
                )
        except Exception as e:
            LOGGER_BOT.error(e, exc_info=e)

    @_guilds.group(name="ban")
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
                await ctx.send(
                    embed=create_bot_message(MSG_CEO189.format(guild.name), MSG_OK)
                )
                await guild.leave()
        except ValueError as e:
            await ctx.send(embed=create_bot_message(MSG_VKI313, MSG_ERROR))
            LOGGER_BOT.error(e, exc_info=e)
        except Exception as e:
            await ctx.send(embed=create_bot_message(MSG_OTK071, MSG_ERROR))
            LOGGER_BOT.error(e, exc_info=e)

    @_guilds.group(name="unban")
    async def _guild_unban(self, ctx: Context, guild_id):
        """
        Unbans the guild specified by the guild id.
        :param ctx: Context.
        :param guild_id: Guild id.
        """
        try:
            if ASYNC_REDIS.srem(f"{SETTINGS_PREFIX}.BANNED_SERVERS", guild_id):
                await ctx.send(
                    embed=create_bot_message(MSG_PHL602.format(guild_id), MSG_OK)
                )
            else:
                await ctx.send(
                    embed=create_bot_message(MSG_FAF070.format(guild_id), MSG_OK)
                )
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
                "guilds_chat_extract": [],
                "banned_guilds": [],
                "whitelisted_guilds": [],
                "env": "",
            }

            try:
                with open(".env", "r") as f:
                    backup["env"] = f.read()
            except Exception as e:
                LOGGER_BOT.warning(
                    e,
                    exc_info=e,
                    extra=logger_extra(ctx, result="Error at loading .env file."),
                )

            # WHITELISTED GUILDS:
            async for whitelisted_guild_id in ASYNC_REDIS.sscan_iter(
                f"{SETTINGS_PREFIX}.BOT_SERVER_WHITELIST"
            ):
                backup["whitelisted_guilds"].append(
                    whitelisted_guild_id.decode("utf-8")
                )

            # CHAT EXTRACT GUILDS:

            async for guild_channel_keys in ASYNC_REDIS.sscan_iter(
                "guilds.chat_extract"
            ):
                backup["guilds_chat_extract"].append(guild_channel_keys.decode("utf-8"))

            # BANNED GUILDS

            async for banned_guild_ids in ASYNC_REDIS.sscan_iter(
                f"{SETTINGS_PREFIX}.BANNED_SERVERS"
            ):
                banned_guild_ids = banned_guild_ids.decode()
                backup["banned_guilds"].append(int(banned_guild_ids))

            cipher = AES.new(getenv("BACKUP_KEY").encode("utf-8"), AES.MODE_EAX)
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

                cipher = AES.new(
                    getenv("BACKUP_KEY").encode("utf-8"), AES.MODE_EAX, nonce=nonce
                )
                data_decrypted = cipher.decrypt_and_verify(data_encrypted, tag)
                data_decompressed = zlib.decompress(data_decrypted)
                data: dict = pickle.loads(data_decompressed)

                # guilds

                try:
                    if guilds_chat_extract := data["guilds_chat_extract"]:
                        await ASYNC_REDIS.sadd(
                            "guilds.chat_extract", *guilds_chat_extract
                        )
                except Exception:
                    pass

                try:
                    if banned_guilds := data["banned_guilds"]:
                        await ASYNC_REDIS.sadd(
                            f"{SETTINGS_PREFIX}.BANNED_SERVERS", *banned_guilds
                        )
                except Exception:
                    pass

                try:
                    if whitelisted_guilds := data["whitelisted_guilds"]:
                        await ASYNC_REDIS.sadd(
                            f"{SETTINGS_PREFIX}.BOT_SERVER_WHITELIST",
                            *whitelisted_guilds,
                        )
                except Exception:
                    pass

                # env
                try:
                    with open(join(os.getcwd(), ".env"), "w") as f:
                        with StringIO(data["env"]) as env_data:
                            f.write(env_data.read())
                            env_data.seek(0)
                            load_dotenv(stream=env_data)
                except Exception as e:
                    pass

                await ctx.send(embed=create_bot_message(MSG_GOW660, MSG_OK))

        except Exception as e:
            await ctx.send(embed=create_bot_message(MSG_OTK071, MSG_ERROR))
            LOGGER_BOT.exception(None, exc_info=e)

    @commands.command("broadcast")
    @commands.check(check_is_authorized)
    @command_logger(color=0x990099)
    async def _broadcast(self, ctx: Context, *args):
        if not args:
            return

        async def _get_messageables():
            for channel in self._bot.get_all_channels():
                try:
                    permissions: Permissions = channel.permissions_for(channel.guild.me)
                    permitted = all(
                        [
                            permissions.send_messages,
                            permissions.read_message_history,
                        ]
                    )

                    if isinstance(channel, TextChannel) and permitted:
                        try:
                            counter = 0
                            async for message in channel.history(limit=50):
                                if message.author.id == self._bot.user.id:
                                    counter += 1
                            if counter > 10:
                                yield channel
                        except Exception:
                            pass
                except Exception:
                    pass

        async for messageable in _get_messageables():
            if messageable:
                await messageable.send(" ".join(args))

    @commands.command("farewell")
    @commands.check(check_is_authorized)
    @command_logger(color=0x990099)
    async def _farewell(self, ctx: Context, *args):
        async def _get_messageables():
            for channel in self._bot.get_all_channels():
                try:
                    permissions: Permissions = channel.permissions_for(channel.guild.me)
                    permitted = all(
                        [
                            permissions.send_messages,
                            permissions.read_message_history,
                        ]
                    )

                    if isinstance(channel, TextChannel) and permitted:
                        try:
                            counter = 0
                            async for message in channel.history(limit=50):
                                if message.author.id == self._bot.user.id:
                                    counter += 1
                            if counter > 5:
                                yield channel
                        except Exception:
                            pass
                except Exception:
                    pass

        async for messageable in _get_messageables():
            if messageable:
                emb: Embed = Embed()
                emb.description = "This bot will now go offline. I won't be able to maintain/update it since I'm gonna be busy next year (work). Thank you to everyone who [bought me a coffee](https://paypal.me/rendererbot?locale.x=en_US).\n\nIf you still want to render your replays, you can use: "
                emb.add_field(name="Trackbot", value="[Invite link](https://discord.com/oauth2/authorize?client_id=633110582865952799&scope=bot+applications.commands&permissions=412317248576)", inline=True)
                emb.add_field(name="Trackbot's Discord server", value="[Join link](https://discord.gg/dU39sjq)", inline=True)
                emb.add_field(name="Source code", value="[Github](https://github.com/imkindaprogrammermyself/renderer-bot-rq)")
                await messageable.send(embed=emb)
        LOGGER_BOT.info("Farewell done.")

    @commands.command("gift")
    @commands.check(
        lambda ctx: ctx.guild.id in [815060530368741377, 821309859835805697]
    )
    @command_logger(color=0x990099)
    async def _gift(self, ctx: Context, box_type: str, count: int):
        mapping = {
            "mega": BOX_MEGA,
            "big": BOX_BIG,
            "normal": BOX_NORM,
        }

        if box_type.lower() not in mapping:
            await ctx.send(embed=create_bot_message("Invalid box. Possible value (mega, big, normal)", MSG_ERROR))
            return

        if 1 > count > 100:
            await ctx.send(embed=create_bot_message("Invalid count. It should be within 1 and 100", MSG_ERROR))
            return

        with StringIO() as f:
            f.write('\n'.join(self.roll(mapping[box_type.lower()], count)))
            f.seek(0)
            await ctx.send(file=File(f, filename="result.txt"))

    @staticmethod
    def roll(box: list, count=1):
        rolled = []
        for _ in range(count):
            weights = [i['chance'] for i in box]
            result = random.choices(box, weights, k=1).pop()
            if result["type"] == "multi":
                weights_sub = [j['chance'] for j in result["value"]]
                result_sub = random.choices(result["value"], weights_sub, k=1).pop()

                if isinstance(result_sub["name"], list):
                    rolled.append(random.choice(result_sub["name"]))
                else:
                    rolled.append(result_sub["name"])
            else:
                rolled.append(result["value"])
        return rolled