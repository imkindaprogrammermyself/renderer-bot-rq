import random
import string
import time

from io import StringIO
from utils.redisconn import REDIS
from utils.settings import retrieve_from_env
from utils.exception import VersionNotFoundError, ReadingError, UnsupportedBattleTypeError
from renderer.data import ReplayData
from replay_unpack.replay_parser import ReplayParser
from rq import get_current_job
from rq.job import Job


def task_extract_chat(data: bytes, requester_id: int):
    job: Job = get_current_job()

    try:
        t1 = time.perf_counter()
        job.meta["status"] = "Reading"
        job.save_meta()

        try:
            replay_info = ReplayParser(data).get_info()
        except RuntimeError:
            raise VersionNotFoundError
        except Exception:
            raise ReadingError

        replay_data: ReplayData = replay_info['hidden']['replay_data']
        replay_data.match.battle_type = replay_info['open']['gameMode']
        replay_data.match.match_group = replay_info['open']['matchGroup']
        replay_data.version = '_'.join(
            replay_info['open']['clientVersionFromExe'].split(',')[:3])

        if replay_data.match.battle_type not in [7, 11, 14, 15, 16]:
            raise UnsupportedBattleTypeError

        relation = {-1: 'YOU', 0: 'ALLY', 1: 'ENEMY'}

        with StringIO() as sio:
            for chat in replay_data.chat:
                msg_time = time.strftime(
                    '%M:%S', time.gmtime(chat.message_time))

                if chat.clan:
                    sio.write(
                        f"{msg_time} [{relation[chat.relation]}][{chat.clan}][{chat.name}]: {chat.message}\n")
                else:
                    sio.write(
                        f"{msg_time} [{relation[chat.relation]}][{chat.name}]: {chat.message}\n")

            sio.seek(0)
            t2 = time.perf_counter()
            str_taken = time.strftime('%M:%S', time.gmtime(t2 - t1))
            random_str = "".join(random.choice(
                string.ascii_uppercase[:6]) for _ in range(4))
            random_str += "".join(random.choice(string.digits)
                                  for _ in range(8))
            return sio.read(), random_str, str_taken
    except Exception as e:
        return e
    finally:
        REDIS.set(f"cooldown_{requester_id}", "",
                  ex=retrieve_from_env('TASK_COOLDOWN', int))
