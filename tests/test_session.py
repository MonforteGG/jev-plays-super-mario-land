from __future__ import annotations

from jev_sml import ActionId, FakeGamePort, GameSession, ReplayPolicy
from jev_sml.moves import AfterFrames, AtEnd, AtStart
from jev_sml.session import PlayedBeat


def test_replay_policy_cycle_holds_recipe_for_n_frames() -> None:
    game = FakeGamePort.from_fixture("grounded_gap_in_12_frames")
    session = GameSession(game, ReplayPolicy(["right_jump"]), frames_per_decision=16)
    beat = session.cycle()
    assert isinstance(beat, PlayedBeat)
    assert beat.result.kind == "advanced"
    assert beat.decision.action is ActionId.RIGHT_JUMP
    assert beat.result.action is ActionId.RIGHT_JUMP
    assert beat.result.end_frame - beat.result.start_frame == 16
    assert beat.frames_per_decision == 16
    assert [(edge.kind, edge.button, edge.at) for edge in game.applied_edges] == [
        ("press", "right", AtStart()),
        ("press", "a", AtStart()),
        ("release", "a", AfterFrames(10)),
        ("release", "right", AtEnd()),
    ]
    assert game.applied_edges[-1].kind == "release"
