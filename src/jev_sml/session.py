from __future__ import annotations

from typing import Annotated, Literal, Protocol

from pydantic import Field

from jev_sml.course import CourseModel, Playing
from jev_sml.domain import (
    ActionId,
    Advanced,
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


class PlayedBeat(Value):
    kind: Literal["played"] = "played"
    observation: Observation
    menu: tuple[ActionId, ...]
    decision: Decision
    result: Advanced
    frames_per_decision: int

    def journal_line(self) -> dict[str, object]:
        return {
            "frame": self.observation.frame,
            "level": self.observation.level,
            "state": self.observation.model_dump(mode="json"),
            "choices": [action.value for action in self.menu],
            "jev_choice": self.decision.action.value,
            "confidence": self.decision.confidence,
            "frames_per_decision": self.frames_per_decision,
            "result": self.result.model_dump(mode="json"),
        }


class RejectedBeat(Value):
    kind: Literal["rejected"] = "rejected"
    observation: Observation
    menu: tuple[ActionId, ...]
    result: Rejected
    frames_per_decision: int

    def journal_line(self) -> dict[str, object]:
        return {
            "frame": self.observation.frame,
            "level": self.observation.level,
            "state": self.observation.model_dump(mode="json"),
            "choices": [action.value for action in self.menu],
            "jev_choice": None,
            "confidence": None,
            "frames_per_decision": self.frames_per_decision,
            "result": self.result.model_dump(mode="json"),
        }


class HaltedBeat(Value):
    kind: Literal["halted"] = "halted"
    result: Stopped
    frames_per_decision: int

    def journal_line(self) -> dict[str, object]:
        return {
            "frame": self.result.frame,
            "level": "1-1",
            "state": None,
            "choices": [],
            "jev_choice": None,
            "confidence": None,
            "frames_per_decision": self.frames_per_decision,
            "result": self.result.model_dump(mode="json"),
        }


Beat = Annotated[PlayedBeat | RejectedBeat | HaltedBeat, Field(discriminator="kind")]


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
            beat = HaltedBeat(
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
            beat = RejectedBeat(
                observation=context.observation,
                menu=tuple(context.menu),
                result=Rejected(frame=state.frame, reason=str(exc)),
                frames_per_decision=self._frames_per_decision,
            )
            self._record(beat)
            return beat

        receipt = self._game.apply(MOVES[action].recipe, self._frames_per_decision)
        self._previous_action = action
        beat = PlayedBeat(
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
            if isinstance(beat, PlayedBeat):
                decisions += 1
                final_frame = beat.result.end_frame
                continue
            if isinstance(beat, HaltedBeat):
                return RunOutcome(
                    kind=beat.result.kind,
                    decisions=decisions,
                    final_frame=beat.result.frame,
                )
            return RunOutcome(
                kind="policy_rejected",
                decisions=decisions,
                final_frame=beat.result.frame,
            )
        return RunOutcome(kind="budget_exhausted", decisions=decisions, final_frame=final_frame)

    def _record(self, beat: Beat) -> None:
        if self._telemetry is not None:
            self._telemetry.record(beat)
