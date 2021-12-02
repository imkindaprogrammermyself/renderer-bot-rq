# coding=utf-8
import logging
from json import JSONEncoder

from replay_unpack.clients import wows
from replay_unpack.replay_reader import ReplayReader, ReplayInfo
from renderer import *

logging.basicConfig(
    level=logging.ERROR
)


class DefaultEncoder(JSONEncoder):
    def default(self, o):
        try:
            return o.__dict__
        except AttributeError:
            return str(o)


class ReplayParser(object):
    def __init__(self, replay_data: bytes, strict: bool = True):
        """
        :param replay_data: Read bytes from a replay file.
        :param strict: Stop when an error occurs.
        """
        self._replay_data: bytes = replay_data
        self._is_strict_mode = strict
        self._reader = ReplayReader(replay_data)

    def get_info(self):
        replay = self._reader.get_replay_data()

        error = None
        try:
            hidden_data = self._get_hidden_data(replay)
        except Exception as e:
            if isinstance(e, RuntimeError):
                error = str(e)
            logging.exception(e)
            hidden_data = None

            # raise error in strict mode
            if self._is_strict_mode:
                raise

        result = {
            "open": replay.engine_data,
            "extra_data": replay.extra_data,
            "hidden": hidden_data,
            "error": error
        }

        return result

    def _get_hidden_data(self, replay: ReplayInfo):
        player = wows.ReplayPlayer(replay.engine_data
                                   .get('clientVersionFromXml')
                                   .replace(' ', '')
                                   .split(','))

        player.play(replay.decrypted_data, self._is_strict_mode)
        return player.get_info()


# if __name__ == '__main__':
#     import argparse

#     parser = argparse.ArgumentParser()
#     parser.add_argument('--replay', type=str, required=True)
#     parser.add_argument(
#         '--log_level',
#         choices=['CRITICAL', 'ERROR', 'WARNING', 'INFO', 'DEBUG'],
#         required=False,
#         default='ERROR'
#     )
#     parser.add_argument(
#         '--strict_mode',
#         action='store_true',
#         required=False
#     )

#     namespace = parser.parse_args()
#     logging.basicConfig(
#         level=getattr(logging, namespace.log_level))
#     with open(namespace.replay, "rb") as f:
#         replay_info = ReplayParser(f.read(), strict=namespace.strict_mode).get_info()
#         match_data: Match = replay_info['hidden']['data_match']
#         print({n: match_data.__getattribute__(n) for n in match_data.__slots__})
