import random
import string

MSG_QFA769 = "Queue full. Please try again later."
MSG_IIZ122 = " You're in cooldown for"
MSG_FNB379 = "You have an ongoing/queued render. Please try again later."
MSG_QYM865 = "No replay file attached."
MSG_LKN365 = "Rendered file too large (Discord 8MB limit)\n Try running it again without `logs`"
MSG_DQP186 = "No running workers detected."
MSG_IBK358 = "An error occurred."
MSG_OIJ303 = "**Minimap Renderer**"
MSG_YSL748 = "https://i.imgur.com/BG4BFuQ.png"
MSG_CBQ274 = "RenderSingle cog ready."
MSG_WPJ675 = "RenderDual cog ready."
MSG_BNC214 = "ReplayRenderDual cog ready."
MSG_HPW280 = "ReplayMatchStats cog ready."
MSG_VDU671 = "Help cog ready."
MSG_CLP091 = "You cannot use this command in a DM channel."
MSG_ZLI953 = "Command done."
MSG_PMC310 = "Invalid or missing value."
MSG_XVK877 = "Value should be <= 500."
MSG_OTK071 = "An error occurred. Check the logs for more information about the error."
MSG_WVL344 = "You are not allowed to do that."
MSG_DRF838 = "Command not found."
MSG_GDX897 = "Missing argument."
MSG_WRS830 = "Bot has joined a banned `{0}` server. Leaving immediately."
MSG_QVY349 = "Bot has joined `{0}` server."
MSG_VZV482 = "Bot has left `{0}` server."
MSG_BYY733 = "The bot already renders here."
MSG_SRW302 = "The bot doesn't render here."
MSG_OTZ736 = "The bot will now render here."
MSG_CWD754 = "The bot will not render here anymore."
MSG_JTY381 = "You still have a pending request."
MSG_ZAN763 = "Request cooldown."
MSG_APU416 = "Request sent."
MSG_RFV747 = "Request for `channel id: {0}` doesn't exists."
MSG_JDL519 = "Incomplete command."
MSG_RMX275 = "Request accepted."
MSG_TZK510 = "Request rejected."
MSG_DSY351 = "Request banned. The bot will now leave. Any subsequent invites will result to auto leave."
MSG_RAR548 = "Wrong or missing subcommand."
MSG_VNJ492 = "Value is not in range. `min: {0}, max: {1}`."
MSG_KND322 = "Value is not a number."
MSG_RLV149 = "`{0}` is set to `{1}`"
MSG_SOR600 = "You can only get {0} settings."
MSG_DSQ832 = "`{0}` value is `{1}`"
MSG_JDU141 = "GUILD NAME: {0} | GUILD ID: {1} | CHANNEL NAME: {2} | CHANNEL ID: {3}\n"
MSG_QHZ393 = "Channel {0} removed."
MSG_GHN894 = "Channel {0} was not removed."
MSG_DIR263 = "Channel {0} was not found."
MSG_ESG543 = "GUILD NAME: {0} | GUILD ID: {1}"
MSG_YDV932 = "GUILD {0} not found."
MSG_CEO189 = "Banned and left {0} server."
MSG_VKI313 = "Invalid guild id."
MSG_PHL602 = "Unbanned guild with id `{0}`."
MSG_FAF070 = "Guild id `{0}` isn't in the banned list."
MSG_AUR237 = "No backup file attached."
MSG_SPS820 = "One or more required permission(s) is/are not granted to the bot in this channel."
MSG_ZLD216 = "Grant the bot with the missing permission(s) and try again."
MSG_GOW660 = "Restore completed."
MSG_FTI238 = "Time limit exceeded."
MSG_LAV349 = "File link: [{0}]({1})\nMessage link: [Message]({2})"
MSG_ASI986 = "Rendering complete."
MSG_WWC273 = "Minimap Renderer"
MSG_HFT616 = "I can create a video of your minimap from a replay file.\n0.10.9 - 0.10.10 replays only."
MSG_FXJ230 = "**Available Commands:**"
MSG_FCQ421 = "`{}render`\n`{}renderzip`"
MSG_XOI463 = "**Help subcommands:**"
MSG_VIJ262 = "`{}help render`\n`{}help renderzip`"
MSG_GVT802 = "☕ [Buy me a coffee]"
MSG_KUQ121 = "This command will render the minimap from your replay file."
MSG_FVV166 = "Includes damage dealt, ribbons, achievements and frags."
MSG_AOB487 = "Adds Benny Hill theme and makes the renders twice as fast."
MSG_RKN680 = ">>> `{}`\n`{} logs`\n`{} benny`\n`{} logs benny`\n`{} doom`\n`{} logs doom`"
MSG_CCT908 = "https://i.imgur.com/pOVEMIA.gif"
MSG_PYD872 = "This command will render two replay files inside a zip file.\n" \
             "The replay files must start with `a-A` or `b-B`.\n" \
             "Ex. `aTeamA.wowsreplay, bTeamB.wowsreplay`\n\n" \
             "__**This command works better if/with:**__\n\n" \
             "> The player died early and spectated the battle until the end.\n" \
             "> A BB player that is mostly in the middle.\n" \
             "> A CV player.\n\n" \
             "Both players must spectate the battle until the end. Failing to do so will make rendered video " \
             "duration the same as the shortest battle replay file."
