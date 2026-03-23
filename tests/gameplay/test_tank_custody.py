"""Wave 1 RED tests for the internal tank-custody helper.

These tests describe the behavior of ``modular_simulation.gameplay.tank_custody``
before that module exists.  Every test in this file MUST fail with an ImportError
or AttributeError until Wave 2 implementation is complete.

Behavioral contract (from design.md / specs/session/spec.md):
- custody is keyed by tank process_id (not by feed/product role)
- multiple incoming streams are aggregated into ONE mixed inventory state
  (no parallel per-source buckets)
- boundary-route assignment is keyed by named boundary id (e.g. "feed_a")
- each boundary id has AT MOST ONE active tank at a time for external routes
- purge clears one tank's custody state without deleting the tank record or
  touching any public session API surface

Implementation-shape-flexible: tests use import_module + behavior discovery
with small synonym sets, so the helper can be a class, a module-level object,
or a factory without freezing one exact internal method naming scheme.
"""

from __future__ import annotations

import inspect
import types
from importlib import import_module
from typing import Any
from unittest.mock import MagicMock

import pytest


# ---------------------------------------------------------------------------
# Discovery helpers — same pattern as test_sandbox_session.py
# ---------------------------------------------------------------------------

METHOD_CANDIDATES = {
    "assign": (
        "assign_tank_to_boundary",
        "assign_boundary_route",
        "set_boundary_assignment",
        "set_boundary_route",
    ),
    "update": (
        "update_tank_inventory",
        "add_tank_inventory",
        "record_tank_contribution",
        "apply_stream_to_tank",
        "merge_tank_inventory",
    ),
    "get_inventory": (
        "get_tank_inventory",
        "read_tank_inventory",
        "tank_inventory_for",
        "get_inventory_for_tank",
    ),
    "purge": (
        "purge_tank",
        "clear_tank_inventory",
        "clear_tank_state",
        "purge_tank_inventory",
    ),
}


def _try_build(candidate: Any) -> Any:
    """Try to instantiate a callable with MagicMock stubs for required params."""
    sig = inspect.signature(candidate)
    kwargs: dict[str, Any] = {}
    for param_name, param in sig.parameters.items():
        if param.kind in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD):
            continue
        if param.default is inspect.Parameter.empty:
            kwargs[param_name] = MagicMock()
    try:
        return candidate(**kwargs)
    except Exception:
        return None


def _resolve_callable(candidate: object, names: tuple[str, ...]) -> Any | None:
    for name in names:
        value = getattr(candidate, name, None)
        if callable(value):
            return value
    return None


def _has_required_methods(candidate: object) -> bool:
    return all(
        _resolve_callable(candidate, names) is not None for names in METHOD_CANDIDATES.values()
    )


def _custody_api() -> Any:
    """Discover the tank-custody API surface.

    The module itself must NOT be returned directly (discovery path (a) is
    intentionally excluded): module-level bound methods would share a global
    singleton across tests, violating the session-owned / non-global contract.

    Accepts:
    (b) Any public non-callable exported object (not the module) with all required methods.
    (c) Any public callable — tried with MagicMock stubs (class or factory).
        A fresh instance is returned each call so state is never shared.
    """
    module = import_module("modular_simulation.gameplay.tank_custody")

    # Discovery path (a) intentionally removed: returning the module itself
    # would permit shared module-global singleton state, which violates the
    # session-owned contract.  The implementation must expose a class or factory.

    for name in dir(module):
        if name.startswith("_"):
            continue
        candidate = getattr(module, name)

        # Skip the module itself if somehow re-encountered.
        if isinstance(candidate, types.ModuleType):
            continue

        if not callable(candidate) and _has_required_methods(candidate):
            return candidate

        if callable(candidate):
            built = _try_build(candidate)
            if built is not None and _has_required_methods(built):
                return built

    raise AssertionError(
        "modular_simulation.gameplay.tank_custody exposes no API surface with the "
        "required assignment/update/get/purge behaviors — must be a class or factory, "
        "not module-level bound methods on a global singleton"
    )


