from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Annotated, Literal

from pydantic import Field

from jev_sml.domain import (
    ActionId,
    AirState,
    Ascending,
    DecisionContext,
    Descending,
    EnemyThreat,
    GapThreat,
    Grounded,
    Observation,
    ObstacleThreat,
    Value,
)
from jev_sml.moves import legal_menu
from jev_sml.ports import RawCapture

TILE_PX = 8
HUD_TILE_ROWS = 2
MARIO_HEIGHT_PX = 16
GAME_OVER_CODE = 0x39
FACING_RIGHT = 0x00
FACING_LEFT = 0x20
JUMP_ASCENDING = 1
JUMP_DESCENDING = 2
JUMP_NONE = 0
AREA_COLS = 20

COMPRESSED_MARIO = frozenset({1})
COMPRESSED_SOLID = frozenset({10, 11, 12, 13, 14})
COMPRESSED_ENEMY = {
    15: "goomba",
    16: "koopa",
    17: "plant",
    18: "moth",
    19: "flying_moth",
    20: "sphinx",
    21: "big_sphinx",
    22: "fist",
    23: "bill",
    24: "projectile",
    25: "shell",
    26: "explosion",
    27: "spike",
}


@dataclass(frozen=True, slots=True)
class SmlRamMap:
    mario_y: int = 0xC201
    mario_x: int = 0xC202
    jump_phase: int = 0xC207
    encoded_y_speed: int = 0xC208
    absolute_x_speed: int = 0xC20C
    directional_x_speed: int = 0xC20E
    facing: int = 0xC205
    level_block: int = 0xC0AB
    game_over: int = 0xC0A4
    lives_bcd: int = 0xDA15


RAM = SmlRamMap()


class ColumnSlice(Value):
    x_tiles: int
    distance_px: int = Field(ge=0)
    ground: bool
    enemy_kind: str | None = None
    obstacle_height_tiles: int = Field(ge=0)


class NearbyCourse(Value):
    columns: tuple[ColumnSlice, ...]


class MarioState(Value):
    air: AirState
    screen_x: int
    screen_y: int
    horizontal_speed_code: int
    facing: Literal["left", "right"]


class Playing(Value):
    kind: Literal["playing"] = "playing"
    frame: int
    progress_px: int
    mario: MarioState
    nearby: NearbyCourse
    lives: int
    time_left: int


class Dead(Value):
    kind: Literal["dead"] = "dead"
    frame: int
    lives: int = Field(ge=0)


class GameOver(Value):
    kind: Literal["game_over"] = "game_over"
    frame: int


class LevelCleared(Value):
    kind: Literal["level_cleared"] = "level_cleared"
    frame: int


CourseState = Annotated[Playing | Dead | GameOver | LevelCleared, Field(discriminator="kind")]


class ParseError(ValueError):
    pass


def _u8(ram: Mapping[int, int] | bytes, address: int) -> int:
    try:
        if isinstance(ram, Mapping):
            return int(ram[address])
        return ram[address]
    except (KeyError, IndexError) as exc:
        raise ParseError(f"missing RAM byte at {address:#x}") from exc


def _tile_col(screen_x: int) -> int:
    return screen_x // TILE_PX


def _row_under_mario(screen_y: int) -> int:
    return (screen_y + MARIO_HEIGHT_PX) // TILE_PX - HUD_TILE_ROWS


def _cell(area: tuple[tuple[int, ...], ...], row: int, col: int) -> int:
    if row < 0 or col < 0 or row >= len(area) or col >= len(area[row]):
        return 0
    return int(area[row][col])


def _solid(tile: int) -> bool:
    return tile in COMPRESSED_SOLID


def _enemy_kind(tile: int) -> str | None:
    return COMPRESSED_ENEMY.get(tile)


def _obstacle_height(area: tuple[tuple[int, ...], ...], col: int, ground_row: int) -> int:
    height = 0
    row = ground_row - 1
    while row >= 0 and _solid(_cell(area, row, col)):
        height += 1
        row -= 1
    return height


def _tiles_under_are_solid(area: tuple[tuple[int, ...], ...], screen_x: int, screen_y: int) -> bool:
    row = _row_under_mario(screen_y)
    col = _tile_col(screen_x)
    return _solid(_cell(area, row, col)) or _solid(_cell(area, row, col + 1))


def _mario_present(area: tuple[tuple[int, ...], ...]) -> bool:
    return any(tile in COMPRESSED_MARIO for row in area for tile in row)


def _frames_until(distance_px: int, speed: int) -> int | None:
    if speed <= 0:
        return None
    return (distance_px + speed - 1) // speed


