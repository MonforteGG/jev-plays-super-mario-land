from __future__ import annotations

import sys
import types

import pytest

from jev_sml.course import CourseModel
from jev_sml.domain import ActionId, DecisionError, Grounded
from jev_sml.moves import legal_menu
from jev_sml.policy import JevPolicy
from jev_sml.testing import fixture_capture


def _menu():
    return legal_menu(Grounded())


def _answer(choice: str, probabilities: dict[str, float], confidence: float = 1.0) -> dict:
    return {"choice": choice, "probabilities": probabilities, "confidence": confidence}


def test_jev_policy_rejects_unknown_id() -> None:
    menu = _menu()
    with pytest.raises(DecisionError, match="unknown action"):
        JevPolicy._validate_answer(
            _answer("spin", {action.value: 1.0 / 5 for action in menu}),
            menu,
            1.0,
            {"model": "test"},
        )


def test_jev_policy_rejects_probability_key_mismatch() -> None:
    with pytest.raises(DecisionError, match="do not match"):
        JevPolicy._validate_answer(
            _answer("right_jump", {"right_jump": 1.0}),
            _menu(),
            1.0,
            {"model": "test"},
        )


def test_jev_policy_rejects_probability_sum() -> None:
    menu = _menu()
    keys = [action.value for action in menu]
    probs = {key: 0.1 for key in keys}
    with pytest.raises(DecisionError, match="do not sum"):
        JevPolicy._validate_answer(_answer("right", probs), menu, 1.0, {"model": "test"})


def test_jev_policy_accepts_stub_client(monkeypatch: pytest.MonkeyPatch) -> None:
    menu = _menu()
    probs = {action.value: 0.0 for action in menu}
    probs["right_jump"] = 1.0

    class FakeChoice:
        def __init__(self, **kwargs: object) -> None:
            self.kwargs = kwargs

    class FakeClient:
        def system_one(self, *, state: object, questions: object) -> dict:
            return {
                "model": "jev-1.13.0",
                "answers": {
                    "next_action": _answer("right_jump", probs),
                },
            }

    monkeypatch.setitem(sys.modules, "typesafe_sdk", types.SimpleNamespace(Choice=FakeChoice))
    context = CourseModel().decision_context(
        CourseModel().read(fixture_capture("grounded")),
        previous_action=None,
        frames=16,
    )
    decision = JevPolicy(client=FakeClient()).choose(context)
    assert decision.action is ActionId.RIGHT_JUMP
    assert decision.provider_model == "jev-1.13.0"
    assert decision.probabilities[ActionId.RIGHT_JUMP] == 1.0