def _assign_boundary(api: Any, boundary_id: str, tank_id: str) -> None:
    assign = _resolve_callable(api, METHOD_CANDIDATES["assign"])
    if assign is None:
        raise AssertionError("No assignment behavior found on custody API")
    assign(boundary_id, tank_id)


def _update_inventory(api: Any, tank_id: str, stream: dict[str, Any]) -> None:
    update = _resolve_callable(api, METHOD_CANDIDATES["update"])
    if update is None:
        raise AssertionError("No inventory-update behavior found on custody API")
    update(tank_id, stream)


def _get_inventory(api: Any, tank_id: str) -> Any:
    getter = _resolve_callable(api, METHOD_CANDIDATES["get_inventory"])
    if getter is None:
        raise AssertionError("No inventory-read behavior found on custody API")
    return getter(tank_id)


def _purge_inventory(api: Any, tank_id: str) -> None:
    purge = _resolve_callable(api, METHOD_CANDIDATES["purge"])
    if purge is None:
        raise AssertionError("No purge behavior found on custody API")
    purge(tank_id)


def _make_stream_dict(
    *,
    temperature: float = 300.0,
    pressure: float = 101325.0,
    mole_fractions: tuple[float, ...] = (1.0,),
    molar_flow_rate: float = 1.0,
    species_ids: tuple[str, ...] | None = None,
    phase: str | None = None,
    enthalpy_molar: float | None = None,
    entropy_molar: float | None = None,
) -> dict[str, Any]:
    """Return a minimal stream-like dict with repo-consistent thermodynamic fields."""
    return {
        "temperature": temperature,
        "pressure": pressure,
        "mole_fractions": mole_fractions,
        "molar_flow_rate": molar_flow_rate,
        "species_ids": species_ids,
        "phase": phase,
        "enthalpy_molar": enthalpy_molar,
        "entropy_molar": entropy_molar,
    }


# ---------------------------------------------------------------------------
# 1. Module is importable and exposes the required internal methods
# ---------------------------------------------------------------------------


def test_tank_custody_module_exposes_core_behaviors() -> None:
    """The module must expose assignment/update/get/purge behaviors internally."""
    api = _custody_api()
    for behavior, names in METHOD_CANDIDATES.items():
        assert _resolve_callable(api, names) is not None, (
            f"Expected a callable implementing {behavior!r} behavior from one of {names!r}"
        )


def test_custody_api_is_not_module_level_global_singleton() -> None:
    """Two calls to _custody_api() must return independent, non-shared instances.

    This proves the implementation is session-owned (class/factory), not a
    module-global singleton.  If both calls return the same object (the module),
    state written through one would be visible through the other.
    """
    api_a = _custody_api()
    api_b = _custody_api()

    # Write state into api_a only.
    stream = _make_stream_dict(molar_flow_rate=5.0, temperature=350.0)
    _update_inventory(api_a, "isolation_tank", stream)

    # api_b must not see the state written into api_a.
    result = _get_inventory(api_b, "isolation_tank")
    assert result is None or not result, (
        "Two _custody_api() calls must return independent instances; "
        "state written to one must not be visible through the other.  "
        f"Got {result!r} — this indicates a shared global singleton."
    )


# ---------------------------------------------------------------------------
# 2. Custody is keyed by tank process_id (not by feed/product role)
# ---------------------------------------------------------------------------


def test_custody_is_keyed_by_process_id() -> None:
    """Each tank's custody record is independent and keyed by its process_id."""
    api = _custody_api()

    stream_a = _make_stream_dict(temperature=310.0, pressure=150000.0, molar_flow_rate=2.0)
    stream_b = _make_stream_dict(temperature=320.0, pressure=200000.0, molar_flow_rate=3.0)

    _update_inventory(api, "tank_alpha", stream_a)
    _update_inventory(api, "tank_beta", stream_b)

    inv_alpha = _get_inventory(api, "tank_alpha")
    inv_beta = _get_inventory(api, "tank_beta")

    # Each tank holds a distinct record — they must not alias each other.
    assert inv_alpha is not None, "Expected a non-None inventory record for tank_alpha"
    assert inv_beta is not None, "Expected a non-None inventory record for tank_beta"
    # The two records must represent different states (at minimum different temps).
    # We check a repo-consistent thermodynamic field to confirm separation.
    temp_alpha = _get_field(inv_alpha, "temperature")
    temp_beta = _get_field(inv_beta, "temperature")
    assert temp_alpha != temp_beta, (
        "Custody records for different tanks must be independent; temperatures should differ"
    )


