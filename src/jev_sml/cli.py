from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from jev_sml.policy import JevPolicy
from jev_sml.pyboy import PyBoyGame
from jev_sml.session import GameSession
from jev_sml.telemetry import JsonlTelemetry


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="jev-sml")
    sub = parser.add_subparsers(dest="command", required=True)
    play = sub.add_parser("play", help="play Super Mario Land World 1-1 with JEV")
    play.add_argument("--rom", type=Path, default=None)
    play.add_argument("--frames-per-decision", type=int, default=16)
    play.add_argument("--max-decisions", type=int, default=None)
    play.add_argument("--log", type=Path, default=Path("runs/latest/beats.jsonl"))
    play.add_argument("--window", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command != "play":
        return 2
    rom = args.rom or (Path(os.environ["SML_ROM"]) if os.environ.get("SML_ROM") else None)
    if rom is None or not rom.is_file():
        print("ROM not found. Pass --rom or set SML_ROM.", file=sys.stderr)
        return 2
    if args.frames_per_decision < 1:
        print("frames-per-decision must be positive", file=sys.stderr)
        return 2
    if not os.environ.get("TYPESAFE_API_KEY"):
        print("TYPESAFE_API_KEY is not set", file=sys.stderr)
        return 2

    game = PyBoyGame.open(rom, world=(1, 1), window=args.window)
    policy = JevPolicy()
    telemetry = JsonlTelemetry(args.log)
    try:
        outcome = GameSession(
            game,
            policy,
            frames_per_decision=args.frames_per_decision,
            telemetry=telemetry,
        ).run(max_decisions=args.max_decisions)
        print(json.dumps(outcome.model_dump(mode="json")))
        return 0
    finally:
        policy.close()
        telemetry.close()
        game.close()


if __name__ == "__main__":
    raise SystemExit(main())
