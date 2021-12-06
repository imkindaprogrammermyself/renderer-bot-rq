import json
import pickle
import struct
import zlib
import polib

from polib import MOFile, MOEntry
from os.path import join
from typing import Dict


class GPEncode(json.JSONEncoder):
    def default(self, o):
        try:
            for e in ['Cameras', 'DockCamera', 'damageDistribution']:
                o.__dict__.pop(e, o.__dict__)
            return o.__dict__
        except AttributeError:
            return {}


def get_ship_data(gp_type: str):
    gp_file_path = join('resources', 'GameParams.data')
    with open(gp_file_path, "rb") as f:
        gp_data: bytes = f.read()
    gp_data: bytes = struct.pack('B' * len(gp_data), *gp_data[::-1])
    gp_data: bytes = zlib.decompress(gp_data)
    gp_data: dict = pickle.loads(gp_data, encoding='windows-1251')
    return filter(lambda g: g.typeinfo.type == gp_type, gp_data[0].values())


if __name__ == '__main__':
    dict_ships = {}
    list_ships = get_ship_data('Ship')

    for ship in list_ships:
        dict_ships[ship.id] = ship

    mo_file_path = join('resources', 'global.mo')
    mo_strings: MOFile = polib.mofile(mo_file_path)
    dict_strings = {}

    for mo_string in mo_strings:
        mo_string: MOEntry
        dict_strings[mo_string.msgid] = mo_string.msgstr

    dict_ships_info: Dict[int, Dict] = {}

    for ship in dict_ships.values():

        si = {
            "name": dict_strings[f"IDS_{ship.index}"].upper(),
            "species": ship.typeinfo.species,
            "level": ship.level
        }

        visibility_coeffs = set()
        visibility_coeffs.add(0)

        for attr in ship.__dict__:
            if "_Hull" in attr:
                visibility_coeffs.add(getattr(ship, attr).visibilityCoeff)

        si['visibility_coef'] = max(visibility_coeffs)
        dict_ships_info[ship.id] = si

    with open(join('..', 'generation', 'generated', 'info_ship.json'), 'w') as f:
        json.dump(dict_ships_info, f, indent=1)
    #
    # with open(join('..', 'generation', 'generated', 'ships.json'), 'w') as f:
    #     json.dump(dict_ships_json, f, indent=1, sort_keys=True)
