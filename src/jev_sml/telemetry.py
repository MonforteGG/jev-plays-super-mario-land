from __future__ import annotations

import json
from pathlib import Path

from jev_sml.session import Beat


class JsonlTelemetry:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def record(self, beat: Beat) -> None:
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(beat.journal_line(), ensure_ascii=False) + "\n")

    def close(self) -> None:
        return None

    def __enter__(self) -> JsonlTelemetry:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()