MSG_EOG769 = "Renders both replay files inside a zip file."
MSG_OTV870 = "??? (player must have a kill)"
MSG_ANM988 = "Unsupported version.\n0.10.9 - 0.10.10 replays only."
MSG_KOL445 = "Unsupported battle type."
MSG_JYQ473 = "Reading error."
MSG_HIY955 = "Rendering error."
MSG_LGD750 = "Time limit exceeded."
MSG_TOG346 = "Arena ID mismatch. Replays are not from the same battle."
MSG_ATK550 = "Multiple replay files found."
MSG_MDF285 = "Not enough replay files."
MSG_TAW064 = "Please contact the bot owner first to whitelist your server.\n" \
             "I am now leaving.\nhttps://c.tenor.com/m-2XXQuq-OwAAAAd/peace-out.gif"
MSG_SLJ122 = "You or someone in your server which at least have `Manager server` permission has invited me to your " \
             "`{0}` server. Please contact the bot owner first to whitelist your server then invite me again."
MSG_MBO040 = "The bot already extracts here."
MSG_IBJ760 = "The bot will now extract chat messages here."
MSG_SBJ866 = "The bot doesn't extract chat messages here."
MSG_OXK728 = "The bot will not extract chat messages here anymore."
MSG_ZPI560 = "This server is banned from using this bot. The bot will now leave."
MSG_TRN372 = "Your server, {0}, is banned from using this bot. The not will now leave."
MSG_UWL774 = "ExtractChat cog ready."
MSG_JMP230 = "No json file attached."
MSG_RHH207 = "Permission error. Please make sure the bot has these permissions in this channel.\n`{0}`"
MSG_OLI026 = "GUILD: {0} | GUILD ID: {1} | CHANNEL: {2} | CHANNEL ID: {3}"
MSG_ADS530 = "This server has been added to the chat extract list. Users will be able to use `{0}chat` command in this server."

def _random_str():
    a = ''.join([random.choice(string.ascii_uppercase) for _ in range(3)])
    b = ''.join([random.choice(string.digits) for _ in range(3)])
    return f"MSG_{a}{b}"


if __name__ == '__main__':
    indexes = set()
    back = locals().copy()
    indexes.update(k for k in back if 'MSG_' in k)

    print(indexes)

    while True:
        inp = input("Press enter to generate index, q to quit: ")
        if inp.lower() == "q":
            break
        else:
            while True:
                _result = _random_str()
                if _result not in indexes:
                    indexes.add(_result)
                    print(_result)
                    break
