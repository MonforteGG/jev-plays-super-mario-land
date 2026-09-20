from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal

from jev_sml.domain import ActionId, ActionMenu, AirState, Grounded, Requirement, Value

JUMP_A_FRAMES = 10


@dataclass(frozen=True, slots=True)
class AtStart:
    kind: Literal["start"] = "start"


@dataclass(frozen=True, slots=True)
class AtEnd:
    kind: Literal["end"] = "end"


@dataclass(frozen=True, slots=True)
class AfterFrames:
    frames: int
    kind: Literal["after_frames"] = "after_frames"


EdgeTime = AtStart | AtEnd | AfterFrames


@dataclass(frozen=True, slots=True)
class InputEdge:
    kind: Literal["press", "release"]
    button: Literal["left", "right", "a"]
    at: EdgeTime


@dataclass(frozen=True, slots=True)
class InputRecipe:
    edges: tuple[InputEdge, ...]


class Move(Value):
    action: ActionId
    criterion: str
    requires: frozenset[Requirement]
    recipe: InputRecipe


MOVES: Mapping[ActionId, Move] = {
    ActionId.NOOP: Move(
        action=ActionId.NOOP,
        criterion="Wait in place.",
        requires=frozenset(),
        recipe=InputRecipe(edges=()),
    ),
    ActionId.RIGHT: Move(
        action=ActionId.RIGHT,
        criterion="Walk right.",
        requires=frozenset(),
        recipe=InputRecipe(
            edges=(
                InputEdge(kind="press", button="right", at=AtStart()),
                InputEdge(kind="release", button="right", at=AtEnd()),
            )
        ),
    ),
    ActionId.LEFT: Move(
        action=ActionId.LEFT,
        criterion="Walk left.",
        requires=frozenset(),
        recipe=InputRecipe(
            edges=(
                InputEdge(kind="press", button="left", at=AtStart()),
                InputEdge(kind="release", button="left", at=AtEnd()),
            )
        ),
    ),
    ActionId.JUMP: Move(
        action=ActionId.JUMP,
        criterion="Jump in place. Use to clear a nearby enemy or obstacle.",
        requires=frozenset({Requirement.ON_GROUND}),
        recipe=InputRecipe(
            edges=(
                InputEdge(kind="press", button="a", at=AtStart()),
                InputEdge(kind="release", button="a", at=AfterFrames(JUMP_A_FRAMES)),
            )
        ),
    ),
    ActionId.RIGHT_JUMP: Move(
        action=ActionId.RIGHT_JUMP,
        criterion="Jump while moving right. Use to clear a gap, enemy, or pipe ahead.",
        requires=frozenset({Requirement.ON_GROUND}),
        recipe=InputRecipe(
            edges=(
                InputEdge(kind="press", button="right", at=AtStart()),
                InputEdge(kind="press", button="a", at=AtStart()),
                InputEdge(kind="release", button="a", at=AfterFrames(JUMP_A_FRAMES)),
                InputEdge(kind="release", button="right", at=AtEnd()),
            )
        ),
    ),
}

if set(MOVES) != set(ActionId):
    raise RuntimeError("MOVES must contain exactly one row per ActionId")


def fire_tick(at: EdgeTime, frames: int) -> int:
    if isinstance(at, AtStart):
        return 0
    if isinstance(at, AfterFrames):
        return min(at.frames, frames)
    return frames


def legal_menu(air: AirState) -> ActionMenu:
    chosen: list[ActionId] = []
    for action in ActionId:
        required = MOVES[action].requires
        if Requirement.ON_GROUND in required and not isinstance(air, Grounded):
            continue
        chosen.append(action)
    return ActionMenu(menu_id="mvp1", first=chosen[0], rest=tuple(chosen[1:]))
