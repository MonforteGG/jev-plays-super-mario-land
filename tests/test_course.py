from __future__ import annotations

from jev_sml.course import CourseModel, Descending, Grounded
from jev_sml.ports import RawCapture
from jev_sml.testing import fixture_capture


def test_jump_phase_zero_with_empty_tiles_under_mario_is_descending() -> None:
    capture = fixture_capture("walk_off")
    assert capture.ram[0xC207] == 0
    state = CourseModel().read(capture)
    assert state.kind == "playing"
    assert isinstance(state.mario.air, Descending)


def test_jump_phase_zero_with_solid_tiles_under_mario_is_grounded() -> None:
    state = CourseModel().read(fixture_capture("grounded"))
    assert state.kind == "playing"
    assert isinstance(state.mario.air, Grounded)


def test_gap_in_12_frames_fixture_reports_gap() -> None:
    state = CourseModel().read(fixture_capture("grounded_gap_in_12_frames"))
    assert state.kind == "playing"
    context = CourseModel().decision_context(state, previous_action=None, frames=16)
    assert context.observation.gap is not None
    assert context.observation.gap.frames_until == 12


def test_plane_tiles_without_mario_are_dead() -> None:
    capture = fixture_capture("dead")
    area = [list(row) for row in capture.game_area]
    area[8][8] = 2
    state = CourseModel().read(
        RawCapture(
            frame=capture.frame,
            ram=capture.ram,
            game_area=tuple(tuple(row) for row in area),
            wrapper_world=capture.wrapper_world,
            wrapper_progress=capture.wrapper_progress,
            wrapper_lives=capture.wrapper_lives,
            wrapper_time_left=capture.wrapper_time_left,
            wrapper_game_over=capture.wrapper_game_over,
        )
    )
    assert state.kind == "dead"
