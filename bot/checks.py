from discord import User
from discord.ext.commands import Context
from os import getenv
from utils.logger import LOGGER_BOT, EXIT
from utils.redisconn import ASYNC_REDIS

if SETTINGS_PREFIX := getenv("SETTINGS_PREFIX"):
    pass
else:
    LOGGER_BOT.error(
        "SETTING_PREFIX variable not declared. Exiting...", extra=EXIT)


async def check_is_render_channel(ctx: Context):
    user: User = ctx.author
    if user.dm_channel == ctx.channel:
        return True
    return await ASYNC_REDIS.sismember(f"guild.{ctx.guild.id}.render-channels", ctx.channel.id)


async def check_is_extract_channel(ctx: Context):
    user: User = ctx.author
    if user.dm_channel == ctx.channel:
        return True
    return await ASYNC_REDIS.sismember(f"guild.{ctx.guild.id}.extract-channels", ctx.channel.id)


async def check_is_valid_channel(ctx: Context):
    user: User = ctx.author
    if user.dm_channel == ctx.channel:
        return True

    is_extract_ch = await ASYNC_REDIS.sismember(f"guild.{ctx.guild.id}.extract-channels", ctx.channel.id)
    is_render_ch = await ASYNC_REDIS.sismember(f"guild.{ctx.guild.id}.render-channels", ctx.channel.id)
    return is_extract_ch or is_render_ch


async def check_is_authorized(ctx: Context):
    return await ASYNC_REDIS.sismember(f"{SETTINGS_PREFIX}.BOT_OWNERS", ctx.message.author.id)


# def bot_has_permission(f):
#     async def wrapped(self, ctx: Context, *args, **kwargs):
#         bot: Bot = ctx.bot
#         guild: Guild = ctx.guild
#         channel: TextChannel = ctx.channel
#         permissions = json.loads(getenv('BOT_REQUIRED_PERM'))
#         permission_obj: Permissions = channel.permissions_for(
#             guild.get_member(bot.user.id))
#         resolved_perms = {' '.join(p.split('_')).capitalize(): getattr(
#             permission_obj, p) for p in permissions}

#         if not all(resolved_perms.values()):
#             lines = [MSG_SPS820, "```"]

#             for perm_name, have_perm in resolved_perms.items():
#                 spaced_perm_name = f"{perm_name}{' ' * (len(max(permissions, key=len)) - len(perm_name))}"
#                 lines.append(
#                     f"{spaced_perm_name}{' : '}{'✔️' if have_perm else '❌'}")

#             lines.append('```')
#             lines.append(MSG_ZLD216)
#             joined_lines = '\n'.join(lines)

#             try:
#                 await ctx.send(joined_lines)
#             except Exception as e:
#                 pass
#             LOGGER_BOT.error(
#                 f"Command `{ctx.command}` invoked on a channel missing required the permissions.", extra=logger_extra(ctx))
#             raise PermissionError
#         else:
#             try:
#                 return await f(self, ctx, *args, **kwargs)
#             except Exception as e:
#                 LOGGER_BOT(e, exc_info=e)
#     return wrapped
