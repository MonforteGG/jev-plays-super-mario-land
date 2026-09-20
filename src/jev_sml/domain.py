from __future__ import annotations

from collections.abc import Iterator, Mapping
from enum import StrEnum
from typing import Annotated, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field


class DecisionError(RuntimeError):
    pass


class Value(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class ActionId(StrEnum):
    NOOP = "noop"
    RIGHT = "right"
    LEFT = "left"
    JUMP = "jump"
    RIGHT_JUMP = "right_jump"


class Requirement(StrEnum):
    ON_GROUND = "on_ground"


class Grounded(Value):
    kind: Literal["grounded"] = "grounded"


class Ascending(Value):
    kind: Literal["ascending"] = "ascending"
    encoded_y_speed: int


class Descending(Value):
    kind: Literal["descending"] = "descending"
    encoded_y_speed: int


AirState = Annotated[Grounded | Ascending | Descending, Field(discriminator="kind")]


class EnemyThreat(Value):
    kind: Literal["enemy"] = "enemy"
    enemy_kind: str
    distance_px: int = Field(ge=0)
    frames_until: int | None = Field(default=None, ge=0)


class GapThreat(Value):
    kind: Literal["gap"] = "gap"
    distance_px: int = Field(ge=0)
    width_px: int = Field(gt=0)
    frames_until: int | None = Field(default=None, ge=0)


class ObstacleThreat(Value):
    kind: Literal["obstacle"] = "obstacle"
    distance_px: int = Field(ge=0)
    height_tiles: int = Field(gt=0)
    frames_until: int | None = Field(default=None, ge=0)


class Observation(Value):
    frame: int = Field(ge=0)
    level: Literal["1-1"]
    progress_px: int = Field(ge=0)
    air: AirState
    horizontal_speed_code: int
    facing: Literal["left", "right"]
    enemy: EnemyThreat | None
    gap: GapThreat | None
    obstacle: ObstacleThreat | None
    previous_action: ActionId | None
    decision_window_frames: int = Field(gt=0, le=60)


class ActionMenu(Value):
    menu_id: str
    first: ActionId
    rest: tuple[ActionId, ...] = ()

    def __iter__(self) -> Iterator[ActionId]:
        yield self.first
        yield from self.rest

    def __contains__(self, action: object) -> bool:
        return action == self.first or action in self.rest

    def require(self, action: ActionId) -> ActionId:
        if action not in self:
            raise DecisionError(f"action {action} is not in the current menu")
        return action

    def criteria(self) -> Mapping[str, str]:
        from jev_sml.moves import MOVES

        return {action.value: MOVES[action].criterion for action in self}


class DecisionContext(Value):
    observation: Observation
    menu: ActionMenu


class Decision(Value):
    action: ActionId
    confidence: float | None = Field(default=None, ge=0, le=1)
    probabilities: Mapping[ActionId, float] | None = None
    provider_model: str | None = None
    latency_ms: float | None = Field(default=None, ge=0)


class DecisionPolicy(Protocol):
    def choose(self, context: DecisionContext) -> Decision: ...


class Advanced(Value):
    kind: Literal["advanced"] = "advanced"
    action: ActionId
    start_frame: int
    end_frame: int
    confidence: float | None


class Stopped(Value):
    kind: Literal["dead", "game_over", "level_cleared"]
    frame: int


class Rejected(Value):
    kind: Literal["policy_rejected"] = "policy_rejected"
    frame: int
    reason: str


CycleResult = Annotated[Advanced | Stopped | Rejected, Field(discriminator="kind")]


class RunOutcome(Value):
    kind: Literal["level_cleared", "dead", "game_over", "budget_exhausted", "policy_rejected"]
    decisions: int = Field(ge=0)
    final_frame: int = Field(ge=0)
