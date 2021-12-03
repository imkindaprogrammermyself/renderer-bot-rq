import json
import math
import subprocess
import tempfile
import time
from collections import namedtuple
from importlib.resources import open_binary, open_text, path, read_text
from math import ceil
from typing import Generator, Union

from imageio_ffmpeg import get_ffmpeg_exe, write_frames
from lxml import etree
from PIL import Image, ImageDraw, ImageFont
from PIL.ImageFont import FreeTypeFont
from rq.job import Job

from renderer.constants import *
from renderer.data import (
    Achievement,
    Capture,
    DataShare,
    Death,
    Plane,
    ReplayData,
    Ribbon,
    Score,
    Ship,
    Ward,
    Weather,
)
from renderer.helpers import (
    catch_exception,
    catch_exception_non_generator,
    check_trim,
    delete_temp_files,
    draw_grid,
    generate_holder,
    generate_torus,
    get_map_size,
    load_image,
    memoize,
    memoize_image_gen,
    paste_args,
    paste_args_centered,
    paste_centered,
    replace_color,
)
from rq import get_current_job


class RendererBase:
    def __init__(
        self,
        replay_data: ReplayData,
        fps=60,
        quality=5,
        logs=False,
        benny=False,
        dual=False,
        as_enemy=False,
        doom=False,
        share: Union[dict, None] = None,
    ):
        self._replay_data = replay_data
        self._fps = 60 if benny else fps
        self._quality = quality
        self._logs = logs
        self._benny = benny
        self._dual = dual
        self._as_enemy = as_enemy
        self._doom = doom
        self._share: dict[int, DataShare] = share
        self._res_package = f"{__package__}.resources"
        self._shared_res_package = f"{__package__}.shared"
        # colors
        self._colors = COLORS_NORMAL
        self._global_bg_color: tuple = (0, 0, 0, 0)
        # scaling
        self._scaling_x: float = 0.0
        self._scaling_y: float = 0.0
        # images
        self._img_minimap: Union[Image.Image, None] = None
        self._img_info_panel: Union[Image.Image, None] = None
        # fonts
        self._font: Union[FreeTypeFont, None] = None
        self._font_damage: Union[FreeTypeFont, None] = None
        self._font_time: Union[FreeTypeFont, None] = None
        self._font_weather: Union[FreeTypeFont, None] = None
        self._font_score: Union[FreeTypeFont, None] = None
        # info
        self._nt_ship_info = ShipInfo = namedtuple(
            "ShipInfo", "name species level visibility_coef holder"
        )
        self._nt_plane_info = PlaneInfo = namedtuple("PlaneInfo", "species ammo_type")
        self._info_ships: dict[int, ShipInfo] = {}
        self._info_planes: dict[int, PlaneInfo] = {}
        self._cap_total_progresses: dict[int, float] = {}
        if not self._dual:
            self._relations = RELATION_NORMAL_STR
        else:
            if self._as_enemy:
                self._relations = RELATION_DUAL_ENEMY_STR
            else:
                self._relations = RELATION_DUAL_ALLY_STR
        self._iterations = 0
        self._logs_y = 0
        self._tiers_roman = TIERS
        self._death_types: dict[int, dict] = {}
        # player's initial state
        self._player_pos_x: int = 0
        self._player_pos_y: int = 0
        self._player_plane_pos_x: int = 0
        self._player_plane_pos_y: int = 0
        self._player_view_range: int = 0
        self._player_is_alive: bool = True
        # output
        self._temp_output_path = tempfile.NamedTemporaryFile(
            "w", delete=False, suffix=".mp4"
        ).name
        # cache
        self._cache = {}
        self._cache_max_it = 10
        # weather
        self._weather: Union[Weather, None] = None
        self._job: Job = get_current_job()

    def start(self) -> bytes:
        assert not all([self._doom, self._benny])
        assert not self._dual or not self._as_enemy
        assert not self._share

        self._load_map()
        self._load_fonts()
        self._get_used_ships()
        self._get_used_planes()
        self._get_player_initial_state()
        self._load_death_icons()
        writer = self._get_writer()
        last_key = list(self._replay_data.states.keys())[-1]
        states_len = len(self._replay_data.states)
        writer.send(None)

        for idx, (_time, states) in enumerate(self._replay_data.states.items()):
            self._weather = states.weather

            minimap = self._img_minimap.copy()
            info_panel = self._img_info_panel.copy()

            info_panel_draw = ImageDraw.Draw(info_panel)
            info_panel_draw.text((5, 5), text=states.time, font=self._font_time)

            if self._replay_data.match.battle_type != 14:
                info_panel.paste(*self._layer_score(states.score))
                info_panel.paste(
                    *self._layer_score_timer(states.score, states.captures)
                )

            if weather_info_image := self._layer_weather(states.weather):
                info_panel.paste(*weather_info_image)

            generators = [
                self._layer_caps(states.captures),
                self._layer_wards(states.wards),
                self._layer_ships(states.ships),
                self._layer_planes(states.planes),
            ]

            if self._logs:
                _logs = [
                    self._layer_damage(
                        states.damage, states.damage_agro, states.damage_spot
                    ),
                    self._layer_ribbon(states.ribbon),
                    self._layer_achievement(states.achievement),
                    self._layer_death(states.deaths),
                ]

                for _log in _logs:
                    if _log:
                        info_panel.paste(*_log)

            for generator in generators:
                for args in generator:
                    if args:
                        minimap.paste(*args)

            info_panel.paste(minimap, (0, 50))

            if last_key == _time:
                for _ in range(0, 60):
                    writer.send(info_panel.__array__())
            else:
                writer.send(info_panel.__array__())

            self._job.meta["progress"] = (idx + 1) / states_len
            self._job.save_meta()

            self._delete_expired()
            self._iterations += 1
        writer.close()

        with open(self._temp_output_path, "rb") as f:
            video_data = f.read()

        if self._doom and self._replay_data.owner_frag_times:
            doomed = tempfile.NamedTemporaryFile("w", delete=False, suffix=".mp4").name
            drop = 4.708
            actual_kill = self._replay_data.owner_frag_times[0] / self._fps
            sync_time = actual_kill - drop

            with path(self._shared_res_package, "elevator.mp3") as elevator_path:
                elevator_bgm = str(elevator_path.absolute())

            with path(self._shared_res_package, "doom.mp3") as doom_path:
                doom_bgm = str(doom_path)

            _filter = (
                f"[1]adelay={round(sync_time * 1000)}|{round(sync_time * 1000)}[a];"
                f"[2]afade=t=out:st={sync_time}:d={drop}[b];[a][b]amix[out]"
            )

            subprocess.run(
                [
                    get_ffmpeg_exe(),
                    "-i",
                    self._temp_output_path,
                    "-i",
                    doom_bgm,
                    "-i",
                    elevator_bgm,
                    "-filter_complex",
                    _filter,
                    "-map",
                    "0:v:0",
                    "-map",
                    "[out]",
                    "-c:v",
                    "copy",
                    "-shortest",
                    "-y",
                    "-loglevel",
                    "quiet",
                    doomed,
                ],
                text=True,
            )

            with open(doomed, "rb") as f:
                video_data = f.read()
            delete_temp_files(doomed)
        delete_temp_files(self._temp_output_path)
        return video_data

    def generator(self):
        assert self._dual
        assert isinstance(self._share, dict)
        assert not self._benny
        assert not self._doom
        assert not self._logs

        self._load_map()
        self._load_fonts()
        self._get_used_ships()
        self._get_used_planes()
        self._get_player_initial_state()
        self._load_death_icons()

        for _time, states in self._replay_data.states.items():
            self._weather = states.weather

            minimap = self._img_minimap.copy()
            info_panel = self._img_info_panel.copy()

            if not self._as_enemy:
                info_panel_draw = ImageDraw.Draw(info_panel)
                info_panel_draw.text((5, 5), text=states.time, font=self._font_time)

            if self._replay_data.match.battle_type != 14:
                if not self._as_enemy:
                    info_panel.paste(*self._layer_score(states.score))
                    info_panel.paste(
                        *self._layer_score_timer(states.score, states.captures)
                    )

            if (
                weather_info_image := self._layer_weather(states.weather)
                and not self._dual
                and not self._as_enemy
            ):
                info_panel.paste(*weather_info_image)

            if self._as_enemy:
                generators = [
                    self._layer_wards(states.wards),
                    self._layer_ships(states.ships),
                    self._layer_planes(states.planes),
                ]
            else:
                generators = [
                    self._layer_caps(states.captures),
                    self._layer_wards(states.wards),
                    self._layer_ships(states.ships),
                    self._layer_planes(states.planes),
                ]

            for generator in generators:
                for args in generator:
                    if args:
                        minimap.paste(*args)

            info_panel.paste(minimap, (0, 50))
            self._delete_expired()
            self._iterations += 1
            yield info_panel.copy()

    def get_total(self) -> int:
        return len(self._replay_data.states)

    ##############
    # SHIP LAYER #
    ##############

    @catch_exception
    def _layer_ships(self, ship_state: dict[int, Ship]) -> Generator[tuple, None, None]:
        """
        Yields the ship icons complete with name and health bar.
        :param ship_state:
        :return:
        """
        for ship in sorted(
            ship_state.values(), key=lambda s: (s.is_alive, s.is_visible)
        ):
            if ship.is_owner:
                self._player_pos_x = ship.x
                self._player_pos_y = ship.y
                self._player_is_alive = ship.is_alive

            yield self._generate_ship(ship)
        return

    @memoize
    def _generate_ship(self, ship: Ship) -> Union[tuple, None]:
        """
        Generates ship icon with names and health bar.
        :param ship:
        :return:
        """
        info = self._info_ships[ship.vehicle_id]
        species = info.species

        x, y = self._get_scaled_xy(ship.x, -ship.y)
        yaw = -ship.yaw

        # view range and weather shenanigans

        dist = (
            math.hypot(ship.x - self._player_pos_x, ship.y - self._player_pos_y) * 0.03
        )
        dist_plane = (
            math.hypot(
                ship.x - self._player_plane_pos_x, ship.y - self._player_plane_pos_y
            )
            * 0.03
        )

        if self._weather.vision_distance_ship:
            sw_vision_km = self._weather.vision_distance_ship * 0.03
            ship_view_range = (
                self._player_view_range
                if sw_vision_km > self._player_view_range
                else sw_vision_km
            )
        else:
            ship_view_range = self._player_view_range

        if self._weather.vision_distance_plane:
            pw_vision_km = self._weather.vision_distance_plane * 0.03
            plane_view_range = 15 if pw_vision_km > 15 else pw_vision_km
        else:
            plane_view_range = 15

        in_range_plane = dist_plane <= plane_view_range
        in_range_ship = dist <= ship_view_range
        in_range = in_range_ship or in_range_plane
        in_range = in_range or not self._player_is_alive
        ###
        if self._dual:
            player = self._replay_data.players[ship.avatar_id]
            if in_range:
                ds = DataShare()
                ds.in_range = in_range
                ds.health = ship.health
                self._share[player.account_id] = ds

            try:
                ds = self._share[player.account_id]
                in_range = ds.in_range or in_range
                ship.health = ds.health if ds.health else ship.health
            except KeyError:
                pass

        if self._dual and ship.relation == 1:
            return None

        icon = self._get_ship_icon(
            ship.is_alive, ship.is_visible, species, ship.relation, in_range
        ).rotate(yaw, Image.BICUBIC, True)

        if ship.is_alive:
            icon_holder = paste_centered(info.holder.copy(), icon)

            if ship.is_visible:
                if in_range:
                    self._draw_health_bar(
                        icon_holder, ship.health, ship.health_max, ship.relation
                    )
                    return paste_args_centered(icon_holder, x, y, True)
            return paste_args_centered(icon_holder, x, y, True)
        else:
            return paste_args_centered(icon, x, y, True)

    def _draw_health_bar(
        self, image: Image.Image, health: int, health_max: int, relation: int
    ):
        """
        Health bar stuff.
        :param image: Image where to draw the health bar.
        :param health: Ship health.
        :param health_max: Ship max health.
        :param relation: Ship relation.
        """
        if self._dual and self._as_enemy:
            color = self._colors[1]
        else:
            relation = 0 if relation == -1 else relation
            color = self._colors[relation]
        draw = ImageDraw.Draw(image)
        health_bar_width = 50
        health_bar_y_pos = 65
        health_bar_height = 4
        w, h = image.size
        x0 = w / 2 - health_bar_width / 2
        x1 = w - (w / 2 - x0) - x0
        health = health if health > 0 else health_max
        x1 = x1 * (health / health_max) + x0
        draw.rectangle(
            [(x0, health_bar_y_pos), (w - x0, health_bar_y_pos + health_bar_height)],
            outline="#808080",
        )
        draw.rectangle(
            [(x0, health_bar_y_pos), (x1, health_bar_y_pos + health_bar_height)],
            fill=color,
        )

    @memoize_image_gen
    def _get_ship_icon(
        self,
        is_alive: bool,
        is_visible: bool,
        species: str,
        relation: int,
        is_in_range: bool,
    ):
        """
        Gets the ship icon from disk/memory.
        :param is_alive: Is the ship alive?
        :param is_visible: Is the ship visible?
        :param species: Ship species aka. Battleship, Cruiser, Destroyer, Carrier.
        :param relation: Player relation.
        :param is_in_range: Is the ship in range?
        :return: Proper ship icon.
        """
        icon_res = f"{self._shared_res_package}.ship_icons"
        icon_type = self._relations[relation]

        if relation == -1 and not self._dual:
            if is_alive:
                species = "alive"
            else:
                species = "dead"
        else:
            if is_alive:
                if is_visible:
                    if is_in_range:
                        icon_type = icon_type
                    else:
                        icon_type = f"outside.{icon_type}"
                else:
                    icon_type = "hidden"
            else:
                icon_type = "dead"

        resource = f"{icon_res}.{icon_type}", f"{species}.png"
        return load_image(self, resource, True)

    #################
    # CAPTURE LAYER #
    #################

    @catch_exception
    def _layer_caps(self, cap_state: list[Capture]) -> Generator[tuple, None, None]:
        for cap in cap_state:
            yield self._generate_cap(cap)
        return

    @memoize
    def _generate_cap(self, cap: Capture) -> Union[tuple, None]:
        """
        This generates the capture area depending on the battle type.
        :param cap:
        :return:
        """

        if self._replay_data.match.battle_type == 14:
            return

        if cap.progress_total != -1.0:
            progress_val = round(
                1 - cap.progress_total / self._cap_total_progresses[cap.id], 1
            )
        else:
            progress_val = round(cap.progress_percent, 2)

        if self._replay_data.match.battle_type in [7, 11, 15]:
            x, y = self._get_scaled_xy(round(cap.x), round(-cap.y))
            radius = self._get_scaled_r(cap.radius)
            w = h = round(radius * 2)
            capture_area = self._get_capture_area_domination(cap.relation).resize(
                (w, h)
            )

            if cap.has_invaders and cap.invader_team != -1:
                if cap.invader_team == self._replay_data.match.owner_team:
                    progress = self._get_progress(
                        self._colors[cap.relation], self._colors[0], progress_val
                    )
                else:
                    progress = self._get_progress(
                        self._colors[cap.relation], self._colors[1], progress_val
                    )
            else:
                progress = replace_color(
                    self._get_progress_normal(),
                    from_color="#000000",
                    to_color=self._colors[cap.relation],
                )

            progress = progress.resize(
                (round(w / 3), round(h / 3)), resample=Image.LANCZOS
            )
            capture_area = paste_centered(capture_area, progress, True)
            return paste_args_centered(capture_area, x, y, True)
        else:
            x, y = self._get_scaled_xy(round(cap.x), round(-cap.y))
            radius = round(self._get_scaled_r(cap.radius))
            inner_radius = round(self._get_scaled_r(cap.inner_radius))

            if cap.has_invaders and cap.invader_team != -1:
                if (
                    cap.invader_team == self._replay_data.match.owner_team
                    and progress_val > 0
                ):
                    to_color = self._colors[0]
                elif (
                    cap.invader_team != self._replay_data.match.owner_team
                    and progress_val > 0
                ):
                    to_color = self._colors[1]
                else:
                    to_color = self._colors[cap.relation]
                    progress_val = 1
            else:
                to_color = self._colors[cap.relation]
                progress_val = 1

            torus = generate_torus(
                self,
                self._colors[cap.relation],
                to_color,
                radius,
                inner_radius,
                progress_val,
            )
            return paste_args_centered(torus, x, y, True)

    def _get_progress_normal(self):
        """
        Gets the neutral capture area from disk or memory.
        :return:
        """
        return load_image(self, (self._shared_res_package, "cap_normal.png"), True)

    @memoize_image_gen
    def _get_progress(self, from_color: str, to_color: str, percent: float):
        """
        Generates the diamond progress icon and colors it depending on the percentage value.
        :param from_color: background color
        :param to_color: foreground color
        :param percent: progress 0.0 - 1.0
        :return: Image.Image
        """
        attr_name = "cap_invaded"
        progress_diamond = load_image(
            self, (f"{self._shared_res_package}", f"{attr_name}.png")
        )
        bg_diamond = replace_color(progress_diamond, "#000000", from_color)
        fg_diamond = replace_color(progress_diamond, "#000000", to_color)
        mask = Image.new("RGBA", progress_diamond.size, None)
        mask_draw = ImageDraw.Draw(mask, "RGBA")
        mask_draw.pieslice(
            [(0, 0), (progress_diamond.width - 1, progress_diamond.height - 1)],
            start=-90,
            end=(-90 + 360 * percent),
            fill="black",
        )
        bg_diamond.paste(fg_diamond, mask)
        return bg_diamond

    def _get_capture_area_domination(self, relation: int):
        """
        Gets the capture area image from disk or memory.
        :param relation:
        :return:
        """
        str_relation = self._relations[relation] if relation != -1 else "neutral"
        attr_name = f"cap_{str_relation}"
        return load_image(self, (self._shared_res_package, f"{attr_name}.png"), True)

    ###############
    # PLANE LAYER #
    ###############

    @catch_exception
    def _layer_planes(
        self, plane_state: dict[int, Plane]
    ) -> Generator[tuple, None, None]:
        """
        Yields tuple for pasting.
        :param plane_state: Data provided by the modified replay_unpack.
        :return:
        """
        for plane in plane_state.values():

            x, y = self._get_scaled_xy(plane.x, -plane.y)

            if plane.relation == -1 and plane.purpose == 0:
                self._player_plane_pos_x = plane.x
                self._player_plane_pos_y = plane.y

            if plane.relation == 1 and self._dual:
                yield None
            else:
                icon = self._get_plane_icon(
                    plane.plane_params_id, plane.purpose, plane.relation
                )
                yield paste_args_centered(icon, x, y, True)
        return

    @memoize_image_gen
    def _get_plane_icon(self, plane_params_id: int, purpose: int, relation: int):
        """
        Gets the plane icon from disk/memory.
        :param plane_params_id: Plane gameparams id.
        :param purpose: Plane's purpose.
        :param relation: Plane's relation.
        :return: PIL Image.
        """
        icon_res = f"{self._shared_res_package}.plane_icons"
        icon_type = self._relations[relation]
        plane_info = self._info_planes[plane_params_id]

        if purpose in [0, 1]:
            if plane_info.species == "Dive":
                data = f"{icon_res}.{icon_type}", f"Dive_{plane_info.ammo_type}.png"
            else:
                data = f"{icon_res}.{icon_type}", f"{plane_info.species}.png"
        elif purpose in [2, 3]:
            data = f"{icon_res}.{icon_type}", "Cap.png"
        else:
            if purpose == 6:
                data = (
                    f"{icon_res}.{icon_type}",
                    f"Airstrike_{plane_info.ammo_type}.png",
                )
            else:
                data = f"{icon_res}.{icon_type}", "Scout.png"

        # icon_image = Image.open(BytesIO(read_binary(*data))).copy()
        icon_image = load_image(self, data)

        if purpose == 1:
            icon_image_return = icon_image.copy()
            icon_image_return.putalpha(64)
            return icon_image_return

        return icon_image.copy()

    ##############
    # WARD LAYER #
    ##############

    @catch_exception
    def _layer_wards(self, ward_state: dict[int, Ward]) -> Generator[tuple, None, None]:
        """
        This yields the ward circle (summoned fighters)
        :param ward_state:
        :return:
        """
        for ward_id, ward in ward_state.items():
            if ward.relation == 1 and self._dual:
                yield None
            else:
                yield self._generate_ward(ward)
        return

    @memoize
    def _generate_ward(self, ward: Ward) -> tuple:
        """
        Gets the ward image from disk or memory.
        :param ward: Data provided by the modified replay_unpack
        :return: Tuple for Image.paste function.
        """
        radius = ward.radius if ward.radius else 60
        x, y = self._get_scaled_xy(ward.x, -ward.y)

        if self._dual and self._as_enemy:
            ward_name = "ward_enemy"
        else:
            if ward.relation == 0:
                ward_name = "ward_ally"
            else:
                ward_name = "ward_enemy"

        w = h = round(self._get_scaled_r(radius) * 2 + 2)
        image = self._get_ward_image(
            (f"{self._shared_res_package}", f"{ward_name}.png"), (w, h)
        )
        return paste_args_centered(image, x, y, masked=True)

    def _get_ward_image(self, resource: tuple, size: tuple):
        image: Image.Image = load_image(self, resource, True)
        image = image.resize(size, resample=Image.LANCZOS)
        return image

    ###############
    # SCORE LAYER #
    ###############

    @catch_exception_non_generator
    def _layer_score(self, score_state: Score):
        """
        Generates scores. (checks for cached data first.)
        :param score_state: Data provided by the replay_unpack
        :return: PIL Image containing the scores/scores bar.
        """
        generated = self._generate_score(score_state)
        return paste_args(generated, 50, 12, False)

    @memoize
    def _generate_score(self, score_state: Score):
        """
        Generates scores.
        :param score_state: Data provided by the replay_unpack
        :return: PIL Image containing the scores/scores bar.
        """
        image: Image.Image = Image.new("RGBA", (700, 50), self._global_bg_color)
        mid_space = 50
        bar_height = 30
        mid = round(image.width / 2)
        bar_ally_x_pos = round(mid * (score_state.ally_score / score_state.win_score))
        bar_enemy_x_pos = round(mid * (score_state.enemy_score / score_state.win_score))
        ally_score_text_w, ally_score_text_h = self._font_score.getsize(
            f"{score_state.ally_score}"
        )
        separator_w, separator_h = self._font_score.getsize(":")
        draw = ImageDraw.Draw(image)

        # GREEN
        draw.rectangle(
            [(0, 0), (mid - mid_space, bar_height)], outline="#4ce8aa", width=1
        )
        draw.rectangle(
            [(0, 0), (bar_ally_x_pos - mid_space, bar_height)], fill="#4ce8aa"
        )
        # RED
        draw.rectangle(
            [(mid + mid_space, 0), (image.width - 1, bar_height)],
            outline="#fe4d2a",
            width=1,
        )
        draw.rectangle(
            [
                (mid + mid_space, 0),
                (round(image.width / 2) + bar_enemy_x_pos - 1, bar_height),
            ],
            fill="#fe4d2a",
        )

        draw.text(
            (mid - ally_score_text_w - 8, -1),
            text=str(score_state.ally_score),
            font=self._font_score,
            fill="white",
        )
        draw.text(
            (mid + 8, -1),
            text=str(score_state.enemy_score),
            font=self._font_score,
            fill="white",
        )
        draw.text((mid - round(separator_w / 2), -1), text=":", font=self._font_score)
        return image

    @catch_exception_non_generator
    def _layer_score_timer(self, score_state: Score, cap_state: list[Capture]):
        """
        Generates scores. (checks for cached data first.)
        :param score_state: Data provided by the replay_unpack
        :return: PIL Image containing the scores/scores bar.
        """
        generated = self._generate_score_timer(score_state, cap_state)
        return paste_args(generated, 800 - generated.width - 5, 5, False)

    @memoize_image_gen
    def _generate_score_timer(self, score_state: Score, cap_state: list[Capture]):
        """
        Generates scores.
        :param score_state: Data provided by the replay_unpack
        :return: PIL Image containing the scores/scores bar.
        """

        if self._replay_data.match.battle_type == 16:
            rate = 5
            score_tick = 5
        elif self._replay_data.match.battle_type == 15:
            rate = 10
            score_tick = 2
        elif self._replay_data.match.battle_type == 1:
            rate = 2
            score_tick = 6
        else:
            rate, score_tick = (3, 5) if len(cap_state) <= 3 else (4, 9)

        ally_caps = 0
        enemy_caps = 0

        for cap in cap_state:
            if cap.relation == 0 and not cap.both_inside:
                ally_caps += 1
            elif cap.relation == 1 and not cap.both_inside:
                enemy_caps += 1

        if ally_caps > 0:
            ally_cumulative_rate = ally_caps * rate
            ally_score_per_sec = ally_cumulative_rate / score_tick
            ally_remaining = score_state.win_score - score_state.ally_score
            ally_cap_time = time.strftime(
                "%M:%S", time.gmtime(ally_remaining / ally_score_per_sec)
            )
            setattr(self, "ally_cap_time", ally_cap_time)

        if enemy_caps > 0:
            enemy_cumulative_rate = enemy_caps * rate
            enemy_score_per_sec = enemy_cumulative_rate / score_tick
            enemy_remaining = score_state.win_score - score_state.enemy_score
            enemy_cap_time = time.strftime(
                "%M:%S", time.gmtime(enemy_remaining / enemy_score_per_sec)
            )
            setattr(self, "enemy_cap_time", enemy_cap_time)

        w, h = 41, 42

        bg_image: Image.Image = Image.new("RGBA", (w, h), self._global_bg_color)
        bg_image_draw = ImageDraw.Draw(bg_image)

        bg_image_draw.text(
            (0, 0),
            text=f"{getattr(self, 'ally_cap_time', '99:99')}",
            fill=self._colors[0],
            font=self._font_time,
        )
        bg_image_draw.text(
            (0, 18),
            text=f"{getattr(self, 'enemy_cap_time', '99:99')}",
            fill=self._colors[1],
            font=self._font_time,
        )

        return bg_image

    #################
    # WEATHER LAYER #
    #################

    @catch_exception_non_generator
    def _layer_weather(self, weather_state: Weather):
        if (
            weather_state.vision_distance_ship
            and weather_state.vision_distance_ship != 2000
        ):
            generated = self._generate_weather_info(weather_state)
            return paste_args(generated, 5, 25, False)
        else:
            return

    @memoize_image_gen
    def _generate_weather_info(self, weather_state: Weather):
        cyclone_icon: Image.Image = load_image(
            self, (self._shared_res_package, "cyclone.png"), True
        )
        cyclone_icon.thumbnail((21, 21), Image.LANCZOS)
        bg: Image.Image = Image.new("RGBA", (41, 21), self._global_bg_color)
        bg.paste(
            cyclone_icon,
            (0, int(bg.height / 2 - cyclone_icon.height / 2)),
            cyclone_icon,
        )
        bg_draw = ImageDraw.Draw(bg)
        dist_text = f"{round(weather_state.vision_distance_ship * 0.03) :02}"
        tw, th = self._font_weather.getsize(dist_text)
        bg_draw.text(
            (cyclone_icon.width + 3, int(bg.height / 2 - th / 2) - 3),
            text=dist_text,
            font=self._font_weather,
        )
        return bg

    ################
    # DAMAGE LAYER #
    ################

    @catch_exception_non_generator
    def _layer_damage(self, damage: int, agro: int, spot: int) -> tuple:
        return self._generate_damage(damage, agro, spot)

    @memoize
    def _generate_damage(self, damage: int, agro: int, spot: int):
        """
        Creates the damage counter image. Pretty straightforward.
        :param damage:
        :return:
        """
        text_damage = f"DAMAGE DEALT"
        text_agro = f"POTENTIAL"
        text_spot = f"SPOTTING"

        text_damage_val = f"{damage:,}".replace(",", " ")
        text_agro_val = f"{agro:,}".replace(",", " ")
        text_spot_val = f"{spot:,}".replace(",", " ")

        base: Image.Image = Image.new("RGBA", (490, 110), self._global_bg_color)
        base_draw = ImageDraw.Draw(base)

        y_pos = -5
        for text in [text_damage, text_agro, text_spot]:
            w, h = self._font_damage.getsize(text)
            base_draw.text((0, y_pos), text=text, font=self._font_damage)
            y_pos += h - 5

        y_pos = -5
        for text in [text_damage_val, text_agro_val, text_spot_val]:
            w, h = self._font_damage.getsize(text)
            x = base.width - w - 10
            base_draw.text((x, y_pos), text=text, font=self._font_damage)
            y_pos += h - 5
        return paste_args(base, 810, 5)

    ################
    # RIBBON LAYER #
    ################

    @catch_exception_non_generator
    def _layer_ribbon(self, ribbon_state: Ribbon):
        if not ribbon_state.non_zero():
            return
        generated = self._generate_ribbons(ribbon_state)
        self._logs_y = generated.height + 110
        return paste_args(generated, 810, 110, False)

    @memoize_image_gen
    def _generate_ribbons(self, ribbons):
        """
        This yields a tuple for the paste function.
        :param ribbons: Ribbon data provided by the modified replay_unpack.
        :return:
        """
        cx = 0  # Ribbons starting x position
        cy = 0  # Ribbons starting y position

        non_zeroes = ribbons.non_zero()

        # ribbon 133x51
        levels = ceil(len(non_zeroes) / 3)
        base_h = (51 + 10) * levels
        base = Image.new("RGBA", (490, base_h), self._global_bg_color)

        for idx, (k, v) in enumerate(ribbons.non_zero().items()):
            img_ribbon = self._get_ribbon_image(k, v)  # get the corresponding ribbon
            base.paste(img_ribbon, (cx, cy), img_ribbon)
            cx += img_ribbon.width + 40
            # sets the position to a new "line" if there's enough icons in that line.
            if (idx + 1) % 3 == 0:
                cy += 51 + 10
                cx = 0
        return base

    @memoize_image_gen
    def _get_ribbon_image(self, ribbon_name, count: int):
        """
        This loads (from disk or memory) the requested ribbon icon.
        :param ribbon_name:
        :param count:
        :return:
        """
        resource = f"{self._res_package}.ribbons"
        ribbon_img = load_image(self, (resource, f"{ribbon_name}.png"), True)
        text = f"x{count}"
        tw, th = self._font_score.getsize(text)
        draw = ImageDraw.Draw(ribbon_img)
        draw.text(
            (ribbon_img.width - tw - 4, ribbon_img.height - th - 3),
            text,
            font=self._font_score,
            stroke_width=1,
            stroke_fill="black",
        )
        return ribbon_img

    #####################
    # ACHIEVEMENT LAYER #
    #####################

    @catch_exception_non_generator
    def _layer_achievement(self, achievement: list[Achievement]):
        if not achievement:
            return

        generated = paste_args(
            self._generate_achievement(achievement), 810, self._logs_y, False
        )
        return generated

    @memoize_image_gen
    def _generate_achievement(self, achievement: list[Achievement]):
        cx = 0
        cy = 0

        # achievement 81x81

        ach_count = len(achievement)
        levels = ceil(ach_count / 6)
        base_w = 81 * 6 if ach_count > 6 else 81 * ach_count
        base_h = 81 * levels
        base = Image.new("RGBA", (base_w, base_h), self._global_bg_color)

        for idx, ac in enumerate(achievement):
            a_img: Image.Image = self._get_achievement_image(ac.id, ac.count)
            base.paste(a_img, (cx, cy), a_img)
            cx += a_img.width
            if (idx + 1) % 5 == 0:
                cy += a_img.height
                cx = 810
        return base

    @memoize_image_gen
    def _get_achievement_image(self, a_id: int, count: int):
        """
        This loads (from disk or memory) the requested achievement icon.
        :rtype: PngImageFile
        """
        resource = f"{self._res_package}.achievements"

        # Checks whether the icon is already loaded or not.
        # If not, load it and set it as an attribute for further usage.

        achievement_image: Image.Image = load_image(
            self, (resource, f"{a_id}.png"), True
        )
        # Don't display x{Count} if there's only 1 achievement of that type earned.
        if count > 1:
            text = f"x{count}"
            tw, th = self._font_score.getsize(text)
            draw = ImageDraw.Draw(achievement_image)
            draw.text(
                (achievement_image.width - tw - 5, achievement_image.height - th - 3),
                text,
                font=self._font_score,
                stroke_width=1,
                stroke_fill="black",
                fill="white",
            )
        return achievement_image

    ################
    # LAYER DEATHS #
    ################

    @catch_exception_non_generator
    def _layer_death(self, deaths: list[Death]):
        """
        This handles the death log and its position.
        Yields a tuple for pasting.
        :param deaths: Data provided by the modified replay_unpack
        :return:
        """

        if not deaths:
            return

        images = []

        for death in deaths[:6]:
            killer_player_info = self._replay_data.players[death.killer_avatar_id]
            killed_player_info = self._replay_data.players[death.killed_avatar_id]

            killer_ship_info = self._info_ships[killer_player_info.vehicle_id]
            killed_ship_info = self._info_ships[killed_player_info.vehicle_id]

            death_icon = self._get_death_type_icon(death.death_type), -1

            killer_ship_icon = (
                self._get_ship_frag_log_icon(
                    killer_ship_info.species, killer_player_info.relation, True
                ),
                4,
            )
            killed_ship_icon = (
                self._get_ship_frag_log_icon(
                    killed_ship_info.species, killed_player_info.relation, False
                ),
                4,
            )

            killer_ship_name = f"{self._tiers_roman[killer_ship_info.level - 1]} {killer_ship_info.name}"
            killed_ship_name = f"{self._tiers_roman[killed_ship_info.level - 1]} {killed_ship_info.name}"

            killer_color = self._colors[
                0 if killer_player_info.relation == -1 else killer_player_info.relation
            ]
            killed_color = self._colors[
                0 if killed_player_info.relation == -1 else killed_player_info.relation
            ]

            killer_name = death.killer_name, killer_color
            killer_ship_name = killer_ship_name, killer_color
            killed_name = death.killed_name, killed_color
            killed_ship_name = killed_ship_name, killed_color

            data = (
                killer_name,
                killer_ship_icon,
                killer_ship_name,
                death_icon,
                killed_name,
                killed_ship_icon,
                killed_ship_name,
            )

            line = self._get_line(*data)
            images.append(line)

        w = max(img.width for img in images)
        h = max(img.height for img in images)

        base: Image.Image = Image.new(
            "RGBA", (w, h * len(images)), self._global_bg_color
        )
        heights = []

        for image in images:
            heights.append(image.height)
            x = 0
            y = base.height - sum(heights)
            base.paste(*paste_args(image, x, y, True))

        return paste_args(base, 810, 850 - base.height, False)

    @memoize_image_gen
    def _get_line(
        self,
        killer_name,
        killer_icon: tuple[Image.Image, int],
        killer_ship_name,
        death_icon: tuple[Image.Image, int],
        killed_name,
        killed_icon: tuple[Image.Image, int],
        killed_ship_name,
    ):

        # get widths of elements with fixed width (ship name will be a fixed width)
        # sum it
        # base width - sum of the fixed widths
        # divide the difference to two and use it as width for the clan+name

        line_height = 21
        spacer = 4

        killer_ship_name_w, killer_ship_name_h = self._font.getsize(killer_ship_name[0])
        killed_ship_name_w, killed_ship_name_h = self._font.getsize(killed_ship_name[0])

        total_w_static = (
            killer_icon[0].width
            + killed_icon[0].width
            + killer_ship_name_w
            + killed_ship_name_w
        )
        total_w_static += (spacer * 6) + death_icon[0].width
        max_width = (490 - total_w_static) // 2

        killer_name_str, killer_name_w, killer_name_h = check_trim(
            killer_name[0], self._font, max_width
        )
        killed_name_str, killed_name_w, killed_name_h = check_trim(
            killed_name[0], self._font, max_width
        )

        killer_name = killer_name_str, killer_name[1]
        killed_name = killed_name_str, killed_name[1]

        total_width = total_w_static + killer_name_w + killed_name_w
        base: Image.Image = Image.new(
            "RGBA", (total_width, line_height), self._global_bg_color
        )
        base_draw = ImageDraw.Draw(base)
        pos_x = 0

        for n in [
            killer_name,
            killer_icon,
            killer_ship_name,
            death_icon,
            killed_name,
            killed_icon,
            killed_ship_name,
        ]:
            if isinstance(n, tuple) and all(isinstance(i, str) for i in n):
                text, color = n
                _w, _ = self._font.getsize(text)
                base_draw.text((pos_x, 0), text=text, font=self._font, fill=color)
                pos_x += _w + spacer
            elif isinstance(n, tuple) and all(
                isinstance(i, Image.Image) or isinstance(i, int) for i in n
            ):
                img, offset = n
                base.paste(img, (pos_x, offset), img)
                pos_x += img.width + spacer

        return base

    @memoize_image_gen
    def _get_ship_frag_log_icon(self, species: str, relation: int, killer: bool):
        """
        Gets the requested killer and killed ship icon and rotate it properly.
        Also caches the images too for consequent usage.
        :param species: Ship species.
        :param relation: Ship relation.
        :param killer: Is killer?
        :return: PIL Image.
        """
        str_relation = (
            self._relations[0] if relation == -1 else self._relations[relation]
        )
        _icon_res = (
            f"{self._shared_res_package}.ship_icons.{str_relation}",
            f"{species}.png",
        )
        image = load_image(self, _icon_res)

        if killer:
            return image.rotate(-90, resample=Image.BICUBIC, expand=True)
        else:
            return image.rotate(90, resample=Image.BICUBIC, expand=True)

    @memoize_image_gen
    def _get_death_type_icon(self, death_type: int) -> Image.Image:
        res_death_type_icons = f"{self._res_package}.frag_icons"
        attr_name = self._death_types[death_type]["icon"]

        try:
            icon = load_image(self, (res_death_type_icons, f"{attr_name}.png"))
        except Exception:
            icon = load_image(self, (res_death_type_icons, f"frags.png"))
        return icon

    ###########
    # LOADERS #
    ###########

    def _load_map(self):
        """
        Get the map info.
        Set the scaling factor for coordinates and radius.
        """
        try:
            target_package = (
                f"{self._res_package}.spaces.{self._replay_data.match.map_name}"
            )
            minimap_settings = read_text(target_package, "space.settings")
        except Exception:
            target_package = (
                f"{self._res_package}.spaces.s{self._replay_data.match.map_name}"
            )
            minimap_settings = read_text(target_package, "space.settings")

        minimap_settings = etree.fromstring(minimap_settings)

        if self._dual and self._as_enemy:
            map_w, map_h = get_map_size(minimap_settings)

            with open_binary(target_package, "minimap.png") as _map:
                island: Image.Image = Image.open(_map)

            base: Image.Image = Image.new("RGBA", (800, 800), "#00000000")
            self._scaling_x = island.width / map_w
            self._scaling_y = island.height / map_h
            self._img_minimap = base
            self._img_info_panel = base.copy().resize(
                (800, 850), resample=Image.NEAREST
            )
            return

        b_islands, b_water, b_legends = map(
            open_binary,
            (target_package, target_package, self._shared_res_package),
            ("minimap.png", "minimap_water.png", "minimap_grid_legends.png"),
        )

        water, island, legend = map(Image.open, [b_water, b_islands, b_legends])
        info_panel = water.copy()
        self._global_bg_color = info_panel.getpixel((10, 10))
        water = water.resize(legend.size, resample=Image.LANCZOS)
        water: Image.Image = Image.alpha_composite(water, legend)
        offset = water.width - island.width, water.height - island.height
        grid_image = draw_grid(island.size)
        water.paste(grid_image, offset, grid_image)
        water.paste(island, offset, island)

        info_panel = info_panel.resize(
            (water.width, water.height + 50), resample=Image.NEAREST
        )
        self._img_info_panel = info_panel

        if self._logs:
            new_base = Image.new(
                "RGBA",
                (info_panel.width + 500, info_panel.height),
                self._global_bg_color,
            )
            new_base.paste(info_panel)
            self._img_info_panel = new_base

        map_w, map_h = get_map_size(minimap_settings)
        self._scaling_x = island.width / map_w
        self._scaling_y = island.height / map_h
        self._img_minimap = water

    def _load_fonts(self):
        """
        Loads the required fonts.
        """
        self._font = ImageFont.truetype(
            open_binary(self._shared_res_package, "warhelios_bold.ttf"), size=12
        )
        self._font_damage = ImageFont.truetype(
            open_binary(self._shared_res_package, "warhelios_bold.ttf"), size=32
        )
        self._font_time = ImageFont.truetype(
            open_binary(self._shared_res_package, "warhelios_bold.ttf"), size=18
        )
        self._font_weather = ImageFont.truetype(
            open_binary(self._shared_res_package, "warhelios_bold.ttf"), size=18
        )
        self._font_score = ImageFont.truetype(
            open_binary(self._shared_res_package, "warhelios_bold.ttf"), size=23
        )

    def _get_used_ships(self):
        """
        Pre generates icon holders and gets the ship info.
        """
        si: dict[str, dict] = json.load(open_text(self._res_package, "info_ship.json"))

        for player in self._replay_data.players.values():
            ship = si[str(player.ship_params_id)]
            name = ship["name"]
            species = ship["species"]
            level = ship["level"]
            visibility_coef = ship["visibility_coef"]
            if self._dual:
                if self._as_enemy:
                    color = self._colors[1]
                else:
                    color = self._colors[0]
            else:
                color = self._colors[player.relation]

            holder = generate_holder(ship["name"], font=self._font, font_color=color)
            self._info_ships[player.vehicle_id] = self._nt_ship_info(
                name, species, level, visibility_coef, holder
            )

    def _get_used_planes(self):
        """
        Gets all the used plane in the replay.
        """
        pi: dict[str, dict] = json.load(
            open_text(self._res_package, "info_planes.json")
        )

        for states in self._replay_data.states.values():
            for plane in states.planes.values():
                info_id = str(plane.plane_params_id)
                if info_id not in self._info_planes:
                    info = pi[info_id]
                    self._info_planes[plane.plane_params_id] = self._nt_plane_info(
                        info["species"], info["ammo_type"]
                    )

    def _get_player_initial_state(self):
        """
        Gets the player's initial position and view range.
        """
        states = self._replay_data.states[next(iter(self._replay_data.states))]

        for vehicle in states.ships.values():
            if vehicle.vehicle_id == self._replay_data.match.owner_vehicle_id:
                self._player_pos_x = vehicle.x
                self._player_pos_y = vehicle.y
                self._player_view_range = self._info_ships[
                    vehicle.vehicle_id
                ].visibility_coef
                break

    def _get_cap_total_progress(self):
        """
        Get's the initial capture area maximum value.
        Cap maximum progress data provided from the replay sometimes gets noisy, get it at start instead.
        """
        states = self._replay_data.states[list(self._replay_data.states)[0]]
        for cap in states.captures:
            self._cap_total_progresses[cap.id] = cap.progress_total

    def _load_death_icons(self):
        """
        Loads the death types.
        """
        self._death_types: dict[str, dict] = {
            int(k): v
            for k, v in json.load(
                open_text(self._res_package, "info_death.json")
            ).items()
        }

    def _get_writer(self):
        """
        Return an ffmpeg writer.
        :return:
        """

        if self._benny:
            with path(self._shared_res_package, "bgm.mp3") as bgm_path:
                return write_frames(
                    path=self._temp_output_path,
                    fps=self._fps,
                    macro_block_size=self._get_macro_block(),
                    quality=self._quality,
                    size=self._img_info_panel.size,
                    pix_fmt_in="rgba",
                    audio_path=str(bgm_path.absolute()),
                    output_params=["-shortest"],
                )
        else:
            return write_frames(
                path=self._temp_output_path,
                fps=self._fps,
                macro_block_size=self._get_macro_block(),
                quality=self._quality,
                size=self._img_info_panel.size,
                pix_fmt_in="rgba",
            )

    def _get_macro_block(self) -> int:
        """
        Get the proper macro block for the imageio.get_writer
        :return:
        """

        def _get_macro_block(frame_size) -> set:
            max_macro_block = 200
            default_macro_block = 16
            nums = set()
            for i in range(1, max_macro_block + 1):
                rem = frame_size % i
                if rem == 0 and i >= default_macro_block:
                    nums.add(i)
            return nums

        a, b = map(_get_macro_block, self._img_info_panel.size)
        return min(a.intersection(b))

    ###########
    # HELPERS #
    ###########

    def _get_scaled_xy(self, x: int, y: int) -> tuple[int, int]:
        """
        Scales the xy properly.
        :param x:
        :param y:
        :return:
        """
        x = round(x * self._scaling_x + 800 / 2)
        y = round(y * self._scaling_y + 800 / 2)
        return x, y

    def _get_scaled_r(self, radius: float) -> float:
        """
        Scales the radius properly.
        :param radius:
        :return:
        """
        return radius * (self._scaling_x + self._scaling_y) / 2

    def _delete_expired(self):
        for idx in set(self._cache.keys()):
            try:
                _, it = self._cache[idx]
                if self._iterations - it >= self._cache_max_it:
                    del self._cache[idx]
            except ValueError:
                pass