def _scan_nearby(
    area: tuple[tuple[int, ...], ...],
    screen_x: int,
    screen_y: int,
) -> NearbyCourse:
    mario_col = _tile_col(screen_x)
    ground_row = _row_under_mario(screen_y)
    columns: list[ColumnSlice] = []
    for col in range(mario_col, AREA_COLS):
        distance_px = max(0, col * TILE_PX - screen_x)
        enemy = None
        for row in range(len(area)):
            kind = _enemy_kind(_cell(area, row, col))
            if kind is not None:
                enemy = kind
                break
        columns.append(
            ColumnSlice(
                x_tiles=col,
                distance_px=distance_px,
                ground=_solid(_cell(area, ground_row, col)),
                enemy_kind=enemy,
                obstacle_height_tiles=_obstacle_height(area, col, ground_row),
            )
        )
    return NearbyCourse(columns=tuple(columns))


def _nearest_enemy(nearby: NearbyCourse, speed: int) -> EnemyThreat | None:
    for column in nearby.columns:
        if column.enemy_kind is None:
            continue
        return EnemyThreat(
            enemy_kind=column.enemy_kind,
            distance_px=column.distance_px,
            frames_until=_frames_until(column.distance_px, speed),
        )
    return None


def _nearest_gap(nearby: NearbyCourse, speed: int) -> GapThreat | None:
    start: ColumnSlice | None = None
    width_tiles = 0
    for column in nearby.columns:
        if column.ground:
            if start is not None:
                break
            continue
        if start is None:
            start = column
        width_tiles += 1
    if start is None or width_tiles == 0:
        return None
    return GapThreat(
        distance_px=start.distance_px,
        width_px=width_tiles * TILE_PX,
        frames_until=_frames_until(start.distance_px, speed),
    )


def _nearest_obstacle(nearby: NearbyCourse, speed: int) -> ObstacleThreat | None:
    for column in nearby.columns:
        if column.obstacle_height_tiles <= 0:
            continue
        return ObstacleThreat(
            distance_px=column.distance_px,
            height_tiles=column.obstacle_height_tiles,
            frames_until=_frames_until(column.distance_px, speed),
        )
    return None


class CourseModel:
    def read(self, capture: RawCapture) -> CourseState:
        if capture.wrapper_game_over or _u8(capture.ram, RAM.game_over) == GAME_OVER_CODE:
            return GameOver(frame=capture.frame)
        if capture.wrapper_world != (1, 1):
            return LevelCleared(frame=capture.frame)
        if not _mario_present(capture.game_area):
            return Dead(frame=capture.frame, lives=max(0, capture.wrapper_lives))

        screen_x = _u8(capture.ram, RAM.mario_x)
        screen_y = _u8(capture.ram, RAM.mario_y)
        jump_phase = _u8(capture.ram, RAM.jump_phase)
        y_speed = _u8(capture.ram, RAM.encoded_y_speed)
        speed = _u8(capture.ram, RAM.absolute_x_speed)
        facing_code = _u8(capture.ram, RAM.facing)
        if facing_code == FACING_RIGHT:
            facing: Literal["left", "right"] = "right"
        elif facing_code == FACING_LEFT:
            facing = "left"
        else:
            raise ParseError(f"unknown facing {facing_code:#x}")

        if jump_phase == JUMP_ASCENDING:
            air: AirState = Ascending(encoded_y_speed=y_speed)
        elif jump_phase == JUMP_DESCENDING:
            air = Descending(encoded_y_speed=y_speed)
        elif jump_phase == JUMP_NONE:
            if _tiles_under_are_solid(capture.game_area, screen_x, screen_y):
                air = Grounded()
            else:
                air = Descending(encoded_y_speed=y_speed)
        else:
            raise ParseError(f"unknown jump_phase {jump_phase}")

        return Playing(
            frame=capture.frame,
            progress_px=capture.wrapper_progress,
            mario=MarioState(
                air=air,
                screen_x=screen_x,
                screen_y=screen_y,
                horizontal_speed_code=speed,
                facing=facing,
            ),
            nearby=_scan_nearby(capture.game_area, screen_x, screen_y),
            lives=capture.wrapper_lives,
            time_left=capture.wrapper_time_left,
        )

    def decision_context(
        self,
        state: Playing,
        *,
        previous_action: ActionId | None,
        frames: int,
    ) -> DecisionContext:
        speed = state.mario.horizontal_speed_code
        return DecisionContext(
            observation=Observation(
                frame=state.frame,
                level="1-1",
                progress_px=state.progress_px,
                air=state.mario.air,
                horizontal_speed_code=speed,
                facing=state.mario.facing,
                enemy=_nearest_enemy(state.nearby, speed),
                gap=_nearest_gap(state.nearby, speed),
                obstacle=_nearest_obstacle(state.nearby, speed),
                previous_action=previous_action,
                decision_window_frames=frames,
            ),
            menu=legal_menu(state.mario.air),
        )
