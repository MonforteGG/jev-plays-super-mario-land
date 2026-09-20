from __future__ import annotations

import importlib
import time
from collections.abc import Mapping
from typing import Any, Literal

from jev_sml.domain import (
    ActionId,
    ActionMenu,
    Decision,
    DecisionContext,
    DecisionError,
)

JEV_MODEL: Literal["jev-1.13.0"] = "jev-1.13.0"
INSTRUCTIONS = (
    "Choose exactly one supplied action ID that best advances World 1-1 as small Mario "
    "using the current structured game state. Do not invent an ID. "
    "Prefer surviving and moving right. Jump to clear enemies, gaps, or obstacles."
)


class JevPolicy:
    def __init__(
        self,
        *,
        model: Literal["jev-1.13.0"] = JEV_MODEL,
        timeout: float = 10.0,
        max_retries: int = 2,
        retry_budget: float = 30.0,
        client: Any | None = None,
    ) -> None:
        self.model = model
        self._client = client
        self._owns_client = client is None
        self._timeout = timeout
        self._max_retries = max_retries
        self._retry_budget = retry_budget

    def _ensure_client(self) -> Any:
        if self._client is None:
            try:
                sdk = importlib.import_module("typesafe_sdk")
            except ImportError as exc:
                raise DecisionError(
                    "typesafe-sdk is required for live Jev decisions; install the runtime extra"
                ) from exc
            self._client = sdk.TypeSafeClient(
                model=self.model,
                timeout=self._timeout,
                retry=sdk.RetryPolicy(max_retries=self._max_retries, timeout=self._retry_budget),
            )
        return self._client

    def choose(self, context: DecisionContext) -> Decision:
        options = list(context.menu)
        if not options:
            raise DecisionError("cannot ask Jev to choose from an empty action set")
        if len(options) > 255:
            raise DecisionError("Jev Choice supports at most 255 options; use explicit hierarchy")
        try:
            Choice = importlib.import_module("typesafe_sdk").Choice
        except ImportError as exc:
            raise DecisionError("typesafe-sdk is required for live Jev decisions") from exc
        started = time.perf_counter()
        response = self._ensure_client().system_one(
            state=context.observation.model_dump(mode="json"),
            questions={
                "next_action": Choice(
                    instructions=INSTRUCTIONS,
                    criteria=context.menu.criteria(),
                )
            },
        )
        latency_ms = (time.perf_counter() - started) * 1000
        answer = self._answer(response)
        return self._validate_answer(answer, context.menu, latency_ms, response)

    @staticmethod
    def _answer(response: Any) -> Any:
        if hasattr(response, "choices"):
            choices = response.choices
            if isinstance(choices, Mapping) and "next_action" in choices:
                return choices["next_action"]
        if hasattr(response, "answers"):
            answers = response.answers
            if isinstance(answers, Mapping) and "next_action" in answers:
                return answers["next_action"]
        if isinstance(response, Mapping):
            answers = response.get("answers", response)
            if isinstance(answers, Mapping):
                return answers.get("next_action", answers)
        raise DecisionError("Jev response did not contain answers.next_action")

    @classmethod
    def _validate_answer(
        cls,
        answer: Any,
        menu: ActionMenu,
        latency_ms: float,
        response: Any,
    ) -> Decision:
        def get(name: str, default: Any = None) -> Any:
            if isinstance(answer, Mapping):
                return answer.get(name, default)
            return getattr(answer, name, default)

        option_id = get("choice")
        legal = {action.value for action in menu}
        if not isinstance(option_id, str) or option_id not in legal:
            raise DecisionError(f"Jev selected unknown action ID {option_id!r}")
        probabilities = get("probabilities", {})
        if not isinstance(probabilities, Mapping):
            raise DecisionError("Jev probabilities are not a mapping")
        probabilities = {str(key): float(value) for key, value in probabilities.items()}
        if set(probabilities) != legal:
            raise DecisionError("Jev probabilities do not match the current action set")
        if any(value < 0 or value > 1 for value in probabilities.values()):
            raise DecisionError("Jev probability is outside [0, 1]")
        if abs(sum(probabilities.values()) - 1.0) > 1e-4:
            raise DecisionError("Jev probabilities do not sum to one")
        confidence = get("confidence")
        confidence = float(confidence) if confidence is not None else None
        provider_model = getattr(response, "model", None)
        if isinstance(response, Mapping):
            provider_model = response.get("model", provider_model)
        return Decision(
            action=ActionId(option_id),
            probabilities={ActionId(key): value for key, value in probabilities.items()},
            confidence=confidence,
            provider_model=str(provider_model) if provider_model else None,
            latency_ms=latency_ms,
        )

    def close(self) -> None:
        if self._owns_client and self._client is not None and hasattr(self._client, "close"):
            self._client.close()
            self._client = None

    def __enter__(self) -> JevPolicy:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()
