from typing import Dict, List, Optional


class Base:
    __slots__ = ['_hash', '_str_hash']

    def __init__(self):
        self._hash = 0

    def _calculate_hash(self):
        to_hash = [self.__getattribute__(v) for v in self.__slots__]
        to_hash.append(self.__class__.__name__)
        self._hash = hash(tuple(to_hash))

    def __hash__(self):
        if self._hash:
            return self._hash
        else:
            self._calculate_hash()
            return self._hash

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._calculate_hash()


class Match:
    __slots__ = ['arena_id', 'map_name', 'owner_avatar_id', 'owner_vehicle_id', 'owner_team', 'owner_realm',
                 'battle_type', 'match_group']

    def __init__(self):
        self.arena_id: int = 0
        self.map_name: str = ""
        self.owner_avatar_id: int = 0
        self.owner_vehicle_id: int = 0
        self.owner_team: int = 0
        self.owner_realm: str = ""
        self.battle_type: int = 0
        self.match_group: str = ""


class Player:
    __slots__ = ['avatar_id', 'account_id', 'vehicle_id', 'ship_params_id', 'realm', 'bot', 'name', 'clan_name',
                 'clan_color', 'relation']

    def __init__(self):
        self.avatar_id: int = 0
        self.account_id: int = 0
        self.vehicle_id: int = 0
        self.ship_params_id: int = 0
        self.realm: str = ""
        self.bot: bool = False
        self.name: str = ""
        self.clan_name: str = ""
        self.clan_color: int = 0
        self.relation: int = 0


class Ship(Base):
    __slots__ = ['avatar_id', 'vehicle_id', 'ship_params_id', 'relation', 'is_alive', 'is_owner', 'health',
                 'health_max', '_x', '_y', '_yaw', 'last_x', 'last_y', 'last_yaw']

    def __init__(self):
        super().__init__()
        self.avatar_id: int = 0
        self.vehicle_id: int = 0
        self.ship_params_id: int = 0
        self.relation: int = 0
        self.is_alive: bool = True
        self.is_owner: bool = False
        self.health: int = 0
        self.health_max: int = 0
        self._x: int = -2500
        self._y: int = -2500
        self._yaw: int = -180
        self.last_x: int = -2500
        self.last_y: int = -2500
        self.last_yaw: int = -180

    @property
    def x(self) -> int:
        return self._x if self.is_visible else self.last_x

    @x.setter
    def x(self, val):
        val = round(val)
        self._x = val
        self.last_x = val if val != -2500 else self.last_x

    @property
    def y(self) -> int:
        return self._y if self.is_visible else self.last_y

    @y.setter
    def y(self, val):
        val = round(val)
        self._y = val
        self.last_y = val if val != -2500 else self.last_y

    @property
    def yaw(self) -> int:
        return self._yaw if self.is_visible else self.last_yaw

    @yaw.setter
    def yaw(self, val):
        import math
        val = round(math.degrees(val))
        self._yaw = val
        self.last_yaw = val if val != -180 else self.last_yaw

    @property
    def is_visible(self) -> bool:
        return self._x != -2500 and self._y != -2500


class Plane(Base):
    __slots__ = ["plane_id", "owner_id", "plane_params_id", "index", "purpose", "departures", "relation", "_x", "_y"]

    # Squadron Index:
    # 1: First squadron of the ship, usually Rocket planes of CV.
    # 2: Second squadron, usually torpedo bombers.
    # 3: Third squadron, usually dive bombers,
    #
    # Squadron purpose:
    # 0: MAIN_SQUADRON (player controlled squadron),
    # 1: ATTACKER (post-attack/recalled squadron),
    # 2: SQUADRON_FIGHTER,
    # 3: SHIP_FIGHTER,
    # 4: SCOUT,
    # 5: AIR_DROP (I dont know about this)
    # 6: AIR STRIKE (HE or DC)

    def __init__(self):
        super().__init__()
        self.plane_id: int = 0
        self.owner_id: int = 0
        self.plane_params_id: int = 0
        self.index: int = 0
        self.purpose: int = 0
        self.departures: int = 0
        self.relation: int = 0
        self._x: int = 0
        self._y: int = 0

    @property
    def x(self) -> int:
        return self._x

    @x.setter
    def x(self, val):
        self._x = round(val)

    @property
    def y(self) -> int:
        return self._y

    @y.setter
    def y(self, val):
        self._y = round(val)


class Ward(Base):
    __slots__ = ["plane_id", "vehicle_id", "relation", "_x", "_y", "_radius", "_duration"]

    def __init__(self):
        super().__init__()
        self.plane_id: int = 0
        self.vehicle_id: int = 0
        self.relation: int = 0
        self._x: int = 0
        self._y: int = 0
        self._radius: int = 0
        self._duration: int = 0

    @property
    def x(self) -> int:
        return self._x

    @x.setter
    def x(self, val):
        self._x = round(val)

    @property
    def y(self) -> int:
        return self._y

    @y.setter
    def y(self, val):
        self._y = round(val)

    @property
    def radius(self) -> int:
        return self._radius

    @radius.setter
    def radius(self, val):
        self._radius = round(val)

    @property
    def duration(self) -> int:
        return self._duration

    @duration.setter
    def duration(self, val):
        self._duration = round(val)


