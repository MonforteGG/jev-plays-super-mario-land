from __future__ import annotations

import pytest
from pydantic import TypeAdapter, ValidationError

from jev_sml import ActionId, FakeGamePort, GameSession
from jev_sml.course import MarioState
from jev_sml.domain import AirState, Ascending, Descending, Grounded
from jev_sml.moves import legal_menu


def test_grounded_and_descending_cannot_both_exist() -> None:
    adapter = TypeAdapter(AirState)
    grounded = adapter.validate_python({"kind": "grounded"})
    descending = adapter.validate_python({"kind": "descending", "encoded_y_speed": 6})
    assert grounded.kind == "grounded"
    assert descending.kind == "descending"
    with pytest.raises(ValidationError):
        adapter.validate_python({"kind": "grounded", "encoded_y_speed": 6})
    mario = MarioState(
        air=Grounded(),
        screen_x=40,
        screen_y=112,
        horizontal_speed_code=2,
        facing="right",
    )
    assert mario.air.kind == "grounded"
    assert not isinstance(mario.air, Descending)


def test_jump_is_absent_from_menu_while_airborne() -> None:
    for air in (Ascending(encoded_y_speed=8), Descending(encoded_y_speed=8)):
        menu = legal_menu(air)
        assert list(menu) == [ActionId.NOOP, ActionId.RIGHT, ActionId.LEFT]
        assert ActionId.JUMP not in menu
        assert ActionId.RIGHT_JUMP not in menu


def test_cycle_does_not_call_policy_when_course_is_terminal() -> None:
    class ForbiddenPolicy:
        def choose(self, context: object) -> None:
            raise AssertionError("policy must not run on a terminal course")

    for name, kind in (
        ("dead", "dead"),
        ("game_over", "game_over"),
        ("level_cleared", "level_cleared"),
    ):
        beat = GameSession(FakeGamePort.from_fixture(name), ForbiddenPolicy()).cycle()
        assert beat.result.kind == kind
        assert beat.decision is None
