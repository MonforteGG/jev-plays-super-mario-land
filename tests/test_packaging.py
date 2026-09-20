from __future__ import annotations

import jev_sml
import jev_sml.cli
import jev_sml.policy
import jev_sml.pyboy


def test_public_exports() -> None:
    assert jev_sml.__all__ == [
        "ActionId",
        "CycleResult",
        "FakeGamePort",
        "GameSession",
        "ReplayPolicy",
    ]


def test_importing_package_does_not_load_optional_runtime() -> None:
    import sys

    assert "pyboy" not in sys.modules
    assert "typesafe_sdk" not in sys.modules


def test_cli_play_without_rom_exits_2() -> None:
    assert jev_sml.cli.main(["play"]) == 2
