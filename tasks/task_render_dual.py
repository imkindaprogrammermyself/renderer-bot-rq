import random
import string
import time
import os
import zipfile
import tempfile

from io import BytesIO
from utils.redisconn import REDIS
from utils.settings import retrieve_from_env
from utils.exception import (
    VersionNotFoundError,
    ReadingError,
    RenderingError,
    UnsupportedBattleTypeError,
    MultipleReplaysError,
    ArenaIdMismatchError,
    NotEnoughReplaysError,
)
from renderer import get_renderer
from renderer.data import ReplayData
from replay_unpack.replay_parser import ReplayParser
from rq import get_current_job
from rq.job import Job
from PIL import Image
from imageio_ffmpeg import write_frames


def delete_temp_files(*files):
    try:
        for file in files:
            if os.path.exists(file):
                os.remove(file)
    except Exception:
        pass


class Parser:
    def __init__(self, data: bytes):
        self._data = data

    def parse(self) -> ReplayData:
        try:
            replay_info = ReplayParser(self._data).get_info()
        except RuntimeError:
            raise VersionNotFoundError("Unsupported replay version")
        except Exception:
            raise ReadingError("Failed to read replay")

        replay_data: ReplayData = replay_info["hidden"]["replay_data"]
        replay_data.match.battle_type = replay_info["open"]["gameMode"]
        replay_data.match.match_group = replay_info["open"]["matchGroup"]
        replay_data.version = "_".join(
            replay_info["open"]["clientVersionFromExe"].split(",")[:3]
        )

        if replay_data.match.battle_type not in [7, 11, 14, 15, 16]:
            raise UnsupportedBattleTypeError("Unsupported battle type")

        return replay_data


def task_render_dual(data: bytes, requester_id: int):
    job: Job = get_current_job()

    try:
        t1 = time.perf_counter()
        with BytesIO(data) as zip_data:
            zip_obj = zipfile.ZipFile(zip_data)

            if len(zip_obj.namelist()) > 2:
                raise MultipleReplaysError("Too much replay files in zip")

            if len(zip_obj.namelist()) < 2:
                raise NotEnoughReplaysError("Not enough replays found.")

            replay_files = {}

            for replay_name in zip_obj.namelist():
                prefix = replay_name[0].lower()

                if prefix == "a":
                    replay_files[prefix] = zip_obj.read(replay_name)
                elif prefix == "b":
                    replay_files[prefix] = zip_obj.read(replay_name)

            difference = {"a", "b"}.difference(set(replay_files.keys()))

            if len(difference) != 0:
                not_found = " or ".join(f"`{i}`, `{i.upper()}`" for i in difference)
                raise FileNotFoundError(
                    f"No replay files found starting with {not_found}"
                )

            job.meta["status"] = "Reading Replay A..."
            job.save_meta()
            replay_data_a = Parser(replay_files["a"]).parse()
            job.meta["status"] = "Reading Replay B..."
            job.save_meta()
            replay_data_b = Parser(replay_files["b"]).parse()

            if replay_data_a.arena_id != replay_data_b.arena_id:
                raise ArenaIdMismatchError("Arena IDs do not match.")

            try:
                share = {}

                renderer_a = get_renderer(replay_data_a.version)(
                    replay_data=replay_data_a, dual=True, as_enemy=False, share=share
                )
                renderer_b = get_renderer(replay_data_b.version)(
                    replay_data=replay_data_b, dual=True, as_enemy=True, share=share
                )

                total = min(renderer_a.get_total(), renderer_b.get_total())

                video_file = tempfile.NamedTemporaryFile(
                    "w+b", suffix=".mp4", delete=False
                )
                writer = write_frames(
                    path=video_file.name,
                    fps=30,
                    macro_block_size=25,
                    quality=9,
                    size=(800, 850),
                    pix_fmt_in="rgba",
                )
                writer.send(None)

                for idx, (a, b) in enumerate(
                    zip(renderer_a.generator(), renderer_b.generator())
                ):
                    new_image = Image.alpha_composite(a, b)
                    writer.send(new_image.__array__())
                    job.meta["progress"] = (idx + 1) / total
                    job.save_meta()

                writer.close()
            except ModuleNotFoundError:
                raise VersionNotFoundError("Version unsupported.")
            except Exception:
                raise RenderingError("Rendering failed.")

            with open(video_file.name, "rb") as f:
                video_data = f.read()

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
