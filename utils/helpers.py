from os import getenv
from logging import RootLogger
from discord import TextChannel, User
from discord.ext.commands import Context

from utils.logger import EXIT


def check_environ_vars(logger: RootLogger, *args, exit_on_err=True):
    env_key_values = {v: getenv(v) for v in args}

    if not all(env_key_values.values()):
        msg = f"Missing {', '.join([i for i in env_key_values if not env_key_values[i]])} environment variable(s)."
        if exit_on_err:
            logger.error(msg, extra=EXIT)
        else:
            logger.error(msg)


def username_to_use(ctx: Context):
    ch: TextChannel = ctx.channel
    user: User = ctx.author

    if hasattr(ch, 'guild'):
        try:
            return ch.guild.get_member(user.id).display_name
        except Exception:
            return user.display_name
    else:
        return user.display_name
