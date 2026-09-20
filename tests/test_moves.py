from __future__ import annotations

from jev_sml.domain import ActionId
from jev_sml.moves import MOVES, AfterFrames, AtEnd, AtStart
from jev_sml.testing import FakeGamePort


def test_right_jump_presses_right_and_a_releases_a_after_10_and_right_at_end() -> None:
    recipe = MOVES[ActionId.RIGHT_JUMP].recipe
    game = FakeGamePort.from_fixture("grounded")
    receipt = game.apply(recipe, 16)
    assert [(edge.kind, edge.button) for edge in receipt.applied_edges] == [
        ("press", "right"),
        ("press", "a"),
        ("release", "a"),
        ("release", "right"),
    ]
    assert receipt.applied_edges[0].at == AtStart()
    assert receipt.applied_edges[1].at == AtStart()
    assert receipt.applied_edges[2].at == AfterFrames(10)
    assert receipt.applied_edges[3].at == AtEnd()
    assert receipt.end_frame - receipt.start_frame == 16
