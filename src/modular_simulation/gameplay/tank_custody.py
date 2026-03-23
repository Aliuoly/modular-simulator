"""Internal tank-custody helper.

Provides lightweight bookkeeping for:
- Per-tank aggregate inventory state (keyed by process_id)
- Boundary-route assignments (each named boundary id maps to at most one tank)

This module is internal. It does NOT touch the public session API, HTTP routes,
economics contracts, or any bootstrap/build-item lists.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class _AggregateInventory:
    """Mixed inventory state for a single holding tank.

    Fields follow the repo-canonical ``StreamData`` vocabulary so that the
    stored record is directly usable for later pressure/volume calculations.
    """

    temperature: float
    pressure: float
    mole_fractions: tuple[float, ...]
    total_mol: float
    species_ids: tuple[str, ...] | None = None
    phase: str | None = None
    enthalpy_molar: float | None = None
    entropy_molar: float | None = None


def _mix(
    existing: _AggregateInventory,
    stream: dict[str, Any],
) -> _AggregateInventory:
    """Combine an existing aggregate with a new incoming stream dict.

    Uses molar-flow-weighted mixing for temperature, pressure, and mole fractions;
    preserves
    optional thermo fields if present in the incoming stream.
    """
    n_new: float = float(stream.get("molar_flow_rate", 0.0))
    n_old: float = existing.total_mol
    n_total: float = n_old + n_new

    if n_total == 0.0:
        return existing

    # Weighted-average temperature
    t_new: float = float(stream.get("temperature", existing.temperature))
    temperature = (n_old * existing.temperature + n_new * t_new) / n_total

    # Pressure — use weighted average
    p_new: float = float(stream.get("pressure", existing.pressure))
    pressure = (n_old * existing.pressure + n_new * p_new) / n_total

    # Mole fractions — weighted average (normalised)
    mf_new_raw = stream.get("mole_fractions") or existing.mole_fractions
    mf_new: tuple[float, ...] = tuple(float(x) for x in mf_new_raw)
    mf_old: tuple[float, ...] = existing.mole_fractions

    # Align lengths (zero-pad shorter side)
    n_comp = max(len(mf_old), len(mf_new))
    mf_old_padded = mf_old + (0.0,) * (n_comp - len(mf_old))
    mf_new_padded = mf_new + (0.0,) * (n_comp - len(mf_new))

    mf_mixed_raw = tuple(
        (n_old * mf_old_padded[i] + n_new * mf_new_padded[i]) / n_total for i in range(n_comp)
    )
    total = sum(mf_mixed_raw)
    if total > 0.0:
        mole_fractions: tuple[float, ...] = tuple(x / total for x in mf_mixed_raw)
    else:
        mole_fractions = mf_mixed_raw

    # species_ids — keep existing if new stream doesn't carry them
    species_ids = stream.get("species_ids") or existing.species_ids
    if species_ids is not None:
        species_ids = tuple(species_ids)

    # Optional thermo fields — prefer incoming if provided
    phase = stream.get("phase") or existing.phase
    enthalpy_molar = (
        stream.get("enthalpy_molar")
        if stream.get("enthalpy_molar") is not None
        else existing.enthalpy_molar
    )
    entropy_molar = (
        stream.get("entropy_molar")
        if stream.get("entropy_molar") is not None
        else existing.entropy_molar
    )

    return _AggregateInventory(
        temperature=temperature,
        pressure=pressure,
        mole_fractions=mole_fractions,
        total_mol=n_total,
        species_ids=species_ids,
        phase=phase,
        enthalpy_molar=enthalpy_molar,
        entropy_molar=entropy_molar,
    )


def _from_stream(stream: dict[str, Any]) -> _AggregateInventory:
    """Create a fresh aggregate record from the first incoming stream dict."""
    mole_fractions_raw = stream.get("mole_fractions") or (1.0,)
    mole_fractions: tuple[float, ...] = tuple(float(x) for x in mole_fractions_raw)
    species_ids = stream.get("species_ids")
    if species_ids is not None:
        species_ids = tuple(species_ids)
    enthalpy_molar = stream.get("enthalpy_molar")
    entropy_molar = stream.get("entropy_molar")
    return _AggregateInventory(
        temperature=float(stream.get("temperature", 300.0)),
        pressure=float(stream.get("pressure", 101325.0)),
        mole_fractions=mole_fractions,
        total_mol=float(stream.get("molar_flow_rate", 0.0)),
        species_ids=species_ids,
        phase=stream.get("phase"),
        enthalpy_molar=enthalpy_molar,
        entropy_molar=entropy_molar,
    )


class TankCustody:
    """Internal bookkeeper for tank inventory state and boundary-route assignments.

    All state is instance-owned; session code holds a private reference and
    never exposes this object through public API surfaces.

    The test discovery helper locates behavior by synonym-based method lookup,
    so this class can remain the single concrete ownership surface.
    """

    def __init__(self) -> None:
        self._inventories: dict[str, _AggregateInventory] = {}
        self.boundary_assignments: dict[str, str] = {}

    # ------------------------------------------------------------------
    # Boundary-route assignment
    # ------------------------------------------------------------------

    def assign_tank_to_boundary(self, boundary_id: str, tank_id: str) -> None:
        """Map a named boundary id to a tank process_id (replaces any prior mapping)."""
        self.boundary_assignments[boundary_id] = tank_id

    def get_boundary_assignment(self, boundary_id: str) -> str | None:
        """Return the tank process_id currently assigned to *boundary_id*, or None."""
        return self.boundary_assignments.get(boundary_id)

    # ------------------------------------------------------------------
    # Tank inventory state
    # ------------------------------------------------------------------

    def update_tank_inventory(self, tank_id: str, stream: dict[str, Any]) -> None:
        """Merge *stream* into the aggregate inventory for *tank_id*.

        Multiple calls accumulate into ONE mixed record — no per-source buckets.
        """
        existing = self._inventories.get(tank_id)
        if existing is None:
            self._inventories[tank_id] = _from_stream(stream)
        else:
            self._inventories[tank_id] = _mix(existing, stream)

    def get_tank_inventory(self, tank_id: str) -> _AggregateInventory | None:
        """Return the aggregate inventory for *tank_id*, or None if unknown."""
        return self._inventories.get(tank_id)

    def purge_tank(self, tank_id: str) -> None:
        """Clear the aggregate inventory for *tank_id*.

        Idempotent: purging an unknown tank is a no-op.
        Boundary-route assignments are NOT affected.
        """
        self._inventories.pop(tank_id, None)


__all__ = [
    "TankCustody",
]
