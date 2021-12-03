import json
import os

from discord import Embed, Message, TextChannel, User
from discord.ext.commands import Bot, Cog, Context
from discord.guild import Guild
from discord.permissions import Permissions
from rq.job import Job
from utils.logger import LOGGER_BOT, logger_extra
from utils.redisconn import ASYNC_REDIS
from utils.settings import retrieve_from_env
from utils.strings import MSG_SPS820, MSG_ZLD216


def track_task_request(f):
    async def wrapped(self, ctx: Context, *args, **kwargs):
        await ASYNC_REDIS.set(f"task_request_{ctx.author.id}", "", ex=180)
        try:
            return await f(self, ctx, *args, **kwargs)
        except Exception as e:
            LOGGER_BOT(e, exc_info=e)
        finally:
            await ASYNC_REDIS.delete(f"task_request_{ctx.author.id}")

    return wrapped


class PermissionCheckerCog(Cog):
    async def cog_before_invoke(self, ctx: Context):
        bot: Bot = ctx.bot
        guild: Guild = ctx.guild
        channel: TextChannel = ctx.channel
        permissions = json.loads(os.getenv("BOT_REQUIRED_PERM"))
        permission_obj: Permissions = channel.permissions_for(
            guild.get_member(bot.user.id)
        )
        resolved_perms = {
            " ".join(p.split("_")).capitalize(): getattr(permission_obj, p)
            for p in permissions
        }

        if not all(resolved_perms.values()):
            lines = [MSG_SPS820, "```"]

            for perm_name, have_perm in resolved_perms.items():
                spaced_perm_name = f"{perm_name}{' ' * (len(max(permissions, key=len)) - len(perm_name))}"
                lines.append(f"{spaced_perm_name}{' : '}{'✔️' if have_perm else '❌'}")

            lines.append("```")
            lines.append(MSG_ZLD216)
            joined_lines = "\n".join(lines)

            try:
                await ctx.send(joined_lines)
            except Exception as e:
                pass
            LOGGER_BOT.error(
                f"Command `{ctx.command}` invoked on a channel missing required the permissions.",
                extra=logger_extra(ctx),
            )
            raise PermissionError


class TaskCog(PermissionCheckerCog):
    def __init__(self, bot: Bot) -> None:
        super().__init__()
        self._bot: Bot = bot
        self._pbar_fg = retrieve_from_env("RENDER_PBAR_F", str)
        self._pbar_bg = retrieve_from_env("RENDER_PBAR_B", str)
        self._task_queue_size = retrieve_from_env("TASK_QUEUE_SIZE", int)
        self._cooldown = retrieve_from_env("TASK_COOLDOWN", int)
        self._queue_max_wait_time = retrieve_from_env("QUEUE_MAX_WAIT_TIME", int)
        self._paypal_url = retrieve_from_env("URL_PAYPAL", str, allow_none=True)
        self._required_perm = json.loads(retrieve_from_env("BOT_REQUIRED_PERM", str))

    def _get_embed(self, ctx: Context, color: int, **kwargs) -> Embed:
        username = self._username_to_use(ctx)
        filename = ctx.message.attachments[0].filename
        embed = Embed(color=color)
        embed.set_author(name=self._bot.user.name, icon_url=self._bot.user.avatar_url)
        embed.add_field(name="Replay file:", value=filename, inline=False)
        embed.add_field(name="Username:", value=username, inline=True)

        if status := kwargs.pop("status", None):
            embed.add_field(name="Status:", value=status, inline=True)

        if position := kwargs.pop("position", None):
            embed.add_field(name="Position:", value=position, inline=True)

        if per := kwargs.pop("per", None):
            embed.add_field(
                name="Progress:",
                value=f"{self._pbar_fg * per}{self._pbar_bg * (10 - per)}",
                inline=True,
            )

        if result := kwargs.pop("result", None):
            result = (
                result
                if any([1 for s in ["File link:", "Message link:"] if s in result])
                else result
            )
            embed.add_field(name="Result:", value=result, inline=True)

        if time_taken := kwargs.pop("time_taken", None):
            embed.add_field(name="Time taken:", value=time_taken, inline=True)

        if command := ctx.command:
            embed.add_field(
                name="Command:", value=f"{self._bot.command_prefix}{command}"
            )

        if self._paypal_url:
            embed.add_field(
                name="\u200B",
                value=f"☕ [Buy me a coffee]({self._paypal_url})",
                inline=False,
            )
        return embed

    @staticmethod
    def _get_job_position(job: Job):
        _pos = job.get_position()
        return _pos + 1 if _pos else 1

    @staticmethod
    async def _try_delete_message(message: Message):
        channel: TextChannel = message.channel

        try:
            if channel.type == "private":
                pass
            else:
                await message.delete()
        except Exception:
            pass

    @staticmethod
    def _delete_temp_files(*files):
        try:
            for file in files:
                if os.path.exists(file):
                    os.remove(file)
        except Exception:
            pass

    @staticmethod
    def _username_to_use(ctx: Context):
        ch: TextChannel = ctx.channel
        user: User = ctx.author

        if hasattr(ch, "guild"):
            try:
                return ch.guild.get_member(user.id).display_name
            except Exception:
                return user.display_name
        else:
            return user.display_name