class Capture(Base):
    __slots__ = ['id', 'x', 'y', 'radius', 'inner_radius', 'team_id', 'relation', 'both_inside', 'has_invaders',
                 'invader_team', 'progress_percent', 'progress_total']

    def __init__(self):
        super().__init__()
        self.id: int = 0
        self.x: float = 0.0
        self.y: float = 0.0
        self.radius: float = 0.0
        self.inner_radius: float = 0.0
        self.team_id: int = -1
        self.relation: int = -1
        self.both_inside: bool = False
        self.has_invaders: bool = False
        self.invader_team: int = 0
        self.progress_percent: float = 0.0
        self.progress_total: float = 0.0


class Ribbon(Base):
    attr_map = {
        1: "torpedo_hit",
        3: "ship_aircraft_kill",
        27: "plane_aircraft_kill",
        4: "crit",
        5: "frag",
        6: "fire",
        7: "flooding",
        8: "citadel",
        9: "defended",
        10: "captured",
        11: "assist",
        13: "secondary",
        19: "spotted"
    }

    __slots__ = ["torpedo_hit", "ship_aircraft_kill", "plane_aircraft_kill", "crit", "frag", "fire", "flooding",
                 "citadel", "defended", "captured", "assist", "secondary", "spotted", "main", "bomb", "rocket"]

    def __init__(self):
        super().__init__()
        self.torpedo_hit = 0
        self.ship_aircraft_kill = 0
        self.plane_aircraft_kill = 0
        self.crit = 0
        self.frag = 0
        self.fire = 0
        self.flooding = 0
        self.citadel = 0
        self.defended = 0
        self.captured = 0
        self.assist = 0
        self.secondary = 0
        self.spotted = 0
        self.main = 0
        self.bomb = 0
        self.rocket = 0

    def set_ribbon_counter(self, ribbon_id: int, count: int):
        if ribbon_id in {14, 15, 16, 17, 28}:
            self.main += count
        elif ribbon_id in {25, 26, 30, 34, 35}:
            self.rocket += count
        elif ribbon_id in {20, 21, 23}:
            self.bomb += count
        else:
            try:
                self.__setattr__(self.attr_map[ribbon_id], count)
            except Exception:
                pass

    def non_zero(self):
        dict_has_values = {}
        for attr in self.__slots__:
            if val := self.__getattribute__(attr):
                dict_has_values[attr] = val
        return dict_has_values


class Score(Base):
    __slots__ = ['ally_score', 'enemy_score', 'win_score']

    def __init__(self):
        super().__init__()
        self.ally_score: int = 0
        self.enemy_score: int = 0
        self.win_score: int = 0


class Achievement(Base):
    __slots__ = ['id', 'count']

    def __init__(self):
        super().__init__()
        self.id = 0
        self.count = 0

    def __hash__(self):
        to_hash = []
        for attr in self.__slots__:
            to_hash.append(self.__getattribute__(attr))
        return hash(tuple(to_hash))


class Death(Base):
    __slots__ = ['time', 'killer_name', 'killer_vehicle_id', 'killed_name', 'killed_vehicle_id', 'death_type',
                 'killer_avatar_id', 'killed_avatar_id']

    def __init__(self):
        super().__init__()
        self.time = "00:00"
        self.killer_name = ""
        self.killer_avatar_id = 0
        self.killer_vehicle_id = 0
        self.killed_name = ""
        self.killed_avatar_id = 0
        self.killed_vehicle_id = 0
        self.death_type = 0


class Weather(Base):
    __slots__ = ['vision_distance_plane', 'vision_distance_ship']

    def __init__(self):
        super().__init__()
        self.vision_distance_plane = 0.0
        self.vision_distance_ship = 0.0


class States:
    __slots__ = ['ships', 'planes', 'wards', 'captures', 'deaths', 'time', 'damage', 'ribbon', 'achievement', 'score',
                 'weather', 'damage_agro', 'damage_spot']

    def __init__(self):
        self.ships: Dict[int, Ship] = {}
        self.planes: Dict[int, Plane] = {}
        self.wards: Dict[int, Ward] = {}
        self.captures: List[Capture] = []
        self.deaths: List[Death] = []
        self.time: str = "00:00"
        self.damage: int = 0
        self.damage_agro: int = 0
        self.damage_spot: int = 0
        self.ribbon: Optional[Ribbon] = None
        self.achievement: List[Achievement] = []
        self.score: Optional[Score] = None
        self.weather: Optional[Weather] = None


class ChatMessage:
    __slots__ = ['message_time', 'clan', 'clan_color', 'name', 'relation', 'message', 'group']

    def __init__(self):
        self.message_time: int = 0
        self.clan: str = ""
        self.clan_color: int = 0
        self.name: str = ""
        self.relation: int = 0
        self.message: str = ""
        self.group: str = ""


class ReplayData:
    __slots__ = ['arena_id', 'version', 'players', 'match', 'states', 'chat', 'owner_frag_times']

    def __init__(self):
        self.arena_id = 0
        self.version: str = ""
        self.match: Match = Match()
        self.players: dict[int, Player] = {}
        self.states: dict[float, States] = {}
        self.chat: list[ChatMessage] = []
        self.owner_frag_times: list[float] = []


class DataShare:
    __slots__ = ["health", "in_range"]

    def __init__(self):
        self.health: int = 0
        self.in_range: bool = False
