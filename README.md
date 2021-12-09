# MINIMAP RENDERER BOT
A Discord bot that generates a video from a World of Warships replay file.
## Getting started
Clone this repo.
`git clone https://github.com/imkindaprogrammermyself/renderer-bot-rq.git`  

Create a virtual environment via Python's venv module and activate it. (This assumes you have Python 3.9 installed and on Linux)
>$cd renderer-bot-rq
>$python3.9 -m venv venv
>$. venv/bin/activate
>$pip install -r requirements.txt

Install `redis-server`.
You can install redis by following the instruction [here](https://redis.io/topics/quickstart) or via `apt`.

If you're planning to run the `bot`, `worker` and `redis-server ` separately, modify the following values inside `/etc/redis/redis.conf`

Comment out the line with `bind 127.0.0.1 ::1`.
Uncomment the line with `# requirepass foobared` and change `foobared` to something secure to set the password.
Restart the `redis-server`.


## SETTING UP .ENV VALUES
First, you need to create a `.env` file. Start by,
>$cp .env-template .env

Modify the values.

 - `ENVIRONMENT` set's which redis url to use.
 - `SETTINGS_PREFIX` redis key prefix to use. `FOOBAR.FPS,
   FOOBAR.QUALITY`
 - `REDIS_TESTING_URL` local redis server url for testing.
 - `REDIS_PRODUCTION_URL` remote or local redis server url depending on your setup.

		Ex. `redis://:yourredispassword@ip-172-0-0-1.us-east-2.compute.internal:6379`

 - `BOT_COMMAND_PREFIX` The bot's command prefix ie. `$`, `!` or any character you want. It's completely up to you but check for prefixes other bot uses in your server to avoid collision with the other bots.

 - `BOT_TOKEN` Your bot's token. Get one from discord.com/developers/applications
 - `BOT_LOGS_CHANNEL` Discord channel ID where the bot will write its logs.
 - `BOT_OWNERS` Bot's owner(s) ID(s). Your Discord ID or and someone's. Valid value (JSON array): `[623183509066088450, 623183509066088423]`
 - `BOT_REQUIRED_PERM` Bot's required permission to function properly. A JSON array.
 - `BOT_SERVER_WHITELIST` Bot's initial whitelist value. A JSON array `[INSERT_YOUR_DISCORD_SERVER_ID_HERE]`
 - `FPS` the render's fps.
 - `QUALITY` the render's quality.
 - `QUEUE_MAX_WAIT_TIME` Queue wait time before the job is deleted.
 - `TASK_COOLDOWN` Seconds before a user can use the bot's render commands again.
 - `TASK_QUEUE_SIZE` Sets the size of the queue. Once the queue size is reached the bot wont take another render request.
 - `RENDER_PBAR_F` Progress bar foreground character.
 - `RENDER_PBAR_B` Progress bar background character.
 - `URL_PAYPAL` Donation URL. Can be Patreon, GoFundMe, etc. Omitting the values will remove the `Buy me a coffee` from the bot's embed messages.
 - `BACKUP_KEY` Backup encrypt key. Strictly must be a 32 characters long.

## RUNNING THE BOT OR THE WORKER
This assumes you activated the Python environment you just created.

 Running the bot.
 >python main.py -r bot

Running a worker
>python main.py -r worker -q single dual chat

main.py arguments:

 - `-r`: specifies if you want to run the bot or the worker.
 - `-q`: specifies which queue(s) your worker to get its job from.
  
	  Possible `-q` values:
	`single` - A queue for `render` command.
	`dual` - A queue for `renderzip`command.
	`chat` - A queue for `chat` command.

  ## UPDATING THE BOT
  Extract the following files from the client using the [World of Warships Unpack Tool](https://forum.worldofwarships.eu/topic/113847-all-wows-unpack-tool-unpack-game-client-resources/)
  ![enter image description here](https://i.imgur.com/Zvo1O6dl.png)
 
The extracted files will be in `World_of_Warships/res_unpack` folder.

Move the following files:
`World_of_Warships/res_unpack/content/GameParams.data` and `World_of_Warships/res_unpack/gui/achievements`
 to `generation/resources`.
### Updating the renderer

 1. Run the scripts with `generated_` at their filenames from
    `generation` folder. This will create the update files.
 2. Copy the renderer version module and paste it into a newest version.
    `cp -r renderer/versions/0_10_10/ renderer/versions/0_10_11`.
 3. Paste the contents of `generation/generated` to
    `renderer/versions/0_10_11/resources` folder.

### Updating the unpacker
Most of the time this works just fine unless Wargaming change something at the replay file. If they did change something, and the unpacker fails, wait for the updated version from https://github.com/Monstrofil/replays_unpack. 

This bot uses a modified version of the Monstrofil's replays_unpack so copy-pasting Monstrofil's to this replays_unpack will not work. 

Files that probably get updated if WG changed or added something:

 - `replay_unpack/core/entity_def`
 - `replay_unpack/core/network`
 - `clients/wows/versions/*/constants.py`

Adding a new version to the modified unpacker:

 1. Copy the last version `clients/wows/versions/0_10_10` and paste it to
    `clients/wows/versions/0_10_11` using the command `cp -r
    clients/wows/versions/0_10_10/ clients/wows/versions/0_10_11`.
 2. Copy the `World_of_Warships/res_unpack/scripts/` and paste it to
    `clients/wows/versions/0_10_11` and overwrite everything.

### BOT COMMANDS

 - `render` renders the replay file.
 - `render logs` same as `render` but with counters, ribbons,
   achievements and death log.
 - `doom` and `benny` subcommands. For `doom`, the starting music will
   be a elevator meme music and if the player gets a kill `The Only
   Thing They Fear Is You` from `Doom` will play.
 - `chat` extracts the chat messages from the replay file.
 - `enablechat` and `disablechat` enables/disables chat extraction from the server it was invoked from. Can only be used by users with `Manage channel` permission.
 - `whitelist` and `unwhitelist` Argument: Discord server id. Adds/Removes the Discord server id to the bot's whitelist. If the bot joins to a server which is not in the whitelist, the bot will leave that server immediately.
 -  `settings get` and `settings set` Arguments: setting name, setting value. Gets and sets the settings. Valid settings `fps` and `quality`.
 - `guild chat` Gets the guild(s) that can extract the chat messages.
 - `guild list` Gets the list of guilds where the bot currently resides in.
 - `guild leave` Argument: Discord server id. Makes the bot leave the specified server.
 - `guild ban` Argument: Discord server id. Makes the bot leave the specified server and adds it to the blacklist.
 - `guild unban` Argument: Discord server id. Removes the id from the blacklist.
 - `backup` Backups the extract channels, whitelist, banned guilds and .env file.
 - `restore` Restores the file generated from the `backup` command.

### FOOTNOTES
This will probably the dirtiest program you will see, not tests, no straightforward way of updating it, but it works. Please don't contribute, just fork it and develop it as your own. Continually developing it wouldn't be possible for me since I'm gonna be busy for a long time (work).
