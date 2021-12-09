from os import getenv

from discord import Embed
from discord.ext import commands
from discord.ext.commands import Bot, Context

from utils.helpers import check_environ_vars
from utils.logger import LOGGER_BOT, command_logger
from utils.strings import *
from .base import PermissionCheckerCog

check_environ_vars(LOGGER_BOT, "URL_PAYPAL", "BOT_COMMAND_PREFIX")

PREFIX = getenv("BOT_COMMAND_PREFIX")
URL_PAYPAL = getenv("URL_PAYPAL")


class Help(PermissionCheckerCog):
    def __init__(self, bot):
        self._bot: Bot = bot
        LOGGER_BOT.info(MSG_VDU671)

    @commands.group(name="help")
    @command_logger(color=0xFF99CC)
    async def help(self, ctx: Context):
        if ctx.invoked_subcommand:
            await ctx.message.delete()
            return
        try:
            try:
                await ctx.message.delete()
                embed = Embed(color=0x66FF33)
                embed.set_author(name=MSG_WWC273, icon_url=MSG_YSL748)
                embed.description = MSG_HFT616
                embed.add_field(name=MSG_FXJ230, value=MSG_FCQ421.format(*PREFIX * 2))
                embed.add_field(name=MSG_XOI463, value=MSG_VIJ262.format(*PREFIX * 2))
                embed.add_field(
                    name="Source code:",
                    value="[Github](https://github.com/imkindaprogrammermyself/renderer-bot-rq)",
                    inline=False,
                )
                embed.add_field(
                    name="\u200B", value=f"{MSG_GVT802}({URL_PAYPAL})", inline=False
                )
                await ctx.channel.send(embed=embed)
            except Exception:
                pass
        except Exception:
            pass

    @help.group("render")
    @command_logger(color=0xFF99CC)
    async def _render(self, ctx: Context):
        cmd = f"{PREFIX}render"
        embed = Embed(color=0x66FF33)
        embed.set_author(name=MSG_WWC273, icon_url=MSG_YSL748)
        embed.description = MSG_KUQ121
        embed.add_field(name=f"`{cmd}`", value="Normal render.", inline=False)
        embed.add_field(name=f"`{cmd} logs`", value=MSG_FVV166, inline=False)
        embed.add_field(name=f"`benny`", value=MSG_AOB487, inline=False)
        embed.add_field(name=f"`doom`", value=MSG_OTV870, inline=False)
        embed.add_field(
            name=f"Syntax",
            value=MSG_RKN680.format(*[f"{PREFIX}render"] * 6),
            inline=False,
        )
        embed.set_image(url=MSG_CCT908)
        await ctx.channel.send(embed=embed)

    @help.group("renderzip")
    @command_logger(color=0xFF99CC)
    async def _renderzip(self, ctx: Context):
        cmd = f"{PREFIX}renderzip"
        embed = Embed(color=0x66FF33)
        embed.set_author(name=MSG_WWC273, icon_url=MSG_YSL748)
        embed.description = MSG_PYD872
        embed.add_field(name=f"`{cmd}`", value=MSG_EOG769, inline=False)
        await ctx.channel.send(embed=embed)
