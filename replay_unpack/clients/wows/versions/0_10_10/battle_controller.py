# coding=utf-8
import logging
import pickle
import copy
import time

from replay_unpack.core import IBattleController
from replay_unpack.core.entity import Entity
from .constants import DamageStatsType, Category, TaskType, Status

from renderer.data import *

try:
    from .constants import DEATH_TYPES
except ImportError:
    DEATH_TYPES = {}
from .players_info import PlayersInfo


class BattleController(IBattleController):

    def __init__(self):
        self._entities = {}
        self._achievements = {}
        self._ribbons = {}
        self._players = PlayersInfo()
        self._battle_result = None
        self._damage_map = {}
        self._agro_damage_map = {}
        self._spot_damage_map = {}
        self._shots_damage_map = {}
        self._death_map = []
        self._map = {}
        self._player_id = None
        self._arena_id = None
        self._dead_planes = {}
        ################################################################################################################

        self._match = Match()
        self._weather: Weather = Weather()
        self._dict_players: Dict[int, Player] = {}
        self._dict_ships: Dict[int, Ship] = {}
        self._dict_planes: Dict[int, Plane] = {}
        self._dict_wards: Dict[int, Ward] = {}
        self._dict_states: Dict[int, States] = {}
        self._list_deaths: List[Death] = []

        self._time_left: int = 0
        self._messages: list[ChatMessage] = []

        self._skip = 0
        self._start_time = 0
        self._owner_frags_times: list[float] = []
        self._packet_time = 0

        ################################################################################################################

        Entity.subscribe_method_call('Avatar', 'onBattleEnd', self.onBattleEnd)
        Entity.subscribe_method_call('Avatar', 'onArenaStateReceived', self.onArenaStateReceived)
        Entity.subscribe_method_call('Avatar', 'onGameRoomStateChanged', self.onPlayerInfoUpdate)
        Entity.subscribe_method_call('Avatar', 'receiveVehicleDeath', self.receiveVehicleDeath)
        # Entity.subscribe_method_call('Vehicle', 'setConsumables', self.onSetConsumable)
        Entity.subscribe_method_call('Avatar', 'onRibbon', self.onRibbon)
        Entity.subscribe_method_call('Avatar', 'onAchievementEarned', self.onAchievementEarned)
        Entity.subscribe_method_call('Avatar', 'receiveDamageStat', self.receiveDamageStat)
        Entity.subscribe_method_call('Avatar', 'receive_planeDeath', self.receive_planeDeath)
        Entity.subscribe_method_call('Avatar', 'onNewPlayerSpawnedInBattle', self.onNewPlayerSpawnedInBattle)
        Entity.subscribe_method_call('Vehicle', 'receiveDamagesOnShip', self.g_receiveDamagesOnShip)

        ################################################################################################################

        Entity.subscribe_method_call('Avatar', 'updateMinimapVisionInfo', self.updateMinimapVisionInfo)
        Entity.subscribe_method_call('Avatar', 'receive_addMinimapSquadron', self.receive_addMinimapSquadron)
        Entity.subscribe_method_call('Avatar', 'receive_updateMinimapSquadron', self.receive_updateMinimapSquadron)
        Entity.subscribe_method_call('Avatar', 'receive_removeMinimapSquadron', self.receive_removeMinimapSquadron)
        Entity.subscribe_method_call('Avatar', 'receive_wardAdded', self.receive_wardAdded)
        Entity.subscribe_method_call('Avatar', 'receive_wardRemoved', self.receive_wardRemoved)
        Entity.subscribe_property_change('Avatar', 'weatherParams', self.set_weather_params)
        Entity.subscribe_property_change('Vehicle', 'health', self.set_health)
        Entity.subscribe_property_change('Vehicle', 'maxHealth', self.set_max_health)
        Entity.subscribe_property_change('Vehicle', 'isAlive', self.set_is_alive)
        Entity.subscribe_method_call('Avatar', 'onChatMessage', self.on_chat_message)
        Entity.subscribe_property_change('BattleLogic', 'timeLeft', self.on_time_left_change)

    ####################################################################################################################

    def packet_time(self, packet_time: float):
        self._packet_time = packet_time

    def on_time_left_change(self, avatar, time_left):
        # TODO: UPDATE VEHICLE

        self._time_left = time_left

        if self._skip < 31:
            self._skip += 1
            return

        if not self._start_time:
            self._start_time = self._packet_time

        with Score() as score:
            try:
                team_scores = self.battle_logic.properties['client']['state']['missions']['teamsScore']
                score.win_score = self.battle_logic.properties['client']['state']['missions']['teamWinScore']

                for team in team_scores:
                    if team['teamId'] == self._match.owner_team:
                        score.ally_score = team['score']
                    else:
                        score.enemy_score = team['score']
            except Exception:
                pass

        temp_captures: List[Capture] = []

        try:

            for idx, cp in enumerate(self._getCapturePointsInfo()):
                with Capture() as cs:
                    cs.id = idx
                    cs.x, cs.y = cp["position"]
                    cs.progress_percent = cp["progress"]
                    cs.progress_total = -1.0
                    cs.radius = cp["radius"]
                    cs.inner_radius = cp["innerRadius"]
                    cs.team_id = cp["teamId"]
                    cs.invader_team = cp["invaderTeam"]
                    cs.both_inside = bool(cp["bothInside"])
                    cs.has_invaders = cp["hasInvaders"]

                    if cp["teamId"] == self._match.owner_team and cp["teamId"] != -1:
                        cs.relation = 0
                    elif cp["teamId"] != self._match.owner_team and cp["teamId"] != -1:
                        cs.relation = 1
                    else:
                        cs.relation = -1
                temp_captures.append(cs)

        except Exception:
            pass

        with Ribbon() as ribbon:
            try:
                for k, v in self._ribbons[self._match.owner_avatar_id].items():
                    ribbon.set_ribbon_counter(k, v)
            except KeyError:
                pass

        achievements: List[Achievement] = []
        try:
            for k, v in self._achievements[self._match.owner_avatar_id].items():
                with Achievement() as ac:
                    ac.id = k
                    ac.count = v
                achievements.append(ac)
        except KeyError:
            pass

        states = States()
        states.ships = copy.deepcopy(self._dict_ships)
        states.planes = copy.deepcopy(self._dict_planes)
        states.wards = copy.deepcopy(self._dict_wards)
        states.captures = copy.deepcopy(temp_captures)
        states.deaths = copy.deepcopy(list(reversed(self._list_deaths)))
        states.time = time.strftime('%M:%S', time.gmtime(self._time_left))
        states.damage = sum(round(i[1]) for v in self._damage_map.values() for i in v.values())
        states.damage_agro = sum(round(i[1]) for v in self._agro_damage_map.values() for i in v.values())
        states.damage_spot = sum(round(i[1]) for v in self._spot_damage_map.values() for i in v.values())
        states.ribbon = ribbon
        states.achievement = achievements
        states.score = copy.deepcopy(score)
        states.weather = copy.deepcopy(self._weather)
        self._dict_states[round(self._time_left)] = states

    def on_chat_message(self, avatar, avatar_id: int, group: str, message: str, data: bytes):
        try:
            if avatar_id != -1:
                player = self._dict_players[avatar_id]
                cm = ChatMessage()
                cm.message_time = self._time_left
                cm.clan = player.clan_name
                cm.clan_color = player.clan_color
                cm.name = player.name
                cm.relation = player.relation
                cm.message = message
                cm.group = group
                self._messages.append(cm)

        except KeyError:
            pass

    def _create_player_vehicle_data(self):
        owner: dict = list(
            filter(lambda ply: ply["avatarId"] == self._player_id, self._players.get_info().values())).pop()

        self._match.arena_id = self._arena_id
        self._match.owner_team = owner["teamId"]
        self._match.owner_realm = owner["realm"]
        self._match.owner_avatar_id = owner["avatarId"]
        self._match.owner_vehicle_id = owner["shipId"]

        for p in self._players.get_info().values():
            player = Player()
            player.avatar_id = p['avatarId']
            player.account_id = p['accountDBID']
            player.vehicle_id = p['shipId']
            player.ship_params_id = p['shipParamsId']
            player.realm = p['realm']
            player.bot = p['isBot']
            player.name = p['name']
            player.clan_name = p['clanTag']
            player.clan_color = p['clanColor']

            is_ally = p['teamId'] == owner['teamId']
            is_owner = p['avatarId'] == owner['avatarId']

            if is_ally and not is_owner:
                player.relation = 0
            elif not is_ally and not is_owner:
                player.relation = 1
            else:
                player.relation = -1

            with Ship() as ship:
                ship.avatar_id = p['avatarId']
                ship.vehicle_id = p['shipId']
                ship.ship_params_id = p['shipParamsId']
                ship.relation = player.relation
                ship.health_max = p['maxHealth']
                ship.is_owner = is_owner

            self._dict_players[p['avatarId']] = player
            self._dict_ships[p['shipId']] = ship

    def _update_player_vehicle_data(self):
        for p in self._players.get_info().values():
            player = Player()
            player.avatar_id = p['avatarId']
            player.vehicle_id = p['shipId']
            player.ship_params_id = p['shipParamsId']
            player.name = p['name']
            player.clan_name = p['clanTag']
            player.clan_color = p['clanColor']

            is_ally = p['teamId'] == self._match.owner_team
            is_owner = p['avatarId'] == self._match.owner_avatar_id

            if is_ally and not is_owner:
                player.relation = 0
            elif not is_ally and not is_owner:
                player.relation = 1
            else:
                player.relation = -1

            with Ship() as ship:
                ship.avatar_id = p['avatarId']
                ship.vehicle_id = p['shipId']
                ship.ship_params_id = p['shipParamsId']
                ship.relation = player.relation
                ship.is_owner = p['avatarId'] == self._match.owner_avatar_id
                ship.health_max = p['maxHealth']

            if player.avatar_id not in self._dict_players:
                self._dict_players[player.avatar_id] = player

            if ship.vehicle_id not in self._dict_ships:
                self._dict_ships[ship.vehicle_id] = ship

    def updateMinimapVisionInfo(self, avatar, ships_minimap_diff, buildings_minimap_diff):
        pack_pattern = (
            (-2500.0, 2500.0, 11),
            (-2500.0, 2500.0, 11),
            (-3.141592753589793, 3.141592753589793, 8)
        )
        for e in ships_minimap_diff:
            try:
                vehicle_id = e['vehicleID']
                x, y, yaw = unpack_values(e['packedData'], pack_pattern)
                with self._dict_ships[vehicle_id] as ship:
                    ship.x = x
                    ship.y = y
                    ship.yaw = yaw
            except KeyError:
                pass

    def receive_addMinimapSquadron(self, avatar, plane_id: int, team_id, gameparams_id, pos, unk):
        owner_id, index, purpose, departures = unpack_plane_id(plane_id)
        x, y = pos
        with Plane() as plane:
            plane.plane_id = plane_id
            plane.owner_id = owner_id
            plane.plane_params_id = gameparams_id
            plane.index = index
            plane.purpose = purpose
            plane.departures = departures

            is_ally = team_id == self._match.owner_team
            is_owner = owner_id == self._match.owner_vehicle_id

            if is_ally and not is_owner:
                plane.relation = 0
            elif not is_ally and not is_owner:
                plane.relation = 1
            else:
                plane.relation = -1

            plane.x = x
            plane.y = y
        self._dict_planes[plane_id] = plane

    def receive_updateMinimapSquadron(self, avatar, plane_id, pos):
        try:
            x, y = pos
            with self._dict_planes[plane_id] as plane:
                plane.x = x
                plane.y = y
        except KeyError:
            pass

    def receive_removeMinimapSquadron(self, avatar, plane_id):
        try:
            self._dict_planes.pop(plane_id)
        except KeyError:
            pass

    def receive_wardAdded(self, avatar, plane_id, position, radius, duration, team_id, vehicle_id):
        x, _, y = position
        with Ward() as ward:
            ward.plane_id = plane_id
            ward.x = x
            ward.y = y
            ward.radius = radius
            ward.duration = duration
            ward.relation = 0 if team_id == self._match.owner_team else 1
            ward.vehicle_id = vehicle_id
        self._dict_wards[plane_id] = ward

    def receive_wardRemoved(self, avatar, plane_id):
        self._dict_wards.pop(plane_id)

    def set_health(self, entity: Entity, health: float):
        try:
            with self._dict_ships[entity.id] as ship:
                ship.health = round(health)
        except KeyError:
            pass

    def set_max_health(self, entity: Entity, max_health: float):
        try:
            with self._dict_ships[entity.id] as ship:
                ship.health_max = round(max_health)
        except KeyError:
            pass

    def set_is_alive(self, entity: Entity, is_alive: int):
        try:
            with self._dict_ships[entity.id] as ship:
                ship.is_alive = bool(is_alive)
        except KeyError:
            pass

    def set_weather_params(self, avatar, params: dict):
        self._weather.vision_distance_ship = params['maxShipVisionDistance']
        self._weather.vision_distance_plane = params['maxPlaneVisionDistance']

    ####################################################################################################################

    def onSetConsumable(self, vehicle, blob):
        # print(pickle.loads(blob))
        pass

    @property
    def entities(self):
        return self._entities

    @property
    def battle_logic(self):
        return next(e for e in self._entities.values() if e.get_name() == 'BattleLogic')

    def create_entity(self, entity: Entity):
        self._entities[entity.id] = entity

    def destroy_entity(self, entity: Entity):
        self._entities.pop(entity.id)

    def on_player_enter_world(self, entity_id: int):
        self._player_id = entity_id

    def get_info(self):
        self._match.map_name = self._map
        replay_data = ReplayData()
        replay_data.match = self._match
        replay_data.players = self._dict_players
        replay_data.states = self._dict_states
        replay_data.chat = self._messages
        replay_data.owner_frag_times = self._owner_frags_times
        replay_data.arena_id = self._arena_id

        return dict(
            achievements=self._achievements,
            ribbons=self._ribbons,
            players=self._players.get_info(),
            battle_result=self._battle_result,
            damage_map=self._damage_map,
            shots_damage_map=self._shots_damage_map,
            death_map=self._death_map,
            death_info=self._getDeathsInfo(),
            map=self._map,
            player_id=self._player_id,
            control_points=self._getCapturePointsInfo(),
            tasks=list(self._getTasksInfo()),
            skills=dict(),
            arena_id=self._arena_id,
            replay_data=replay_data
        )

    def _getDeathsInfo(self):
        deaths = {}
        for killedVehicleId, fraggerVehicleId, typeDeath in self._death_map:
            death_type = DEATH_TYPES.get(typeDeath)
            if death_type is None:
                logging.warning('Unknown death type %s', typeDeath)
                continue

            deaths[killedVehicleId] = {
                'killer_id': fraggerVehicleId,
                'icon': death_type['icon'],
                'name': death_type['name'],
            }
        return deaths

    def _getCapturePointsInfo(self):
        return self.battle_logic.properties['client']['state'].get('controlPoints', [])

    def _getTasksInfo(self):
        tasks = self.battle_logic.properties['client']['state'].get('tasks', [])
        for task in tasks:
            yield {
                "category": Category.names[task['category']],
                "status": Status.names[task['status']],
                "name": task['name'],
                "type": TaskType.names[task['type']]
            }

    def onBattleEnd(self, avatar, teamId, state):
        self._battle_result = dict(winner_team_id=teamId, victory_type=state)

    def onNewPlayerSpawnedInBattle(self, avatar, pickle_data):
        self._players.create_or_update_players(pickle.loads(pickle_data, encoding='latin1'))
        self._update_player_vehicle_data()

    def onArenaStateReceived(self, avatar, arenaUniqueId, teamBuildTypeId, preBattlesInfo, playersStates,
                             observersState, buildingsInfo):
        self._arena_id = arenaUniqueId
        try:
            self._players.create_or_update_players(pickle.loads(playersStates, encoding='latin1'))
        except UnicodeDecodeError:
            pass
        self._create_player_vehicle_data()

    def onPlayerInfoUpdate(self, avatar, playersData, observersData):
        self._players.create_or_update_players(pickle.loads(playersData, encoding='latin1'))

    def receiveDamageStat(self, avatar, blob):
        normalized = {}
        normalized_agro = {}
        normalized_spot = {}
        for (type_, bool_), value in pickle.loads(blob).items():
            # TODO: improve damage_map and list other damage types too
            if bool_ == DamageStatsType.DAMAGE_STATS_AGRO:
                normalized_agro.setdefault(type_, {}).setdefault(bool_, 0)
                normalized_agro[type_][bool_] = value
            elif bool_ == DamageStatsType.DAMAGE_STATS_SPOT:
                normalized_spot.setdefault(type_, {}).setdefault(bool_, 0)
                normalized_spot[type_][bool_] = value
            elif bool_ == DamageStatsType.DAMAGE_STATS_ENEMY:
                normalized.setdefault(type_, {}).setdefault(bool_, 0)
                normalized[type_][bool_] = value
            else:
                print(type_, bool_, value)
                continue
        self._agro_damage_map.update(normalized_agro)
        self._spot_damage_map.update(normalized_spot)
        self._damage_map.update(normalized)

    def onRibbon(self, avatar, ribbon_id):
        self._ribbons.setdefault(avatar.id, {}).setdefault(ribbon_id, 0)
        self._ribbons[avatar.id][ribbon_id] += 1

    def onAchievementEarned(self, avatar, avatar_id, achievement_id):
        self._achievements.setdefault(avatar_id, {}).setdefault(achievement_id, 0)
        self._achievements[avatar_id][achievement_id] += 1

    def receiveVehicleDeath(self, avatar, killedVehicleId, fraggerVehicleId, typeDeath):
        if fraggerVehicleId == self._match.owner_vehicle_id:
            self._owner_frags_times.append(self._packet_time - self._start_time)

        with Death() as death:
            killer_info = self._dict_players[self._dict_ships[fraggerVehicleId].avatar_id]
            killed_info = self._dict_players[self._dict_ships[killedVehicleId].avatar_id]

            if killer_info.clan_name:
                death.killer_name = f"[{killer_info.clan_name}]{killer_info.name}"
            else:
                death.killer_name = killer_info.name

            if killed_info.clan_name:
                death.killed_name = f"[{killed_info.clan_name}]{killed_info.name}"
            else:
                death.killed_name = killed_info.name

            death.killer_vehicle_id = killer_info.vehicle_id
            death.killer_avatar_id = killer_info.avatar_id

            death.killed_vehicle_id = killed_info.vehicle_id
            death.killed_avatar_id = killed_info.avatar_id

            death.time = time.strftime('%M:%S', time.gmtime(self._time_left))
            death.death_type = typeDeath
        self._list_deaths.append(death)
        self._death_map.append((killedVehicleId, fraggerVehicleId, typeDeath))

    def g_receiveDamagesOnShip(self, vehicle, damages):
        for damage_info in damages:
            self._shots_damage_map.setdefault(vehicle.id, {}).setdefault(damage_info['vehicleID'], 0)
            self._shots_damage_map[vehicle.id][damage_info['vehicleID']] += damage_info['damage']

    def receive_planeDeath(self, avatar, squadronID, planeIDs, reason, attackerId):
        self._dead_planes.setdefault(attackerId, 0)
        self._dead_planes[attackerId] += len(planeIDs)

    @property
    def map(self):
        raise NotImplemented()

    @map.setter
    def map(self, value):
        self._map = value.lstrip('spaces/')


def unpack_value(packed_value, value_min, value_max, bits):
    return packed_value / (2 ** bits - 1) * (abs(value_min) + abs(value_max)) - abs(value_min)


def unpack_values(packed_value, pack_pattern):
    values = []
    for i, pattern in enumerate(pack_pattern):
        min_value, max_value, bits = pattern
        value = packed_value & (2 ** bits - 1)

        values.append(unpack_value(value, min_value, max_value, bits))
        packed_value = packed_value >> bits
    try:
        assert packed_value == 0
    except AssertionError:
        pass
    return tuple(values)


def unpack_plane_id(packed_value: int) -> tuple:
    # avatar_id, index, purpose, departures
    bits = [32, 3, 3, 1]
    values = []
    for bit in bits:
        value = packed_value & (2 ** bit - 1)
        packed_value = packed_value >> bit
        values.append(value)
    return tuple(values)
