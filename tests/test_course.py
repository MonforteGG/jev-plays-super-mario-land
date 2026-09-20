from __future__ import annotations

from jev_sml.course import CourseModel, Descending, Grounded
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
