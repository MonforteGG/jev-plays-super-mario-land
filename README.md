# Play World 1-1 with JEV

The package exposes `GameSession`. Callers do not wire perception, menus, JEV, or buttons.

Install Python 3.12. Tests need pydantic and pytest only.

```
pip install -e ".[dev]"
pip install -e ".[runtime]"
```

`runtime` adds PyBoy and `typesafe-sdk`. Set `TYPESAFE_API_KEY`. Pass a legal ROM with `--rom` or `SML_ROM`. The ROM is not in git. Model is pinned to `jev-1.13.0`.

## Live play

```
jev-sml play --rom path\to\sml.gb --frames-per-decision 16
```

The process starts World 1-1 as small Mario, freezes the emulator while JEV answers, holds the chosen recipe for 16 frames, and appends one JSONL `Beat` per window. It stops on level clear, game over, death with no lives, or `--max-decisions`.

## Test a cycle without a ROM

```python
from jev_sml import ActionId, FakeGamePort, GameSession, ReplayPolicy

game = FakeGamePort.from_fixture("grounded_gap_in_12_frames")
session = GameSession(game, ReplayPolicy(["right_jump"]), frames_per_decision=16)
beat = session.cycle()
assert beat.result.kind == "advanced"
assert beat.decision.action is ActionId.RIGHT_JUMP
assert game.applied_edges[-1].kind == "release"
```

`FakeGamePort` does not import PyBoy. `ReplayPolicy` does not call TypeSafe.

## Public names

```python
from jev_sml import ActionId, FakeGamePort, GameSession, ReplayPolicy, CycleResult
```

`JevPolicy`, `PyBoyGame`, `Observation`, and `DecisionContext` stay module imports.
