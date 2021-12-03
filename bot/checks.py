from discord import User
from discord.ext.commands import Context
from os import getenv
from utils.logger import LOGGER_BOT, EXIT
from utils.redisconn import ASYNC_REDIS

if SETTINGS_PREFIX := getenv("SETTINGS_PREFIX"):
    pass
else:
    LOGGER_BOT.error("SETTING_PREFIX variable not declared. Exiting...", extra=EXIT)


async def check_guild_can_extract(ctx: Context):
    user: User = ctx.author
    if user.dm_channel == ctx.channel:
        return True
    return await ASYNC_REDIS.sismember(
        f"guilds.chat_extract", ctx.guild.id
    )

async def check_is_authorized(ctx: Context):
    return await ASYNC_REDIS.sismember(
        f"{SETTINGS_PREFIX}.BOT_OWNERS", ctx.message.author.id
    )
