"""Public surface for instantiating gameplay play-starts by id."""

from __future__ import annotations

from modular_simulation.gameplay.starts.builders import SeedBackedStart, build_seed_backed_start


def build_start(*, start_id: str) -> SeedBackedStart:
    """Return a seed-backed start instance for *start_id*."""
    return build_seed_backed_start(start_id=start_id)
