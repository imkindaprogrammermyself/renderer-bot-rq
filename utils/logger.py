import functools
import logging
from logging import StreamHandler, LogRecord
from typing import Union, Callable, Optional

from discord import User, TextChannel, DMChannel
from discord.ext.commands import Context
from utils.strings import *

EXIT = {"exit": True}


class ErrorHandler(StreamHandler):
    def __init__(self):
        super().__init__()

    def emit(self, record: LogRecord) -> None:
        try:
            if record.__getattribute__("exit"):
                record.msg = f"{record.msg} Exiting..."
                super().emit(record)
                exit(1)
        except AttributeError:
            pass
        super().emit(record)


logging.basicConfig(format='%(asctime)s | %(name)s | %(levelname)s | %(message)s', datefmt='%Y-%m-%d %H:%M:%S',
                    level=logging.INFO, handlers=[ErrorHandler()])

LOGGER = logging.getLogger('Renderer')
LOGGER_BOT = logging.getLogger('Bot')
LOGGER_WORKER = logging.getLogger('Worker')
LOGGER_REDIS = logging.getLogger('Redis')


def logger_extra(obj: Union[Context, TextChannel, DMChannel], user: Optional[User] = None, **kwargs):
    if isinstance(obj, Context):
        channel: TextChannel = obj.channel
        user: User = obj.author
    else:
        channel = obj
        assert user is not None

    if hasattr(channel, 'guild'):
        try:
            username = channel.guild.get_member(user.id).display_name
        except Exception:
            username = user.display_name
    else:
        username = user.display_name

    extra_data = {
        "guild_id": channel.guild.id if hasattr(channel, 'guild') else "DM channel",
        "guild_name": channel.guild.name if hasattr(channel, 'guild') else "DM channel",
        "channel_id": channel.id,
        "channel_name": channel.name if hasattr(channel, 'name') else "DM channel",
        "user_id": user.id,
        "user_name": username
    }

    extra_data.update(kwargs)
    return extra_data


def log_command(ctx: Context, logger: Callable, color: int = 0):
    author: User = ctx.author
    channel: Union[TextChannel, DMChannel] = ctx.channel
    extra_data = logger_extra(ctx, command=ctx.message.content, color=color)
    guild_message = f"DM Channel" if isinstance(channel, DMChannel) else MSG_OLI026.format(ctx.guild.name, ctx.guild.id,
                                                                                           ctx.channel.name,
                                                                                           ctx.channel.id)
    log_message = f"{guild_message} | USER: {author.display_name} | USER ID: {author.id} | CMD: {ctx.command}"

    if ctx.message.attachments:
        log_message = f"{log_message} | FILE: {ctx.message.attachments[0].filename}"
        extra_data.update({'file': ctx.message.attachments[0].filename})

    logger(log_message, extra=extra_data)


def command_logger(logger: Callable = LOGGER_BOT.info, color: int = 0):
    def decorator(func):
        @functools.wraps(func)
        async def wrapped(self, ctx: Context, *args, **kwargs):
            log_command(ctx, logger, color)
            return await func(self, ctx, *args, **kwargs)
        return wrapped
    return decorator


def log_command_render_extract(ctx: Context, logger: Callable, color: int = 0, status="Started"):
    author: User = ctx.author
    channel: Union[TextChannel, DMChannel] = ctx.channel
    extra = logger_extra(ctx, command=ctx.command, color=color, status=status)
    guild_message = f"DM Channel" if isinstance(channel, DMChannel) else MSG_OLI026.format(ctx.guild.name, ctx.guild.id,
                                                                                           ctx.channel.name,
                                                                                           ctx.channel.id)
    log_message = f"{guild_message} | USER: {author.display_name} | USER ID: {author.id} | CMD: {ctx.command}"
    log_message = f"{log_message} | STATUS: {status}"

    if ctx.message.attachments:
        log_message = f"{log_message} | FILE: {ctx.message.attachments[0].filename}"
        extra.update({'file': ctx.message.attachments[0].filename})

    logger(log_message, extra=extra)


def command_logger_render_extract(colors: tuple[int], logger: Callable = LOGGER_BOT.info):
    color_a, color_b = colors

    def decorator(func):
        @functools.wraps(func)
        async def wrapped(self, ctx: Context, *args, **kwargs):
            log_command_render_extract(ctx, logger, color_a)
            result = await func(self, ctx, *args, **kwargs)
            result = result if result else "Done."
            log_command_render_extract(
                ctx, logger, color_b, status=result)
        return wrapped
    return decorator
