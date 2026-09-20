# Designed playbook for MVP 1

Definition of done. `pytest` is green on a closed observation-decision-execution cycle using `ReplayPolicy` and a fake emulator backend. The live JEV adapter validates Choice responses against the current action set. The PyBoy adapter exists and is untested against a ROM until a ROM path is supplied.

Rigor. High on domain types and the JEV boundary. Those are one-way doors. Medium on tile-to-hazard heuristics until a ROM exists to measure them.

Units, in order.

1. Arena design of types and module map. Gate for all later code.
2. Package scaffold. `pyproject.toml`, `src/`, pytest, ruff.
3. Domain types from the synthesized sketch. Tests for illegal-state rejection.
4. Fake backend plus runner cycle with ReplayPolicy. Tests for one decision holding N frames.
5. Pure extractor and observation builder from RAM bytes plus a fake game_area. Tests for enemy-ahead and gap-ahead on fixtures.
6. Action generator and executor button table. Tests for airborne jump filtering and button recipes.
7. TypeSafe JEV adapter with the same validation rules as the Pokemon sibling. Tests with a stub client.
8. PyBoy adapter. Import-guarded. No ROM required for CI.
9. CLI `play` and JSONL telemetry.
10. Verify the Phase A predicate. Open a PR.

Do not start unit 3 until the arena synthesis note exists.
