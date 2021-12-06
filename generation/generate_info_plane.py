import json
import struct
import zlib
import pickle

from os.path import join


class GPEncode(json.JSONEncoder):
    def default(self, o):
        try:
            for e in ['Cameras', 'DockCamera', 'damageDistribution']:
                o.__dict__.pop(e, o.__dict__)
            return o.__dict__
        except AttributeError:
            return {}


def get_params_data(*gp_type: str):
    gp_file_path = join('resources', 'GameParams.data')
    with open(gp_file_path, "rb") as f:
        gp_data = f.read()
    gp_data = struct.pack('B' * len(gp_data), *gp_data[::-1])
    gp_data = zlib.decompress(gp_data)
    gp_data = pickle.loads(gp_data, encoding='windows-1251')

    def _do_filter(_type):
        return filter(lambda g: g.typeinfo.type == _type, gp_data[0].values())

    return map(_do_filter, gp_type)


if __name__ == '__main__':
    p, a = get_params_data('Projectile', 'Aircraft')
    p = {y.name: y for y in p}

    dict_planes_info = {}

    for plane in a:
        if b := plane.bombName:
            try:
                ammo_type = p[b].ammoType
            except KeyError:
                ammo_type = None
        else:
            ammo_type = None

        pi = {"species": plane.typeinfo.species,
              "ammo_type": ammo_type}
        dict_planes_info[plane.id] = pi

    with open(join('..', 'generation', 'generated', 'info_planes.json'), 'w') as f:
        json.dump(dict_planes_info, f, indent=1)