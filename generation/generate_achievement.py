import json
import os
import pickle
import struct
import zlib
from os.path import join


class GPEncode(json.JSONEncoder):
    def default(self, o):
        try:
            for e in ['Cameras', 'DockCamera', 'damageDistribution']:
                o.__dict__.pop(e, o.__dict__)
            return o.__dict__
        except AttributeError:
            return {}


def get_data(gp_type: str):
    gp_file_path = join('resources', 'GameParams.data')
    with open(gp_file_path, "rb") as f:
        gp_data: bytes = f.read()
    gp_data: bytes = struct.pack('B' * len(gp_data), *gp_data[::-1])
    gp_data: bytes = zlib.decompress(gp_data)
    gp_data: dict = pickle.loads(gp_data, encoding='windows-1251')
    return filter(lambda g: g.typeinfo.type == gp_type, gp_data[0].values())


if __name__ == '__main__':
    dict_data = {}
    list_data = get_data('Achievement')

    import shutil

    for data in list_data:
        path = join(os.getcwd(), 'resources', 'achievements', 'icons', f"icon_achievement_{data.uiName}.png")
        new_path = join(os.getcwd(), 'generated', 'achievements', f"{data.id}.png")
        if os.path.exists(path):
            os.makedirs(os.path.dirname(new_path), exist_ok=True)
            shutil.copy(path, new_path)