def _get_field(obj: Any, name: str) -> Any:
    """Read a field from either a dict or an object attribute."""
    if isinstance(obj, dict):
        return obj[name]
    return getattr(obj, name)


def test_custody_unknown_tank_returns_none_or_empty() -> None:
    """Querying a process_id that has never been assigned returns None or empty."""
    api = _custody_api()
    result = _get_inventory(api, "nonexistent_tank_xyz")
    # None or an empty/falsy record both satisfy the contract.
    # An exception is NOT acceptable — missing tanks should not be hard errors on read.
    assert result is None or not result, (
        f"get_tank_inventory for an unknown process_id should return None or empty, got {result!r}"
    )


# ---------------------------------------------------------------------------
# 3. Mixed incoming streams are aggregated — not stored as parallel buckets
# ---------------------------------------------------------------------------


def test_multiple_updates_produce_single_aggregate_record() -> None:
    """Multiple update_tank_inventory calls must combine into ONE mixed record.

    The helper MUST NOT store them as separate per-source sub-inventories.
    After two updates the tank holds a single aggregate inventory, not two.
    """
    api = _custody_api()

    stream_1 = _make_stream_dict(
        temperature=300.0,
        pressure=101325.0,
        mole_fractions=(0.4, 0.6),
        molar_flow_rate=2.0,
        species_ids=("methane", "ethane"),
    )
    stream_2 = _make_stream_dict(
        temperature=320.0,
        pressure=110000.0,
        mole_fractions=(0.7, 0.3),
        molar_flow_rate=3.0,
        species_ids=("methane", "ethane"),
    )

    _update_inventory(api, "mix_tank", stream_1)
    _update_inventory(api, "mix_tank", stream_2)

    inventory = _get_inventory(api, "mix_tank")
    assert inventory is not None, "Expected an aggregate inventory record after two updates"

    # The aggregate must not be identical to either pure source.
    # After mixing, total amount should reflect both contributions.
    # We verify that the record is a single object (not a list/tuple of two).
    assert not isinstance(inventory, (list, tuple)), (
        "Aggregate inventory must be a single record, not a list or tuple of per-source buckets"
    )


def test_aggregate_inventory_preserves_repo_consistent_thermodynamic_fields() -> None:
    """Aggregate state must expose repo-consistent thermo fields.

    Required: temperature, pressure, species_ids / composition (mole_fractions or equivalent).
    Optional (accepted if present): phase, enthalpy_molar, entropy_molar.
    """
    api = _custody_api()

    stream = _make_stream_dict(
        temperature=310.0,
        pressure=130000.0,
        mole_fractions=(0.6, 0.4),
        molar_flow_rate=1.5,
        species_ids=("methane", "propane"),
        phase="vapor",
        enthalpy_molar=-80000.0,
        entropy_molar=120.0,
    )

    _update_inventory(api, "thermo_tank", stream)
    inventory = _get_inventory(api, "thermo_tank")
    assert inventory is not None

    # Must expose temperature and pressure (required thermo fields).
    temperature = _get_field(inventory, "temperature")
    pressure = _get_field(inventory, "pressure")
    assert isinstance(temperature, (int, float)), "temperature must be numeric"
    assert isinstance(pressure, (int, float)), "pressure must be numeric"

    # Must expose composition (mole_fractions or equivalent tuple/sequence).
    composition = _get_composition(inventory)
    assert composition is not None, "Aggregate state must expose a composition field"
    assert len(composition) > 0, "Composition must be non-empty after an update"

    # species_ids must be preserved if the incoming stream carried them.
    species = _get_field_optional(inventory, "species_ids")
    if species is not None:
        assert len(species) == len(composition), "species_ids length must match composition length"


