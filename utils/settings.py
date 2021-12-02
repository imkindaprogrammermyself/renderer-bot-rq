import os
from typing import Union, Callable
from utils.redisconn import REDIS
from utils.logger import LOGGER_WORKER, EXIT
from os import getenv

if SETTINGS_PREFIX := getenv("SETTINGS_PREFIX"):
    pass
else:
    LOGGER_WORKER.error("SETTING_PREFIX variable not declared. Exiting...", extra=EXIT)


def retrieve_from_db(setting_name: str) -> Union[list, int, str]:
    key_name = f"{SETTINGS_PREFIX}.{setting_name}"
    if not REDIS.exists(key_name):
        raise RuntimeError(f"Key {key_name} doesn't exists.")

    d_type = REDIS.type(key_name).decode()

    if d_type == "set":
        return list(item.decode() for item in REDIS.smembers(key_name))
    else:
        try:
            return int(REDIS.get(key_name).decode())
        except ValueError:
            return REDIS.get(key_name).decode()


def retrieve_from_env(setting_name: str, converter: Callable, allow_none=False) -> Union[int, str, None]:
    try:
        return converter(os.getenv(setting_name))
    except Exception as e:
        if allow_none:
            return None
        else:
            raise e


