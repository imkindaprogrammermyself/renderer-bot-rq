import random
import string
import time

from utils.redisconn import REDIS
from utils.settings import retrieve_from_db, retrieve_from_env
from utils.exception import (
    VersionNotFoundError,
    ReadingError,
    RenderingError,
    UnsupportedBattleTypeError,
)
from renderer import get_renderer
from renderer.data import ReplayData
from replay_unpack.replay_parser import ReplayParser
from rq import get_current_job
from rq.job import Job


def task_render_single(
    data: bytes, requester_id: int, logs=False, benny=False, doom=False
):
    job: Job = get_current_job()

    try:
        t1 = time.perf_counter()
        job.meta["status"] = "Reading"
        job.save_meta()

        try:
            replay_info = ReplayParser(data).get_info()
        except RuntimeError:
            raise VersionNotFoundError("Version not supported.")
        except Exception:
            raise ReadingError("Reading failed.")

        replay_data: ReplayData = replay_info["hidden"]["replay_data"]
        replay_data.match.battle_type = replay_info["open"]["gameMode"]
        replay_data.match.match_group = replay_info["open"]["matchGroup"]
        replay_data.version = "_".join(
            replay_info["open"]["clientVersionFromExe"].split(",")[:3]
        )

        if replay_data.match.battle_type not in [7, 11, 14, 15, 16]:
            raise UnsupportedBattleTypeError("Unsupported battle type.")

        try:
            video_data = get_renderer(replay_data.version)(
                replay_data=replay_data,
                fps=retrieve_from_db("FPS"),
                quality=retrieve_from_db("QUALITY"),
                logs=logs,
                benny=benny,
                doom=doom,
            ).start()
        except ModuleNotFoundError:
            raise VersionNotFoundError("Unsupported version.")
        except Exception:
            raise RenderingError("Rendering failed.")

        t2 = time.perf_counter()
        str_taken = time.strftime("%M:%S", time.gmtime(t2 - t1))
        random_str = "".join(
            random.choice(string.ascii_uppercase[:6]) for _ in range(4)
        )
        random_str += "".join(random.choice(string.digits) for _ in range(8))
        return video_data, random_str, str_taken
    except Exception as e:
        return e
    finally:
        REDIS.set(
            f"cooldown_{requester_id}", "", ex=retrieve_from_env("TASK_COOLDOWN", int)
        )
