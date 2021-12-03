import asyncio
import json
from os import getenv
from io import BytesIO

import discord
from discord import TextChannel, Message, File, Attachment, Embed, Guild, Permissions
from discord.errors import Forbidden
from discord.ext import commands
from discord.ext.commands import Context, Bot

from utils.constants import GREEN, YELLOW, ORANGE, RED, COLOR_STARTED, COLOR_ENDED
from utils.exception import (
    RenderingError,
    ReadingError,
    VersionNotFoundError,
    UnsupportedBattleTypeError,
)
from utils.logger import LOGGER_BOT, logger_extra, command_logger_render_extract
from utils.redisconn import ASYNC_REDIS, REDIS
from utils.strings import *
from tasks.task_render_single import task_render_single
from rq import Queue
from rq.job import Job
from rq.worker import Worker
from .base import TaskCog, track_task_request


queue = Queue(connection=REDIS)
workers = Worker([queue], connection=REDIS)


class RenderSingle(TaskCog):
    def __init__(self, bot):
        super().__init__(bot)
        LOGGER_BOT.info(MSG_CBQ274)

    @commands.group(name="render")
    async def render(self, ctx: Context):
        if ctx.invoked_subcommand:
            return
        await self._worker(ctx, False)

    @render.group()
    async def logs(self, ctx: Context):
        if ctx.invoked_subcommand:
            return
        await self._worker(ctx, True)

    @render.group(name="benny")
    async def _render_benny(self, ctx: Context):
        await self._worker(ctx, False, benny=True)

    @logs.group(name="benny")
    async def _logs_benny(self, ctx: Context):
        await self._worker(ctx, True, benny=True)

    @render.group(name="doom")
    async def _render_doom(self, ctx: Context):
        await self._worker(ctx, False, doom=True)

    @logs.group(name="doom")
    async def _logs_doom(self, ctx: Context):
        await self._worker(ctx, True, doom=True)

    async def _worker(self, ctx: Context, logs=False, benny=False, doom=False):
        worker_count = Worker.count(connection=REDIS, queue=queue)
        job_ttl = max(queue.count, 1) * self._queue_max_wait_time
        message: Message = ctx.message
        cooldown = await ASYNC_REDIS.ttl(f"cooldown_{ctx.author.id}")
        ebd = Embed(title=MSG_OIJ303, color=0xFF751A)
        ebd.set_thumbnail(url=MSG_YSL748)

        try:
            assert worker_count != 0, f"{message.author.mention} {MSG_DQP186}"
            assert (
                queue.count <= self._task_queue_size
            ), f"{message.author.mention} {MSG_QFA769}"
            assert cooldown <= 0, f"{message.author.mention} {MSG_IIZ122} {cooldown}s"
            assert not await ASYNC_REDIS.exists(
                f"task_request_{ctx.author.id}"
            ), f"{message.author.mention} {MSG_FNB379}"
            assert message.attachments, f"{message.author.mention} {MSG_QYM865}"
        except AssertionError as e:
            ebd.description = str(e)
            await ctx.channel.send(embed=ebd, delete_after=5)
            await self._try_delete_message(message)
            return

        attachment: Attachment = message.attachments[0]

        with BytesIO() as buf:
            await attachment.save(buf)
            buf.seek(0)
            job: Job = queue.enqueue(
                task_render_single,
                args=(buf.read(), ctx.author.id, logs, benny, doom),
                failure_ttl=180,
                result_ttl=180,
                ttl=job_ttl,
            )

        self._bot.loop.create_task(self._poll_result(ctx, job))
        await self._try_delete_message(message)

    @command_logger_render_extract((COLOR_STARTED, COLOR_ENDED))
    @track_task_request
    async def _poll_result(self, ctx: Context, job: Job):
        ch: TextChannel = ctx.channel
        position = self._get_job_position(job)
        embed = self._get_embed(ctx, ORANGE, status="Queued", position=position)
        message: Message = await ch.send(embed=embed)
        status = "Failed"

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
                            ctx, YELLOW, status="Rending", per=progress
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

        job.delete()
        return status
