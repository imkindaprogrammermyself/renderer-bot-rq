import asyncio
import json
import traceback
from logging import StreamHandler, LogRecord
from os import getenv

import discord
from discord import TextChannel
from discord.ext.commands import AutoShardedBot
from discord.ext.commands.bot import Bot
from discord.guild import Guild
from discord.permissions import Permissions

from utils.helpers import check_environ_vars
from utils.logger import LOGGER_BOT, LOGGER_REDIS, LOGGER, logger_extra
from utils.strings import MSG_SPS820, MSG_ZLD216
from .cogs.cog_administrative import Administrative
from .cogs.cog_render_single import RenderSingle
from .cogs.cog_render_dual import RenderDual
from .cogs.cog_extract_chat import ExtractChat
from .cogs.cog_help import Help

check_environ_vars(LOGGER_BOT, 'BOT_TOKEN', 'BOT_COMMAND_PREFIX')

intents = discord.Intents.default()
intents.members = True

BOT = AutoShardedBot(command_prefix=getenv('BOT_COMMAND_PREFIX'), help_command=None, intents=intents)


class DiscordLogger(StreamHandler):
    def __init__(self, logging_channel: TextChannel):
        self._loop = asyncio.get_event_loop()
        self._logging_channel: TextChannel = logging_channel
        self._level_colors = {
            "INFO": 0x32CD32,
            "WARN": 0xFFA500,
            "WARNING": 0xFFA500,
            "ERROR": 0xFF0000,
            "EXCEPTION": 0xFF0000,
            "DEBUG": 0x808080
        }
        self._extras = ['guild_id', 'guild_name', 'channel_id', 'channel_name', 'user_id', 'user_name', 'command',
                        'file', 'status', 'desc']
        super().__init__()

    async def send_log(self, record: LogRecord):
        if color := getattr(record, "color", None):
            embed_color = color
        else:
            embed_color = self._level_colors[record.levelname]

        embed = discord.Embed(color=embed_color)
        embed.set_author(name="Logger", icon_url='https://i.imgur.com/00fEmeR.png')
        embed.add_field(name="Name", value=record.name)
        embed.add_field(name="Level", value=record.levelname)
        embed.add_field(name='System time', value=record.asctime)

        if exc_info := record.exc_info:
            if msg := record.msg:
                embed.add_field(name="Message", value=f"```\n{msg}```", inline=False)

            e_type, exception, tb = exc_info
            tracebacks = traceback.format_exception(e_type, exception, tb)[-4:]
            embed.add_field(name="Traceback", value=f"```\n{''.join(tracebacks)}```", inline=False)
        else:
            if msg := record.msg:
                embed.description = f"```\n{msg}```"

        if any([hasattr(record, i) for i in self._extras]):
            for extra in self._extras:
                if data := getattr(record, extra, None):
                    if extra != 'desc':
                        embed.add_field(name=' '.join(extra.split('_')).capitalize(), value=f"{data}")
                    else:
                        embed.description = data
        else:
            if msg := record.msg:
                embed.description = f"```\n{msg}```"
        
        await self._logging_channel.send(embed=embed)

    def emit(self, record: LogRecord) -> None:
        self._loop.create_task(self.send_log(record))


def subscribe_to_logger():
    try:
        if logging_channel := BOT.get_channel(int(getenv('BOT_LOGS_CHANNEL'))):
            for logger in [LOGGER_BOT, LOGGER_REDIS, LOGGER]:
                logger.addHandler(DiscordLogger(logging_channel))
    except Exception:
        LOGGER_BOT.error("Error on subscribing to logger(s).")


@BOT.event
async def on_ready():
    LOGGER_BOT.info(f"Logged in as: {BOT.user.name}")
    LOGGER_BOT.info(f"Loading cogs...")

    for cog in [Administrative, RenderSingle, RenderDual, ExtractChat, Help]:
        try:
            BOT.add_cog(cog(BOT))
        except Exception as e:
            LOGGER_BOT.exception(e)

    LOGGER_BOT.info(f"Cogs loaded.")
    LOGGER_BOT.info(f"Bot ready.")
    subscribe_to_logger()

@BOT.before_invoke
async def before_invoke(ctx):
    bot: Bot = ctx.bot
    guild: Guild = ctx.guild
    channel: TextChannel = ctx.channel
    permissions = json.loads(getenv('BOT_REQUIRED_PERM'))
    permission_obj: Permissions = channel.permissions_for(
        guild.get_member(bot.user.id))
    resolved_perms = {' '.join(p.split('_')).capitalize(): getattr(
        permission_obj, p) for p in permissions}

    if not all(resolved_perms.values()):
        lines = [MSG_SPS820, "```"]

        for perm_name, have_perm in resolved_perms.items():
            spaced_perm_name = f"{perm_name}{' ' * (len(max(permissions, key=len)) - len(perm_name))}"
            lines.append(
                f"{spaced_perm_name}{' : '}{'✔️' if have_perm else '❌'}")

        lines.append('```')
        lines.append(MSG_ZLD216)
        joined_lines = '\n'.join(lines)

        try:
            await ctx.send(joined_lines)
        except Exception as e:
            pass
        LOGGER_BOT.error(
            f"Command `{ctx.command}` invoked on a channel missing required the permissions.", extra=logger_extra(ctx))
        raise PermissionError


def run_bot():
    token = getenv('BOT_TOKEN')
    LOGGER_BOT.info(f"Running the bot with token: {'.' * 4}{token[-4:]}")
    BOT.run(token)