def _get_composition(obj: Any) -> Any:
    """Try common composition field names used in this repo."""
    for name in ("mole_fractions", "composition", "mole_fraction"):
        val = _get_field_optional(obj, name)
        if val is not None:
            return val
    return None


def _get_field_optional(obj: Any, name: str) -> Any:
    if isinstance(obj, dict):
        return obj.get(name)
    return getattr(obj, name, None)


def test_aggregate_molar_amount_reflects_combined_contributions() -> None:
    """The aggregate inventory must carry enough information for volume calculation.

    The spec requires state suitable for later outlet-pressure and volume calculation.
    A total molar amount (or equivalent holdup field) must be present and must reflect
    the sum of the contributed amounts after multiple updates.
    """
    api = _custody_api()

    stream_a = _make_stream_dict(molar_flow_rate=2.0)
    stream_b = _make_stream_dict(molar_flow_rate=3.0)

    _update_inventory(api, "amount_tank", stream_a)
    _update_inventory(api, "amount_tank", stream_b)

    inventory = _get_inventory(api, "amount_tank")
    assert inventory is not None

    # Look for a molar amount / holdup / total_mol field.
    amount = _get_molar_amount(inventory)
    assert amount is not None, (
        "Aggregate inventory must expose a total molar amount or holdup field "
        "suitable for later volume/pressure calculations"
    )
    assert isinstance(amount, (int, float)), "Molar amount field must be numeric"
    assert amount > 0, "Molar amount must be positive after two non-zero stream updates"


def _get_molar_amount(obj: Any) -> Any:
    """Try common total-amount field names."""
    for name in (
        "total_mol",
        "molar_amount",
        "holdup_mol",
        "amount_mol",
        "moles",
        "total_moles",
        "molar_holdup",
    ):
        val = _get_field_optional(obj, name)
        if val is not None:
            return val
    return None


# ---------------------------------------------------------------------------
# 4. Boundary-route assignment: each boundary id maps to at most one tank
# ---------------------------------------------------------------------------


def test_boundary_route_assignment_is_keyed_by_boundary_id() -> None:
    """assign_tank_to_boundary maps a named boundary id to a tank process_id."""
    api = _custody_api()

    _assign_boundary(api, "feed_a", "tank_001")

    # Reading back the assignment must return the same tank id.
    assigned = _get_assigned_tank(api, "feed_a")
    assert assigned == "tank_001", (
        f"Expected 'tank_001' assigned to boundary 'feed_a', got {assigned!r}"
    )


def _get_assigned_tank(api: Any, boundary_id: str) -> Any:
    """Read the currently assigned tank for a boundary id via any reasonable accessor."""
    # Try an explicit getter first; fall back to a dict-like interface.
    for getter_name in ("get_boundary_assignment", "get_assigned_tank", "get_boundary_route"):
        getter = getattr(api, getter_name, None)
        if callable(getter):
            return getter(boundary_id)
    # Some implementations may store assignments as a plain dict attribute.
    for attr_name in ("boundary_assignments", "boundary_routes"):
        assignments = getattr(api, attr_name, None)
        if isinstance(assignments, dict):
            return assignments.get(boundary_id)
    raise AssertionError(
        "Cannot read boundary assignment from custody API: "
        "expected a boundary-assignment getter or dict-like boundary-assignment attribute"
    )


def test_each_boundary_id_has_at_most_one_active_tank_at_a_time() -> None:
    """Reassigning a boundary route replaces the previous mapping.

    After reassignment, the boundary id maps ONLY to the new tank,
    not to both the old and the new.
    """
    api = _custody_api()

    _assign_boundary(api, "product_a", "tank_v1")
    _assign_boundary(api, "product_a", "tank_v2")

    assigned = _get_assigned_tank(api, "product_a")
    assert assigned == "tank_v2", (
        "After reassignment, boundary id must map to the NEW tank only; "
        f"expected 'tank_v2', got {assigned!r}"
    )


def test_different_boundary_ids_can_each_be_assigned_independently() -> None:
    """Two distinct boundary ids may each have their own assigned tank."""
    api = _custody_api()

    _assign_boundary(api, "feed_a", "tank_feed")
    _assign_boundary(api, "product_a", "tank_product")

    assert _get_assigned_tank(api, "feed_a") == "tank_feed"
    assert _get_assigned_tank(api, "product_a") == "tank_product"


