from os import environ, getenv
from utils.logger import *
from utils.helpers import check_environ_vars
from dotenv import load_dotenv

import json
import os

try:
    os.chdir(os.path.join(*os.path.abspath(__file__).split(os.sep)[:-1]))
except Exception:
    pass


def update_db():
    from utils.redisconn import REDIS

    check_environ_vars(LOGGER, 'BOT_CONTROL_CHANNEL', 'BOT_OWNERS', 'FPS', 'QUALITY', 'SETTINGS_PREFIX',
                       'BOT_SERVER_WHITELIST', exit_on_err=True)

    settings_prefix = getenv('SETTINGS_PREFIX')
    data_types = {
        'BOT_CONTROL_CHANNEL': int,
        'BOT_OWNERS': list,
        'FPS': int,
        'QUALITY': int,
        'BOT_SERVER_WHITELIST': list
    }

    for key, value_type in data_types.items():
        if value_type == int:
            REDIS.set(f"{settings_prefix}.{key}", int(getenv(key)))
        elif value_type == list:
            for member in json.loads(getenv(key)):
                REDIS.sadd(f"{settings_prefix}.{key}", member)


if __name__ == '__main__':
    try:
        load_dotenv()
        environ.pop('ENV_LOADED')
    except KeyError:
        LOGGER.error(".env file not found.", extra=EXIT)

    try:
        if environ.get('ENVIRONMENT') not in ['TESTING', 'PRODUCTION']:
            raise ValueError
    except KeyError:
        LOGGER.error("Missing \"ENVIRONMENT\" environment variable.", extra=EXIT)
    except ValueError:
        LOGGER.error("Invalid value for \"ENVIRONMENT\" environment variable.", extra=EXIT)
    else:
        update_db()

        from bot.bot import run_bot

        LOGGER.info("Running the bot...")
        run_bot()
