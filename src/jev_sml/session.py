from __future__ import annotations

from typing import Protocol

from jev_sml.course import CourseModel, Playing
from jev_sml.domain import (
    ActionId,
    Advanced,
    CycleResult,
    Decision,
    DecisionError,
    DecisionPolicy,
    Observation,
    Rejected,
    RunOutcome,
    Stopped,
    Value,
)
from jev_sml.moves import MOVES
from jev_sml.ports import GamePort


class Beat(Value):
    observation: Observation | None
    menu: tuple[ActionId, ...]
    decision: Decision | None
    result: CycleResult
    frames_per_decision: int

    def journal_line(self) -> dict[str, object]:
        frame = (
            self.observation.frame if self.observation is not None else _result_frame(self.result)
        )
        return {
            "frame": frame,
            "level": "1-1" if self.observation is None else self.observation.level,
            "state": None if self.observation is None else self.observation.model_dump(mode="json"),
            "choices": [action.value for action in self.menu],
            "jev_choice": None if self.decision is None else self.decision.action.value,
            "confidence": None if self.decision is None else self.decision.confidence,
            "frames_per_decision": self.frames_per_decision,
            "result": self.result.model_dump(mode="json"),
        }


def _result_frame(result: CycleResult) -> int:
    if isinstance(result, Advanced):
        return result.end_frame
    return result.frame


class TelemetrySink(Protocol):
    def record(self, beat: Beat) -> None: ...


class GameSession:
    def __init__(
        self,
        game: GamePort,
        policy: DecisionPolicy,
        *,
        frames_per_decision: int = 16,
        telemetry: TelemetrySink | None = None,
        course: CourseModel | None = None,
    ) -> None:
        if frames_per_decision < 1:
            raise ValueError("frames_per_decision must be positive")
        self._game = game
        self._policy = policy
        self._frames_per_decision = frames_per_decision
        self._telemetry = telemetry
        self._course = course or CourseModel()
        self._previous_action: ActionId | None = None

    def cycle(self) -> Beat:
        capture = self._game.capture()
        state = self._course.read(capture)
        if not isinstance(state, Playing):
            beat = Beat(
                observation=None,
                menu=(),
                decision=None,
                result=Stopped(kind=state.kind, frame=state.frame),
                frames_per_decision=self._frames_per_decision,
            )
            self._record(beat)
            return beat

        context = self._course.decision_context(
            state,
            previous_action=self._previous_action,
            frames=self._frames_per_decision,
        )
        try:
            decision = self._policy.choose(context)
            action = context.menu.require(decision.action)
        except DecisionError as exc:
            beat = Beat(
                observation=context.observation,
                menu=tuple(context.menu),
                decision=None,
                result=Rejected(frame=state.frame, reason=str(exc)),
                frames_per_decision=self._frames_per_decision,
            )
            self._record(beat)
            return beat

        receipt = self._game.apply(MOVES[action].recipe, self._frames_per_decision)
        self._previous_action = action
        beat = Beat(
            observation=context.observation,
            menu=tuple(context.menu),
            decision=decision,
            result=Advanced(
                action=action,
                start_frame=receipt.start_frame,
                end_frame=receipt.end_frame,
                confidence=decision.confidence,
            ),
            frames_per_decision=self._frames_per_decision,
        )
        self._record(beat)
        return beat

    def run(self, *, max_decisions: int | None = None) -> RunOutcome:
        decisions = 0
        final_frame = 0
        while max_decisions is None or decisions < max_decisions:
            beat = self.cycle()
            result = beat.result
            if isinstance(result, Advanced):
                decisions += 1
                final_frame = result.end_frame
                continue
            if isinstance(result, Stopped):
                return RunOutcome(kind=result.kind, decisions=decisions, final_frame=result.frame)
            return RunOutcome(kind="policy_rejected", decisions=decisions, final_frame=result.frame)
        return RunOutcome(kind="budget_exhausted", decisions=decisions, final_frame=final_frame)

    def _record(self, beat: Beat) -> None:
        if self._telemetry is not None:
            self._telemetry.record(beat)
