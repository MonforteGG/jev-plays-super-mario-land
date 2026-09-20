from __future__ import annotations

from collections.abc import Sequence
from dataclasses import replace

from jev_sml.course import AREA_COLS, RAM, TILE_PX
from jev_sml.domain import ActionId, Decision, DecisionContext, DecisionError
from jev_sml.moves import InputEdge, InputRecipe, fire_tick
from jev_sml.ports import ExecutionReceipt, RawCapture

AREA_ROWS = 16
SOLID = 10
MARIO = 1
DEFAULT_MARIO_X = 40
DEFAULT_MARIO_Y = 112


def _empty_area() -> list[list[int]]:
    return [[0 for _ in range(AREA_COLS)] for _ in range(AREA_ROWS)]


def _place_mario(area: list[list[int]], screen_x: int, screen_y: int) -> None:
    col = screen_x // TILE_PX
    top = screen_y // TILE_PX - 2
    for row in (top, top + 1):
        for offset in (0, 1):
            if 0 <= row < AREA_ROWS and 0 <= col + offset < AREA_COLS:
                area[row][col + offset] = MARIO


def _freeze_area(area: list[list[int]]) -> tuple[tuple[int, ...], ...]:
    return tuple(tuple(row) for row in area)


def _ram(
    *,
    jump_phase: int,
    mario_x: int,
    mario_y: int,
    y_speed: int = 0,
    abs_x_speed: int = 2,
    facing: int = 0x00,
    game_over: int = 0,
) -> dict[int, int]:
    return {
        RAM.mario_y: mario_y,
        RAM.mario_x: mario_x,
        RAM.jump_phase: jump_phase,
        RAM.encoded_y_speed: y_speed,
        RAM.absolute_x_speed: abs_x_speed,
        RAM.directional_x_speed: abs_x_speed,
        RAM.facing: facing,
        RAM.level_block: 0,
        RAM.game_over: game_over,
        RAM.lives_bcd: 0x02,
    }


def _capture(
    *,
    frame: int = 0,
    jump_phase: int = 0,
    mario_x: int = DEFAULT_MARIO_X,
    mario_y: int = DEFAULT_MARIO_Y,
    abs_x_speed: int = 2,
    y_speed: int = 0,
    world: tuple[int, int] = (1, 1),
    progress: int = 251,
    lives: int = 2,
    time_left: int = 400,
    game_over: bool = False,
    game_over_ram: int = 0,
    area: list[list[int]] | None = None,
    place_mario: bool = True,
) -> RawCapture:
    grid = area if area is not None else _empty_area()
    if place_mario:
        _place_mario(grid, mario_x, mario_y)
    return RawCapture(
        frame=frame,
        ram=_ram(
            jump_phase=jump_phase,
            mario_x=mario_x,
            mario_y=mario_y,
            y_speed=y_speed,
            abs_x_speed=abs_x_speed,
            game_over=game_over_ram,
        ),
        game_area=_freeze_area(grid),
        wrapper_world=world,
        wrapper_progress=progress,
        wrapper_lives=lives,
        wrapper_time_left=time_left,
        wrapper_game_over=game_over,
    )


def _grounded_area(*, gap_cols: frozenset[int] | None = None) -> list[list[int]]:
    area = _empty_area()
    holes = gap_cols or frozenset()
    for col in range(AREA_COLS):
        if col in holes:
            continue
        area[14][col] = SOLID
        area[15][col] = SOLID
    return area


def fixture_capture(name: str) -> RawCapture:
    if name == "grounded_gap_in_12_frames":
        return _capture(area=_grounded_area(gap_cols=frozenset({8, 9, 10})))
    if name == "grounded":
        return _capture(area=_grounded_area())
    if name == "walk_off":
        return _capture(area=_empty_area())
    if name == "airborne":
        return _capture(jump_phase=1, y_speed=12, area=_grounded_area())
    if name == "dead":
        return _capture(place_mario=False, lives=1, area=_empty_area())
    if name == "game_over":
        return _capture(game_over=True, game_over_ram=0x39, place_mario=False)
    if name == "level_cleared":
        return _capture(world=(1, 2), area=_grounded_area())
    raise KeyError(name)


class FakeGamePort:
    def __init__(self, captures: Sequence[RawCapture]) -> None:
        if not captures:
            raise ValueError("FakeGamePort needs at least one capture")
        self._captures = list(captures)
        self._index = 0
        self.applied_edges: list[InputEdge] = []

    @classmethod
    def from_fixture(cls, name: str) -> FakeGamePort:
        return cls([fixture_capture(name)])

    def capture(self) -> RawCapture:
        return self._captures[self._index]

    def apply(self, recipe: InputRecipe, frames: int) -> ExecutionReceipt:
        start = self._captures[self._index].frame
        applied: list[InputEdge] = []

        def fire(tick: int) -> None:
            for edge in recipe.edges:
                if fire_tick(edge.at, frames) == tick:
                    applied.append(edge)
                    self.applied_edges.append(edge)

        fire(0)
        current = self._captures[self._index]
        for i in range(frames):
            current = replace(current, frame=current.frame + 1)
            fire(i + 1)
        if self._index + 1 < len(self._captures):
            self._index += 1
        else:
            self._captures[self._index] = current
        return ExecutionReceipt(
            start_frame=start, end_frame=start + frames, applied_edges=tuple(applied)
        )


class ReplayPolicy:
    def __init__(self, actions: Sequence[ActionId | str]) -> None:
        self._actions = [ActionId(action) for action in actions]
        self._index = 0

    def choose(self, context: DecisionContext) -> Decision:
        if self._index >= len(self._actions):
            raise DecisionError("replay policy is exhausted")
        action = context.menu.require(self._actions[self._index])
        self._index += 1
        return Decision(action=action)
