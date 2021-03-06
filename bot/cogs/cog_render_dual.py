import asyncio
from io import BytesIO

import discord
from discord import TextChannel, Message, File, Attachment
from discord.errors import Forbidden
from discord.ext import commands
from discord.ext.commands import Context

from utils.constants import (
    GREEN,
    YELLOW,
    ORANGE,
    RED,
    COLOR_DUAL_STARTED,
    COLOR_DUAL_ENDED,
)
from utils.exception import (
    RenderingError,
    ReadingError,
    VersionNotFoundError,
    UnsupportedBattleTypeError,
    ArenaIdMismatchError,
    MultipleReplaysError,
    NotEnoughReplaysError,
)
from utils.logger import LOGGER_BOT, logger_extra, command_logger_render_extract
from utils.redisconn import REDIS
from utils.strings import *
from tasks.task_render_dual import task_render_dual
from rq import Queue
from rq.job import Job
from .base import TaskCog, track_task_request

QUEUE = Queue(name="dual", connection=REDIS)

class RenderDual(TaskCog):
    def __init__(self, bot):
        super().__init__(bot)
        LOGGER_BOT.info(MSG_BNC214)

    @commands.command(name="renderzip")
    async def render(self, ctx: Context):
        if ctx.invoked_subcommand:
            return
        await self._worker(ctx)

    async def _worker(self, ctx: Context):
        message: Message = ctx.message

        if not await self._checks(ctx, QUEUE):
            return

        job_ttl = max(QUEUE.count, 1) * self._queue_max_wait_time
        attachment: Attachment = message.attachments[0]

        with BytesIO() as buf:
            await attachment.save(buf)
            buf.seek(0)
            job: Job = QUEUE.enqueue(
                task_render_dual,
                args=(buf.read(), ctx.author.id),
                failure_ttl=180,
                result_ttl=180,
                ttl=job_ttl,
            )

        self._bot.loop.create_task(self._poll_result(ctx, job))
        await self._try_delete_message(message)

    @command_logger_render_extract((COLOR_DUAL_STARTED, COLOR_DUAL_ENDED))
    @track_task_request
    async def _poll_result(self, ctx: Context, job: Job):
        ch: TextChannel = ctx.channel
        position = self._get_job_position(job)
        embed = self._get_embed(ctx, ORANGE, status="Queued", position=position)
        message: Message = await ch.send(embed=embed)
        status = "Failed"

        try:
            while True:
                position = self._get_job_position(job)
                status = job.get_status(refresh=True)
                if status == "queued":
                    embed = self._get_embed(ctx, ORANGE, status="Queued", position=position)
                    await message.edit(embed=embed)
                elif status == "started":
                    try:
                        if progress := job.get_meta(refresh=True).get("progress", None):
                            progress = round(progress * 10)
                            embed = self._get_embed(
                                ctx, YELLOW, status="Rendering", per=progress
                            )
                        elif task_status := job.get_meta(refresh=True).get("status", None):
                            embed = self._get_embed(ctx, YELLOW, status=task_status)
                        else:
                            embed = self._get_embed(ctx, YELLOW, status="Running")
                    except Exception as e:
                        LOGGER_BOT.error(e, exc_info=e)
                    await message.edit(embed=embed)
                elif status == "finished":
                    if isinstance(job.result, Exception):
                        if isinstance(job.result, VersionNotFoundError):
                            err_message = MSG_ANM988
                        elif isinstance(job.result, UnsupportedBattleTypeError):
                            err_message = MSG_KOL445
                        elif isinstance(job.result, ReadingError):
                            err_message = MSG_JYQ473
                        elif isinstance(job.result, RenderingError):
                            err_message = MSG_HIY955
                        elif isinstance(job.result, ArenaIdMismatchError):
                            err_message = MSG_TOG346
                        elif isinstance(job.result, MultipleReplaysError):
                            err_message = MSG_ATK550
                        elif isinstance(job.result, NotEnoughReplaysError):
                            err_message = MSG_MDF285
                        elif isinstance(job.result, FileNotFoundError):
                            err_message = str(job.result)
                        else:
                            err_message = MSG_IBK358
                        embed = self._get_embed(
                            ctx, RED, status="Error", result=err_message
                        )
                        LOGGER_BOT.error(job.result, exc_info=job.result)
                    elif isinstance(job.result, tuple):
                        video_data, random_str, time_taken = job.result
                        try:
                            with BytesIO(video_data) as reader:
                                file = File(reader, f"{random_str}.mp4")
                            video_msg: Message = await ch.send(file=file, reference=message)
                            attached_file: Attachment = video_msg.attachments[0]
                            result_msg = MSG_LAV349.format(
                                attached_file.filename,
                                attached_file.url,
                                video_msg.jump_url,
                            )
                            embed = self._get_embed(
                                ctx,
                                GREEN,
                                status="Completed",
                                result=result_msg,
                                time_taken=time_taken,
                            )
                            status = "Completed"
                        except discord.InvalidArgument as e:
                            embed = self._get_embed(
                                ctx, RED, status="Error", result=MSG_LKN365
                            )
                            LOGGER_BOT.error(e, exc_info=e, extra=logger_extra(ctx))
                        except Forbidden as e:
                            formatted_names = ", ".join(
                                [
                                    " ".join(perm.split("_")).capitalize()
                                    for perm in self._required_perm
                                ]
                            )
                            embed = self._get_embed(
                                ctx,
                                RED,
                                status="Error",
                                result=MSG_RHH207.format(formatted_names),
                            )
                            LOGGER_BOT.error(e, exc_info=e, extra=logger_extra(ctx))
                    await message.edit(embed=embed)
                    break
                elif status == "failed":
                    embed = self._get_embed(ctx, RED, status="Failed")
                    await message.edit(embed=embed)
                    break
                elif not status:
                    embed = self._get_embed(ctx, RED, status="Max queue time reached.")
                    await message.edit(embed=embed)
                    break
                await asyncio.sleep(1)
        except Exception as e:
            LOGGER_BOT.error(e, exc_info=e)

        job.delete()
        return status
