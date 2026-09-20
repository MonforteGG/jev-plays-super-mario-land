from __future__ import annotations

import importlib
from pathlib import Path
from typing import Any

from jev_sml.course import RAM
from jev_sml.moves import InputRecipe, fire_tick
from jev_sml.ports import ExecutionReceipt, RawCapture


class PyBoyGame:
    def __init__(self, pyboy: Any) -> None:
        self._pyboy = pyboy
        self._wrapper = pyboy.game_wrapper

    @classmethod
    def open(
        cls,
        rom: Path,
        *,
        world: tuple[int, int] = (1, 1),
        window: bool = False,
    ) -> PyBoyGame:
        try:
            PyBoy = importlib.import_module("pyboy").PyBoy
        except ImportError as exc:
            raise RuntimeError(
                "PyBoy is required for live play; install the runtime extra"
            ) from exc
        pyboy = PyBoy(str(rom), window="SDL2" if window else "null")
        wrapper = pyboy.game_wrapper
        wrapper.game_area_mapping(wrapper.mapping_compressed, 0)
        wrapper.start_game(world_level=world)
        return cls(pyboy)

    def capture(self) -> RawCapture:
        wrapper = self._wrapper
        area = wrapper.game_area()
        return RawCapture(
            frame=int(self._pyboy.frame_count),
            ram={address: int(self._pyboy.memory[address]) for address in _RAM_ADDRESSES},
            game_area=tuple(tuple(int(cell) for cell in row) for row in area),
            wrapper_world=(int(wrapper.world[0]), int(wrapper.world[1])),
            wrapper_progress=int(wrapper.level_progress),
            wrapper_lives=int(wrapper.lives_left),
            wrapper_time_left=int(wrapper.time_left),
            wrapper_game_over=bool(wrapper.game_over()),
        )

    def apply(self, recipe: InputRecipe, frames: int) -> ExecutionReceipt:
        start = int(self._pyboy.frame_count)
        applied = []

        def fire(tick: int) -> None:
            for edge in recipe.edges:
                if fire_tick(edge.at, frames) != tick:
                    continue
                if edge.kind == "press":
                    self._pyboy.button_press(edge.button)
                else:
                    self._pyboy.button_release(edge.button)
                applied.append(edge)

        fire(0)
        for i in range(frames):
            if not self._pyboy.tick():
                raise RuntimeError("PyBoy stopped emulation")
            fire(i + 1)
        return ExecutionReceipt(
            start_frame=start,
            end_frame=int(self._pyboy.frame_count),
            applied_edges=tuple(applied),
        )

    def close(self) -> None:
        for button in ("left", "right", "a"):
            try:
                self._pyboy.button_release(button)
            except Exception:
                pass
        self._pyboy.stop()

    def __enter__(self) -> PyBoyGame:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()


_RAM_ADDRESSES = (
    RAM.mario_y,
    RAM.mario_x,
    RAM.jump_phase,
    RAM.encoded_y_speed,
    RAM.absolute_x_speed,
    RAM.directional_x_speed,
    RAM.facing,
    RAM.level_block,
    RAM.game_over,
    RAM.lives_bcd,
)
