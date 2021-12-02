from discord import Embed

MSG_OK = 3329330
MSG_WARN = 16753920
MSG_ERROR = 16711680


def create_bot_message(msg: str, color) -> Embed:
    embed = Embed(color=color)
    embed.set_author(name="Minimap Renderer", icon_url="https://i.imgur.com/BG4BFuQ.png")
    embed.description = msg
    return embed