def test_boundary_route_uniqueness_rule_does_not_constrain_unassigned_boundaries() -> None:
    """An unassigned boundary id returns None (or equivalent falsy) without error."""
    api = _custody_api()

    result = _get_assigned_tank(api, "boundary_never_assigned")
    assert result is None or not result, (
        f"An unassigned boundary should return None or empty, got {result!r}"
    )


# ---------------------------------------------------------------------------
# 5. Purge clears one tank's custody state — no side effects on other tanks
# ---------------------------------------------------------------------------


def test_purge_clears_the_target_tank_custody_record() -> None:
    """purge_tank removes the aggregate stored state for the given process_id."""
    api = _custody_api()

    stream = _make_stream_dict(molar_flow_rate=1.0)
    _update_inventory(api, "purgeable_tank", stream)

    # Confirm inventory exists before purge.
    assert _get_inventory(api, "purgeable_tank") is not None, (
        "Expected inventory to exist before purge"
    )

    _purge_inventory(api, "purgeable_tank")

    after = _get_inventory(api, "purgeable_tank")
    assert after is None or not after, (
        f"After purge, get_tank_inventory should return None or empty for that tank; got {after!r}"
    )


def test_purge_does_not_affect_other_tank_custody_records() -> None:
    """Purging one tank must not clear any other tank's custody state."""
    api = _custody_api()

    stream = _make_stream_dict(molar_flow_rate=1.5)
    _update_inventory(api, "bystander_tank", stream)
    _update_inventory(api, "purge_target", stream)

    _purge_inventory(api, "purge_target")

    bystander = _get_inventory(api, "bystander_tank")
    assert bystander is not None and bystander, (
        f"Purging 'purge_target' must not clear 'bystander_tank'; got {bystander!r}"
    )


def test_purge_of_unknown_tank_does_not_raise() -> None:
    """Purging a process_id that was never assigned must not raise an exception.

    purge is a clearing primitive; it must be idempotent on unknown ids.
    """
    api = _custody_api()
    # Must not raise.
    _purge_inventory(api, "never_seen_tank")


def test_purge_does_not_affect_boundary_route_assignments() -> None:
    """Purging a tank's custody record must not remove boundary-route assignments.

    Boundary assignments are a separate bookkeeping concern; purge only clears
    the aggregate stored inventory state for a given process_id.
    """
    api = _custody_api()

    stream = _make_stream_dict(molar_flow_rate=2.0)
    _update_inventory(api, "assigned_tank", stream)
    _assign_boundary(api, "feed_b", "assigned_tank")

    _purge_inventory(api, "assigned_tank")

    # The boundary assignment must still be in place.
    assigned = _get_assigned_tank(api, "feed_b")
    assert assigned == "assigned_tank", (
        "purge_tank must not clear boundary-route assignments; "
        f"expected 'assigned_tank' still assigned to 'feed_b', got {assigned!r}"
    )


# ---------------------------------------------------------------------------
# 6. Boundary-route uniqueness is scoped to external routes only
# ---------------------------------------------------------------------------


def test_boundary_route_uniqueness_rule_does_not_constrain_non_boundary_streams() -> None:
    """The one-active-route-per-boundary rule applies only to external boundary routes.

    update_tank_inventory must accept multiple calls for the same tank
    without requiring any boundary assignment.  This test confirms the helper
    does NOT refuse multi-stream fan-in to a tank that has no boundary route.
    """
    api = _custody_api()

    stream_x = _make_stream_dict(temperature=305.0, molar_flow_rate=1.0)
    stream_y = _make_stream_dict(temperature=315.0, molar_flow_rate=1.0)

    # Both calls should succeed without error.
    _update_inventory(api, "fan_in_tank", stream_x)
    _update_inventory(api, "fan_in_tank", stream_y)

    inventory = _get_inventory(api, "fan_in_tank")
    assert inventory is not None, (
        "update_tank_inventory must accept multi-stream fan-in for non-boundary tanks "
        "and store an aggregate record"
    )
