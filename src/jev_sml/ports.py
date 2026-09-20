from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Protocol

from jev_sml.moves import InputEdge, InputRecipe


@dataclass(frozen=True, slots=True)
class RawCapture:
    frame: int
    ram: Mapping[int, int] | bytes
    game_area: tuple[tuple[int, ...], ...]
    wrapper_world: tuple[int, int]
    wrapper_progress: int
    wrapper_lives: int
    wrapper_time_left: int
    wrapper_game_over: bool


@dataclass(frozen=True, slots=True)
class ExecutionReceipt:
    start_frame: int
    end_frame: int
    applied_edges: tuple[InputEdge, ...]


class GamePort(Protocol):
    def capture(self) -> RawCapture: ...

    def apply(self, recipe: InputRecipe, frames: int) -> ExecutionReceipt: ...
