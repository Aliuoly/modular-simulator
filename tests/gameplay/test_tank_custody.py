"""Ownership-boundary regression for ej7.1 (simulation-owned tank state).

Behavioral contract (from openspec/specs/session/spec.md — ej7.1 wave):
- Gameplay SHALL NOT maintain a session-owned mirror of simulation-owned
  holding-tank conserved inventory or mixed thermodynamic state.
- Any future gameplay-owned tank metadata MAY track only non-physical route or
  UI intent keyed by tank process_id, and SHALL remain non-public.
- No new public tank methods, tank snapshot fields, or build/start widenings in ej7.1.

These tests assert that the prohibited physical-mirror surface has been removed.
"""

from __future__ import annotations

import importlib
import importlib.util
import inspect
import sys


# ---------------------------------------------------------------------------
# 1. Gameplay no longer carries a physical tank-inventory mirror
# ---------------------------------------------------------------------------


def test_gameplay_tank_custody_module_does_not_exist() -> None:
    """Gameplay must not own a module that mirrors simulation-owned physical tank state.

    The ej7.1 wave removes or makes non-importable the previous
    ``modular_simulation.gameplay.tank_custody`` module, which contained
    conserved-inventory and mixed thermodynamic state owned by the
    simulation runtime, not gameplay.
    """
    mod_name = "modular_simulation.gameplay.tank_custody"
    # Remove any cached entry first so the import machinery makes a fresh decision.
    sys.modules.pop(mod_name, None)
    spec = importlib.util.find_spec(mod_name)
    assert spec is None, (
        f"Module {mod_name!r} still exists on disk. "
        "ej7.1 requires that gameplay no longer ships a module that owns "
        "conserved tank inventory or mixed thermodynamic state — "
        "those are now simulation-runtime-owned quantities."
    )


def test_gameplay_package_does_not_re_export_physical_tank_inventory_types() -> None:
    """The gameplay package __init__ must not re-export any physical-tank inventory type.

    Forbidden names are any that imply conserved inventory or thermodynamic
    state ownership at the gameplay layer (e.g. TankCustody, AggregateInventory,
    HoldingTankState, TankInventory, etc.).
    """
    import modular_simulation.gameplay as gameplay_pkg

    forbidden_patterns = (
        "TankCustody",
        "AggregateInventory",
        "HoldingTankState",
        "TankInventory",
        "TankMirror",
    )
    for name in dir(gameplay_pkg):
        for pattern in forbidden_patterns:
            assert pattern not in name, (
                f"gameplay package re-exports {name!r} which matches forbidden pattern "
                f"{pattern!r}. Gameplay must not own or re-export physical tank "
                f"inventory types in ej7.1."
            )


# ---------------------------------------------------------------------------
# 2. Existing gameplay public surfaces are unchanged (live slice guard)
# ---------------------------------------------------------------------------


def test_realtime_service_has_no_new_public_tank_methods() -> None:
    """No new public tank-related methods must appear on RealtimeGameService.

    The ej7.1 ownership cleanup must not widen the public realtime-service
    surface with tank-specific methods (e.g. purge_tank, assign_tank, etc.).
    """
    from modular_simulation.gameplay.realtime_service import RealtimeGameService

    forbidden_prefixes = ("purge_tank", "assign_tank", "update_tank", "get_tank_inventory")
    public_methods = [
        name
        for name in dir(RealtimeGameService)
        if not name.startswith("_") and callable(getattr(RealtimeGameService, name, None))
    ]
    for method_name in public_methods:
        for prefix in forbidden_prefixes:
            assert not method_name.startswith(prefix), (
                f"RealtimeGameService has a new public method {method_name!r} which "
                f"matches forbidden prefix {prefix!r}. The ej7.1 ownership cleanup "
                f"must not widen the public service surface with tank operations."
            )


def test_sandbox_session_has_no_new_public_tank_snapshot_fields() -> None:
    """SimulationSessionSnapshot must not gain new tank inventory or custody fields.

    The ej7.1 wave must not add physical tank-state fields to the frozen
    simulation session snapshot contract.
    """
    from modular_simulation.gameplay.contracts import SimulationSessionSnapshot

    forbidden_fields = (
        "tank_inventory",
        "tank_custody",
        "holding_tank_state",
        "tank_mirror",
        "aggregate_inventory",
    )
    snapshot_fields = set(inspect.signature(SimulationSessionSnapshot).parameters.keys())
    # Also check dataclass fields if applicable
    if hasattr(SimulationSessionSnapshot, "__dataclass_fields__"):
        snapshot_fields |= set(SimulationSessionSnapshot.__dataclass_fields__.keys())

    for field_name in forbidden_fields:
        assert field_name not in snapshot_fields, (
            f"SimulationSessionSnapshot has a new field {field_name!r} which is "
            f"a prohibited physical-tank-state field. ej7.1 forbids adding "
            f"conserved inventory or thermodynamic state to the public snapshot."
        )


def test_supported_build_item_ids_unchanged_after_ownership_cleanup() -> None:
    """SUPPORTED_BUILD_ITEM_IDS must stay exactly the live frozen set after cleanup.

    Removing the gameplay physical-tank mirror must not cause any accidental
    widening of the build-item allowlist.
    """
    from modular_simulation.gameplay import realtime_service

    assert tuple(realtime_service.SUPPORTED_BUILD_ITEM_IDS) == (
        "place_heater_cooler",
        "place_flash_drum",
        "build_process_line",
    ), (
        "SUPPORTED_BUILD_ITEM_IDS changed after ownership cleanup. "
        "The ej7.1 wave must not widen the live build-item set."
    )
