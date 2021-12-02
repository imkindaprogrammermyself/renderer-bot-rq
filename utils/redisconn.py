import redis
import aioredis
import asyncio
from os import getenv
from .logger import LOGGER_REDIS, EXIT
from .helpers import check_environ_vars
from dotenv import load_dotenv

load_dotenv()

check_environ_vars(LOGGER_REDIS, 'REDIS_TESTING_URL', 'REDIS_PRODUCTION_URL')

if getenv("ENVIRONMENT") == "TESTING":
    REDIS_URL = getenv("REDIS_TESTING_URL")
else:
    REDIS_URL = getenv("REDIS_PRODUCTION_URL")

REDIS = redis.from_url(REDIS_URL)
ASYNC_REDIS = aioredis.from_url(REDIS_URL)


async def check_redis():
    return await ASYNC_REDIS.client_id()


try:
    asyncio.get_event_loop().run_until_complete(check_redis())
    REDIS.client_id()
except (redis.exceptions.ConnectionError, aioredis.exceptions.ConnectionError):
    LOGGER_REDIS.error(f'Cannot connect to {REDIS_URL}..', extra=EXIT)

