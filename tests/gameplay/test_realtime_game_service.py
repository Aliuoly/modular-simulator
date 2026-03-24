from __future__ import annotations

import inspect
from importlib import import_module
from typing import Any, Mapping, cast
from unittest.mock import MagicMock, patch

import pytest

from modular_simulation.gameplay.contracts import CashLedgerSnapshot, SimulationSessionSnapshot
from modular_simulation.gameplay.sandbox_catalog import build_sandbox_catalog


SUPPORTED_MODE_IDS = (
    "phase1_process_sandbox_v1",
    "heater_flash_guided_build_v1",
)
SUPPORTED_SIMULATION_DT_S_PRESETS = (1 / 60, 1 / 30, 1 / 20)
DEFAULT_SIMULATION_DT_S = 1 / 60

REQUIRED_SERVICE_METHODS = (
    "get_bootstrap",
    "create_session",
    "get_snapshot",
    "build",
    "buy_feed",
    "sell_product",
    "restart_session",
    "tick",
)


def _as_mapping(obj: object) -> Mapping[str, object] | None:
    return obj if isinstance(obj, Mapping) else None


def _field(obj: object, name: str) -> object:
    as_mapping = _as_mapping(obj)
    if as_mapping is not None:
        return as_mapping[name]
    return getattr(obj, name)


def _sandbox_error_type() -> type[Any]:
    contracts = import_module("modular_simulation.gameplay.contracts")
    return getattr(contracts, "SandboxRequestError")


def _has_required_methods(candidate: object) -> bool:
    return all(callable(getattr(candidate, method, None)) for method in REQUIRED_SERVICE_METHODS)


def _try_build(candidate: Any) -> Any:
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


def _service_api() -> Any:
    module = import_module("modular_simulation.gameplay.realtime_service")

    if _has_required_methods(module):
        return module

    for name in dir(module):
        if name.startswith("_"):
            continue
        candidate = getattr(module, name)
        if not callable(candidate) and _has_required_methods(candidate):
            return candidate
        if callable(candidate):
            built = _try_build(candidate)
            if built is not None and _has_required_methods(built):
                return built

    raise AssertionError(
        "modular_simulation.gameplay.realtime_service exposes no public API "
        "surface with the frozen realtime-service methods"
    )


def _create_session(
    service: Any,
    *,
    mode_id: str,
    simulation_dt_s: float | None = None,
) -> object:
    if simulation_dt_s is None:
        return service.create_session(mode_id=mode_id)
    return service.create_session(mode_id=mode_id, simulation_dt_s=simulation_dt_s)


def test_realtime_service_api_surface_is_frozen() -> None:
    service = _service_api()
    assert (
        tuple(name for name in REQUIRED_SERVICE_METHODS if callable(getattr(service, name, None)))
        == REQUIRED_SERVICE_METHODS
    )


def test_bootstrap_exposes_exact_slice_modes_and_simulation_dt_contract() -> None:
    service = _service_api()

    bootstrap = service.get_bootstrap()

    assert tuple(cast(Any, _field(bootstrap, "supported_mode_ids"))) == SUPPORTED_MODE_IDS
    assert tuple(
        cast(Any, _field(bootstrap, "supported_simulation_dt_s_presets"))
    ) == pytest.approx(SUPPORTED_SIMULATION_DT_S_PRESETS)
    assert _field(bootstrap, "default_simulation_dt_s") == pytest.approx(DEFAULT_SIMULATION_DT_S)
    assert _field(bootstrap, "pause_supported") is False


@pytest.mark.parametrize("simulation_dt_s", [None, 1 / 60, 1 / 30, 1 / 20])
def test_session_creation_accepts_only_advertised_simulation_dt_presets(
    simulation_dt_s: float | None,
) -> None:
    service = _service_api()

    created = _create_session(
        service,
        mode_id="phase1_process_sandbox_v1",
        simulation_dt_s=simulation_dt_s,
    )
    snapshot = _field(created, "snapshot")
    expected_dt = DEFAULT_SIMULATION_DT_S if simulation_dt_s is None else simulation_dt_s
    assert _field(snapshot, "simulation_dt_s") == pytest.approx(expected_dt)


def test_unsupported_simulation_dt_is_rejected_with_stable_error_code() -> None:
    service = _service_api()
    error_type = _sandbox_error_type()

    with pytest.raises(error_type) as exc_info:
        _create_session(
            service,
            mode_id="phase1_process_sandbox_v1",
            simulation_dt_s=0.1,
        )
    assert exc_info.value.error_code == "unsupported_simulation_dt_s"


def test_only_one_active_local_session_can_exist_at_once() -> None:
    service = _service_api()
    error_type = _sandbox_error_type()

    _create_session(service, mode_id="phase1_process_sandbox_v1")
    with pytest.raises(error_type) as exc_info:
        _create_session(service, mode_id="heater_flash_guided_build_v1")
    assert exc_info.value.error_code == "session_already_active"


def test_sessions_are_always_running_and_pause_resume_are_not_supported() -> None:
    service = _service_api()

    created = _create_session(service, mode_id="phase1_process_sandbox_v1")
    snapshot = _field(created, "snapshot")

    assert _field(snapshot, "is_running") is True
    assert not callable(getattr(service, "pause_session", None))
    assert not callable(getattr(service, "resume_session", None))


def test_restart_preserves_session_id_and_resets_slice_state() -> None:
    service = _service_api()

    created = _create_session(service, mode_id="phase1_process_sandbox_v1")
    session_id = _field(created, "session_id")
    initial_snapshot = _field(created, "snapshot")

    service.buy_feed(session_id=session_id, material_id="feed_a", quantity_mol=1.0)
    service.tick(session_id=session_id, wall_dt_s=0.5)

    restarted = service.restart_session(session_id=session_id)
    restarted_snapshot = _field(restarted, "snapshot")

    assert _field(restarted_snapshot, "session_id") == session_id
    assert _field(restarted_snapshot, "mode_id") == _field(initial_snapshot, "mode_id")
    assert _field(restarted_snapshot, "simulation_dt_s") == pytest.approx(
        _field(initial_snapshot, "simulation_dt_s")
    )

    restarted_sim = _field(restarted_snapshot, "simulation_snapshot")
    initial_sim = _field(initial_snapshot, "simulation_snapshot")
    assert isinstance(restarted_sim, SimulationSessionSnapshot)
    assert isinstance(initial_sim, SimulationSessionSnapshot)
    assert restarted_sim.elapsed_time_s == pytest.approx(initial_sim.elapsed_time_s)
    assert restarted_sim.feed_inventory_by_material_id == initial_sim.feed_inventory_by_material_id
    assert (
        restarted_sim.product_inventory_by_product_id == initial_sim.product_inventory_by_product_id
    )


def test_combined_snapshot_contains_required_authoritative_sections() -> None:
    service = _service_api()

    created = _create_session(service, mode_id="phase1_process_sandbox_v1")
    session_id = _field(created, "session_id")
    snapshot = service.get_snapshot(session_id=session_id)

    for required_field in (
        "session_id",
        "is_running",
        "mode_id",
        "session_kind",
        "active_start_id",
        "active_tutorial_id",
        "elapsed_time_s",
        "simulation_dt_s",
        "simulation_snapshot",
        "cash_ledger",
        "published_signal_values_by_id",
        "topology",
        "board_layout",
        "supported_build_item_ids",
        "lag_backlog_s",
    ):
        _field(snapshot, required_field)

    assert _field(snapshot, "mode_id") in SUPPORTED_MODE_IDS
    assert isinstance(_field(snapshot, "simulation_snapshot"), SimulationSessionSnapshot)
    assert isinstance(_field(snapshot, "cash_ledger"), CashLedgerSnapshot)
    assert isinstance(_field(snapshot, "published_signal_values_by_id"), Mapping)
    assert isinstance(_field(snapshot, "topology"), Mapping)
    assert isinstance(_field(snapshot, "board_layout"), Mapping)
    assert tuple(cast(Any, _field(snapshot, "supported_build_item_ids"))) == (
        "place_heater_cooler",
        "place_flash_drum",
        "build_process_line",
    )
    assert cast(float, _field(snapshot, "lag_backlog_s")) >= 0.0

    simulation_snapshot = cast(SimulationSessionSnapshot, _field(snapshot, "simulation_snapshot"))
    assert _field(snapshot, "session_kind") == simulation_snapshot.session_kind
    assert _field(snapshot, "active_start_id") == simulation_snapshot.active_start_id
    assert _field(snapshot, "active_tutorial_id") == simulation_snapshot.active_tutorial_id
    assert _field(snapshot, "elapsed_time_s") == pytest.approx(simulation_snapshot.elapsed_time_s)


def test_commands_do_not_require_or_accept_client_receipt_ids() -> None:
    service = _service_api()

    create_result = _create_session(service, mode_id="phase1_process_sandbox_v1")
    session_id = _field(create_result, "session_id")

    for method_name in ("build", "buy_feed", "sell_product"):
        signature = inspect.signature(getattr(service, method_name))
        assert all("receipt" not in parameter_name for parameter_name in signature.parameters)

    build_result = service.build(
        session_id=session_id,
        item_id="place_heater_cooler",
        config={"process_id": "heater_1"},
        layout={"anchor_xy": (0.0, 0.0)},
    )
    assert _field(build_result, "accepted") is True

    buy_result = service.buy_feed(session_id=session_id, material_id="feed_a", quantity_mol=1.0)
    assert _field(buy_result, "accepted") is True


def test_service_advances_from_wall_clock_without_explicit_tick_on_get_snapshot() -> None:
    """Service must own wall-clock progression: get_snapshot() advances without a prior tick().

    Uses deterministic time patching so no real-time waiting is needed.
    """
    realtime_module = import_module("modular_simulation.gameplay.realtime_service")
    service = realtime_module.RealtimeGameService()

    # Patch the time source at t=0 for session creation and feed purchase.
    with patch.object(realtime_module, "_monotonic", return_value=0.0):
        created = service.create_session(mode_id="phase1_process_sandbox_v1")
        session_id = _field(created, "session_id")
        # Buy feed at t=0 so the simulation can actually run (wall_dt=0 here, no advancement).
        service.buy_feed(session_id=session_id, material_id="feed_a", quantity_mol=100.0)

    # Now advance simulated wall clock by 1.0 second and call get_snapshot() (no tick()).
    with patch.object(realtime_module, "_monotonic", return_value=1.0):
        snapshot = service.get_snapshot(session_id=session_id)

    # Simulation must have advanced: elapsed_time_s > 0.0.
    elapsed = cast(float, _field(snapshot, "elapsed_time_s"))
    assert elapsed > 0.0, (
        "Service should self-advance from wall-clock time inside get_snapshot(); "
        "elapsed_time_s was still 0 after 1 simulated second."
    )


def test_service_advances_from_wall_clock_without_explicit_tick_on_buy_feed() -> None:
    """Service must advance the session from wall clock in buy_feed() without prior tick().

    A second buy_feed call at t=1.0 (after session created at t=0.0 with initial feed) should
    show elapsed simulation time has advanced due to the wall-clock delta.
    """
    realtime_module = import_module("modular_simulation.gameplay.realtime_service")
    service = realtime_module.RealtimeGameService()

    with patch.object(realtime_module, "_monotonic", return_value=0.0):
        created = service.create_session(mode_id="phase1_process_sandbox_v1")
        session_id = _field(created, "session_id")
        # Prime with feed so simulation can run during the subsequent wall-clock tick.
        service.buy_feed(session_id=session_id, material_id="feed_a", quantity_mol=100.0)

    # At t=1.0, buy more feed. The service must advance the simulation from the 1s wall delta
    # before recording the purchase.
    with patch.object(realtime_module, "_monotonic", return_value=1.0):
        result = service.buy_feed(session_id=session_id, material_id="feed_a", quantity_mol=1.0)

    elapsed = cast(float, _field(_field(result, "snapshot"), "elapsed_time_s"))
    assert elapsed > 0.0, (
        "Service should self-advance from wall-clock time inside buy_feed(); "
        "elapsed_time_s was still 0 after 1 simulated second."
    )


def test_restart_resets_wall_clock_baseline_so_subsequent_snapshot_is_not_inflated() -> None:
    """After restart, the session's internal clock baseline must reset.

    If we restart at t=10.0 and then call get_snapshot() at t=10.05,
    only ~0.05s worth of simulation must advance, not 10.05s.
    """
    realtime_module = import_module("modular_simulation.gameplay.realtime_service")
    service = realtime_module.RealtimeGameService()

    with patch.object(realtime_module, "_monotonic", return_value=0.0):
        created = service.create_session(mode_id="phase1_process_sandbox_v1")
    session_id = _field(created, "session_id")

    # Advance 5 seconds to get some history.
    with patch.object(realtime_module, "_monotonic", return_value=5.0):
        service.get_snapshot(session_id=session_id)

    # Restart at t=10.0.
    with patch.object(realtime_module, "_monotonic", return_value=10.0):
        service.restart_session(session_id=session_id)

    # 50ms after restart - should only advance ~0.05s.
    with patch.object(realtime_module, "_monotonic", return_value=10.05):
        snapshot = service.get_snapshot(session_id=session_id)

    elapsed = cast(float, _field(snapshot, "elapsed_time_s"))
    # Must be much less than the 10.05s total wall time since session start.
    # Allow up to 0.5s slack for rounding but not 10s.
    assert elapsed < 1.0, (
        f"After restart, elapsed_time_s ({elapsed:.3f}) should reflect only the time "
        "since restart (0.05s), not the full 10.05s since session creation."
    )


# ---------------------------------------------------------------------------
# Wave 1 — RED guards: item-aware placement seam (module-private helper)
#
# These tests prove that a module-private helper exists in realtime_service.py
# and that it correctly resolves runtime-authoritative metadata (unit_module,
# unit_type, constructor_payload, and real ports) from SandboxCatalogItemDefinition
# records with item_kind="unit_blueprint" / apply_kind="add_process".
#
# The helper does NOT exist yet, so all tests in this group are expected to
# fail (RED) until Wave 2 implementation is complete.
# ---------------------------------------------------------------------------


def _resolve_unit_metadata_helper() -> Any:
    """Return the module-private helper that _install_unit() should call.

    The convention frozen by this test pack is that the helper is named
    ``_resolve_unit_metadata`` and lives at module level in
    ``modular_simulation.gameplay.realtime_service``.
    """
    module = import_module("modular_simulation.gameplay.realtime_service")
    helper = getattr(module, "_resolve_unit_metadata", None)
    if helper is None or not callable(helper):
        raise AssertionError(
            "modular_simulation.gameplay.realtime_service does not expose a "
            "module-private callable '_resolve_unit_metadata'. "
            "This helper must be added in Wave 2 so that _install_unit() can "
            "resolve runtime-authoritative unit metadata from catalog records."
        )
    return helper


def test_module_private_resolve_unit_metadata_helper_exists() -> None:
    """A module-private helper '_resolve_unit_metadata' must exist in realtime_service.

    This is the exact proof seam: _install_unit() should call this helper to
    resolve unit metadata from a SandboxCatalogItemDefinition record instead of
    hard-coding generic ports.  The helper must be importable and callable.
    """
    # Will raise AssertionError (red) if the helper is absent.
    _resolve_unit_metadata_helper()


def test_install_unit_uses_resolve_unit_metadata_helper() -> None:
    """_install_unit() must invoke the exact module-private helper seam.

    The approved 4fm pack freezes one proof seam only: a module-private helper
    in realtime_service.py used by _install_unit(). This guard fails until
    _install_unit() actually calls `_resolve_unit_metadata(...)`.
    """
    module = import_module("modular_simulation.gameplay.realtime_service")
    source = inspect.getsource(module.RealtimeGameService._install_unit)
    assert "_resolve_unit_metadata(" in source, (
        "RealtimeGameService._install_unit() must call the module-private "
        "_resolve_unit_metadata(...) helper as the approved item-aware placement seam."
    )


def test_resolve_unit_metadata_derives_real_holding_tank_ports() -> None:
    """The helper must derive real ports ("inlet",) / ("outlet",) for place_holding_tank.

    The catalog record for place_holding_tank already freezes:
        unit_module = "modular_simulation.unit_processes.storage.holding_tank"
        unit_type   = "HoldingTank"
        constructor_payload = {}

    The HoldingTank implementation declares _PORTS = UnitProcessPorts(
        inlets=("inlet",), outlets=("outlet",)
    ).  The helper must read those real ports from the unit rather than forcing
    the generic ("in",) / ("out",) that _install_unit() currently hard-codes.
    """
    helper = _resolve_unit_metadata_helper()
    catalog = build_sandbox_catalog()
    item = catalog["place_holding_tank"]

    result = helper(item)

    # result must expose inlet_ports and outlet_ports (attribute or mapping access)
    as_mapping = result if isinstance(result, Mapping) else None

    def _get(name: str) -> Any:
        if as_mapping is not None:
            return as_mapping[name]
        return getattr(result, name)

    inlet_ports = tuple(_get("inlet_ports"))
    outlet_ports = tuple(_get("outlet_ports"))

    assert inlet_ports == ("inlet",), (
        f"place_holding_tank inlet_ports should be ('inlet',), got {inlet_ports!r}. "
        "The helper must read real declared ports from the unit implementation, not "
        "hard-code generic ('in',)."
    )
    assert outlet_ports == ("outlet",), (
        f"place_holding_tank outlet_ports should be ('outlet',), got {outlet_ports!r}. "
        "The helper must read real declared ports from the unit implementation, not "
        "hard-code generic ('out',)."
    )


def test_resolve_unit_metadata_preserves_constructor_payload_for_quality_control_lab() -> None:
    """The helper must preserve constructor_payload exactly from the catalog record.

    place_quality_control_lab freezes constructor_payload =
    {"minimum_purity_mol_fraction": 0.95}.  This payload is runtime-authoritative
    metadata: the helper must pass it through unchanged alongside unit_module and
    unit_type, even though no current start exposes this item.

    This is the non-public metadata proof case: it must NOT require widening
    SUPPORTED_BUILD_ITEM_IDS or any start allowlist.
    """
    helper = _resolve_unit_metadata_helper()
    catalog = build_sandbox_catalog()
    item = catalog["place_quality_control_lab"]

    result = helper(item)

    as_mapping = result if isinstance(result, Mapping) else None

    def _get(name: str) -> Any:
        if as_mapping is not None:
            return as_mapping[name]
        return getattr(result, name)

    constructor_payload = _get("constructor_payload")
    assert constructor_payload == {"minimum_purity_mol_fraction": 0.95}, (
        f"constructor_payload for place_quality_control_lab should be "
        f"{{'minimum_purity_mol_fraction': 0.95}}, got {constructor_payload!r}. "
        "The helper must preserve constructor_payload exactly from the catalog record."
    )

    # Verify unit_module and unit_type are also present.
    unit_module = _get("unit_module")
    unit_type = _get("unit_type")
    assert isinstance(unit_module, str) and unit_module, (
        "helper result must include a non-empty unit_module string"
    )
    assert isinstance(unit_type, str) and unit_type, (
        "helper result must include a non-empty unit_type string"
    )


def test_resolve_unit_metadata_returns_unit_declared_ports_not_single_in_out_assumption() -> None:
    """The helper must not freeze single-inlet/single-outlet as a general rule.

    The HoldingTank proof case happens to be single-inlet/single-outlet, but the
    seam must remain general.  This test verifies that the helper reads ports from
    the actual unit implementation (UnitProcessPorts) rather than returning a
    hard-coded single-inlet/single-outlet shape from a lookup table.

    Concretely: the helper called with the place_holding_tank catalog record must
    return exactly what the HoldingTank.ports property declares — no more, no fewer.
    """
    helper = _resolve_unit_metadata_helper()
    catalog = build_sandbox_catalog()
    item = catalog["place_holding_tank"]

    result = helper(item)

    as_mapping = result if isinstance(result, Mapping) else None

    def _get(name: str) -> Any:
        if as_mapping is not None:
            return as_mapping[name]
        return getattr(result, name)

    # Import the real HoldingTank to read what ports it actually declares.
    holding_tank_module = import_module("modular_simulation.unit_processes.storage.holding_tank")
    HoldingTank = getattr(holding_tank_module, "HoldingTank")
    real_ports = HoldingTank().ports

    assert tuple(_get("inlet_ports")) == tuple(real_ports.inlets), (
        "Helper must derive inlet_ports from the unit's declared ports, not a hard-coded rule."
    )
    assert tuple(_get("outlet_ports")) == tuple(real_ports.outlets), (
        "Helper must derive outlet_ports from the unit's declared ports, not a hard-coded rule."
    )


def test_resolve_unit_metadata_instantiates_unit_class_with_constructor_payload() -> None:
    """The helper must pass constructor_payload kwargs when instantiating the unit class.

    This is the payload-instantiation proof: the helper must call ``unit_cls(**payload)``
    rather than ``unit_cls()`` (no-args).  Proved by intercepting the module import inside
    _resolve_unit_metadata and asserting the class is called with the constructor_payload
    kwargs during port derivation.

    Uses place_quality_control_lab because its catalog record has a non-empty
    constructor_payload = {"minimum_purity_mol_fraction": 0.95}.
    """
    helper = _resolve_unit_metadata_helper()
    catalog = build_sandbox_catalog()
    item = catalog["place_quality_control_lab"]

    realtime_module = import_module("modular_simulation.gameplay.realtime_service")

    # Build a fake unit instance with a .ports attribute so the helper can complete.
    from modular_simulation.thermodynamics.algebraic_process_model import UnitProcessPorts

    fake_ports = UnitProcessPorts(inlets=("inlet",), outlets=("reject_outlet",))
    fake_instance = MagicMock()
    fake_instance.ports = fake_ports

    # The fake unit class: records every call's kwargs for later assertion.
    call_records: list[dict[str, Any]] = []

    class _RecordingClass:
        def __new__(cls, **kwargs: Any) -> Any:  # type: ignore[override]
            call_records.append(dict(kwargs))
            return fake_instance

    # Build a fake module whose attribute lookup for "QualityControlLab" returns the spy.
    fake_mod = MagicMock()
    fake_mod.QualityControlLab = _RecordingClass

    with patch.object(realtime_module, "_import_module", return_value=fake_mod):
        helper(item)

    assert len(call_records) >= 1, (
        "unit_cls must have been instantiated at least once during port derivation."
    )
    last_kwargs = call_records[-1]
    expected_payload: dict[str, Any] = {"minimum_purity_mol_fraction": 0.95}
    for key, value in expected_payload.items():
        assert key in last_kwargs, (
            f"constructor_payload key {key!r} must be passed to unit_cls() during "
            f"instantiation; got kwargs {last_kwargs!r}.  "
            f"The helper must call unit_cls(**constructor_payload), not unit_cls()."
        )
        assert last_kwargs[key] == value, (
            f"constructor_payload[{key!r}] must be {value!r}; got {last_kwargs[key]!r}."
        )


# ---------------------------------------------------------------------------
# Frozen live-surface guards (must remain GREEN before and after Wave 2)
# ---------------------------------------------------------------------------


def test_supported_build_item_ids_remains_exactly_frozen_live_set() -> None:
    """SUPPORTED_BUILD_ITEM_IDS must stay exactly ("place_heater_cooler",
    "place_flash_drum", "build_process_line") — unchanged by the staging work.

    place_holding_tank and place_quality_control_lab must NOT appear here.
    """
    module = import_module("modular_simulation.gameplay.realtime_service")
    supported = tuple(module.SUPPORTED_BUILD_ITEM_IDS)
    assert supported == (
        "place_heater_cooler",
        "place_flash_drum",
        "build_process_line",
    ), (
        f"SUPPORTED_BUILD_ITEM_IDS changed; got {supported!r}. "
        "This constant must remain frozen throughout the staging work."
    )


def test_public_realtime_service_method_set_is_unchanged() -> None:
    """The public realtime-service method set must remain exactly the frozen set.

    No new public methods (e.g. 'purge_tank', 'place_tank') may be added by the
    staging work.  The module-private placement helper must stay non-public.
    """
    module = import_module("modular_simulation.gameplay.realtime_service")
    actual_public_methods = tuple(
        sorted(
            name
            for name in dir(module)
            if not name.startswith("_")
            and inspect.isfunction(getattr(module, name, None))
            and getattr(module, name).__module__ == module.__name__
        )
    )
    expected_public_methods = tuple(sorted(REQUIRED_SERVICE_METHODS))
    assert actual_public_methods == expected_public_methods, (
        f"Public method set changed; expected {expected_public_methods!r}, "
        f"got {actual_public_methods!r}."
    )


# ---------------------------------------------------------------------------
# Wave 3 — RED guards: build-path metadata-resolution failure translation
#
# These tests prove that _install_unit() is the explicit translation boundary
# for qualifying metadata-resolution failures.  All three failure modes
# (missing module, missing unit type, bad constructor payload) must be
# translated into SandboxRequestError(error_code="invalid_config", ...).
#
# The tests use the module-private _resolve_unit_metadata helper seam and
# a crafted SandboxCatalogItemDefinition to inject each failure mode.
# ---------------------------------------------------------------------------


def _make_fake_unit_blueprint_item(default_config: dict[str, object]) -> Any:
    """Build a minimal SandboxCatalogItemDefinition with apply_kind='add_process'."""
    from modular_simulation.gameplay.contracts import SandboxCatalogItemDefinition

    return SandboxCatalogItemDefinition(
        item_id="__test_item__",
        title="Test item",
        item_kind="unit_blueprint",
        apply_kind="add_process",
        default_config=default_config,
        required_user_inputs=("process_id",),
        supported_start_ids=(),
        educational_summary="Test only",
    )


def test_install_unit_translates_missing_module_to_invalid_config_error() -> None:
    """_install_unit() must translate ModuleNotFoundError from metadata resolution.

    When the catalog record references a unit_module that cannot be imported,
    _resolve_unit_metadata raises ModuleNotFoundError.  _install_unit() must
    catch this and re-raise SandboxRequestError(error_code="invalid_config", ...)
    rather than letting the raw ModuleNotFoundError escape to callers.
    """
    realtime_module = import_module("modular_simulation.gameplay.realtime_service")
    error_type = _sandbox_error_type()

    service = realtime_module.RealtimeGameService()
    created = service.create_session(mode_id="phase1_process_sandbox_v1")
    session_id = _field(created, "session_id")
    active = service._active_session  # type: ignore[attr-defined]

    bad_item = _make_fake_unit_blueprint_item(
        {
            "unit_module": "modular_simulation.unit_processes.__does_not_exist__",
            "unit_type": "SomeUnit",
            "constructor_payload": {},
        }
    )

    with pytest.raises(error_type) as exc_info:
        service._install_unit(active=active, process_id="test_proc", item=bad_item)  # type: ignore[attr-defined]

    assert exc_info.value.error_code == "invalid_config", (
        f"Missing-module failure must produce error_code='invalid_config'; "
        f"got {exc_info.value.error_code!r}.  "
        "_install_unit() must be the translation boundary for metadata-resolution failures."
    )


def test_install_unit_translates_missing_unit_type_to_invalid_config_error() -> None:
    """_install_unit() must translate AttributeError from a missing unit type.

    When unit_module imports successfully but unit_type does not exist as an
    attribute, _resolve_unit_metadata raises AttributeError.  _install_unit()
    must translate this into SandboxRequestError(error_code="invalid_config", ...).
    """
    realtime_module = import_module("modular_simulation.gameplay.realtime_service")
    error_type = _sandbox_error_type()

    service = realtime_module.RealtimeGameService()
    created = service.create_session(mode_id="phase1_process_sandbox_v1")
    active = service._active_session  # type: ignore[attr-defined]

    # Use a real importable module but a unit_type that doesn't exist in it.
    bad_item = _make_fake_unit_blueprint_item(
        {
            "unit_module": "modular_simulation.unit_processes.thermal.heater_cooler",
            "unit_type": "__DoesNotExistUnit__",
            "constructor_payload": {},
        }
    )

    with pytest.raises(error_type) as exc_info:
        service._install_unit(active=active, process_id="test_proc2", item=bad_item)  # type: ignore[attr-defined]

    assert exc_info.value.error_code == "invalid_config", (
        f"Missing-unit-type failure must produce error_code='invalid_config'; "
        f"got {exc_info.value.error_code!r}.  "
        "_install_unit() must be the translation boundary for missing exported unit types."
    )


def test_install_unit_translates_constructor_payload_failure_to_invalid_config_error() -> None:
    """_install_unit() must translate constructor payload failures.

    When unit_cls(**constructor_payload) raises TypeError or ValueError because
    the payload does not match the constructor signature, _resolve_unit_metadata
    propagates the raw exception.  _install_unit() must translate it into
    SandboxRequestError(error_code="invalid_config", ...).
    """
    realtime_module = import_module("modular_simulation.gameplay.realtime_service")
    error_type = _sandbox_error_type()

    service = realtime_module.RealtimeGameService()
    created = service.create_session(mode_id="phase1_process_sandbox_v1")
    active = service._active_session  # type: ignore[attr-defined]

    # HeaterCooler does NOT accept 'nonexistent_kwarg'; this causes TypeError.
    bad_item = _make_fake_unit_blueprint_item(
        {
            "unit_module": "modular_simulation.unit_processes.thermal.heater_cooler",
            "unit_type": "HeaterCooler",
            "constructor_payload": {"nonexistent_kwarg": "bad_value"},
        }
    )

    with pytest.raises(error_type) as exc_info:
        service._install_unit(active=active, process_id="test_proc3", item=bad_item)  # type: ignore[attr-defined]

    assert exc_info.value.error_code == "invalid_config", (
        f"Constructor-payload failure must produce error_code='invalid_config'; "
        f"got {exc_info.value.error_code!r}.  "
        "_install_unit() must be the translation boundary for constructor payload failures."
    )


def test_build_route_returns_invalid_config_on_metadata_resolution_failure() -> None:
    """The public build() path must return SandboxRequestError(invalid_config)
    when metadata resolution fails, not a raw internal exception.

    This end-to-end test ensures the full build() → _install_unit() → _resolve_unit_metadata
    chain translates the failure before it reaches the caller.  Uses patch to inject
    a _MetadataResolutionError from _resolve_unit_metadata so the test is isolated from
    actual module availability.

    Under the internal-sentinel design, _install_unit() catches _MetadataResolutionError
    (not raw exception families), so the patch must inject the sentinel.
    """
    realtime_module = import_module("modular_simulation.gameplay.realtime_service")
    error_type = _sandbox_error_type()

    # Access the module-private sentinel class.
    MetadataResolutionError = getattr(realtime_module, "_MetadataResolutionError")

    service = realtime_module.RealtimeGameService()
    created = service.create_session(mode_id="phase1_process_sandbox_v1")
    session_id = _field(created, "session_id")

    # Inject a _MetadataResolutionError from _resolve_unit_metadata to simulate
    # a corrupt catalog entry (e.g. missing module target).
    with patch.object(
        realtime_module,
        "_resolve_unit_metadata",
        side_effect=MetadataResolutionError("injected missing module sentinel"),
    ):
        with pytest.raises(error_type) as exc_info:
            service.build(
                session_id=session_id,
                item_id="place_heater_cooler",
                config={"process_id": "heater_test"},
                layout={"anchor_xy": (0.0, 0.0)},
            )

    assert exc_info.value.error_code == "invalid_config", (
        f"build() must translate _MetadataResolutionError from _resolve_unit_metadata "
        f"into SandboxRequestError(error_code='invalid_config'); "
        f"got {exc_info.value.error_code!r}."
    )


def test_install_unit_does_not_translate_unrelated_exception_to_invalid_config() -> None:
    """_install_unit() must NOT translate unrelated exceptions from _resolve_unit_metadata.

    An unrelated exception such as RuntimeError injected from _resolve_unit_metadata
    must propagate unchanged — not be silently masked as 'invalid_config'.

    This guard enforces the narrow seam: broad Exception masking is not allowed.
    """
    realtime_module = import_module("modular_simulation.gameplay.realtime_service")
    error_type = _sandbox_error_type()

    service = realtime_module.RealtimeGameService()
    created = service.create_session(mode_id="phase1_process_sandbox_v1")
    active = service._active_session  # type: ignore[attr-defined]

    # Use a real catalog item so we reach _resolve_unit_metadata patching.
    catalog = build_sandbox_catalog()
    item = catalog["place_heater_cooler"]

    unrelated_error = RuntimeError("unexpected internal failure — must not be masked")

    with patch.object(
        realtime_module,
        "_resolve_unit_metadata",
        side_effect=unrelated_error,
    ):
        with pytest.raises(RuntimeError) as exc_info:
            service._install_unit(active=active, process_id="test_proc_unrelated", item=item)  # type: ignore[attr-defined]

    assert exc_info.value is unrelated_error, (
        "_install_unit() must NOT translate an unrelated RuntimeError from "
        "_resolve_unit_metadata into SandboxRequestError(invalid_config). "
        "Only approved metadata-resolution failures may be translated."
    )
    # Also assert no SandboxRequestError was raised instead.
    assert not isinstance(exc_info.value, error_type), (
        "The unrelated RuntimeError must NOT be wrapped as a SandboxRequestError."
    )


def test_resolve_unit_metadata_does_not_translate_import_side_effect_module_not_found() -> None:
    """_resolve_unit_metadata must NOT translate import-side-effect ModuleNotFoundError.

    If an otherwise valid module successfully starts loading but then fails because
    one of ITS OWN dependencies is missing (import side-effect), the resulting
    ModuleNotFoundError should NOT be translated to invalid_config.  Only
    ModuleNotFoundError for the target module itself (unit_module) qualifies
    as a metadata-resolution failure.

    This regression guard proves the sentinel design is narrow: a
    ModuleNotFoundError whose .name is NOT the target unit_module must escape
    as-is and must NOT be caught and re-raised as SandboxRequestError(invalid_config).
    """
    realtime_module = import_module("modular_simulation.gameplay.realtime_service")
    error_type = _sandbox_error_type()

    service = realtime_module.RealtimeGameService()
    created = service.create_session(mode_id="phase1_process_sandbox_v1")
    active = service._active_session  # type: ignore[attr-defined]

    # A real importable module with a unit that actually exists — so unit_module itself
    # is valid. We simulate that this module's own dependency "some_missing_dep" fails.
    valid_unit_module = "modular_simulation.unit_processes.thermal.heater_cooler"
    item = _make_fake_unit_blueprint_item(
        {
            "unit_module": valid_unit_module,
            "unit_type": "HeaterCooler",
            "constructor_payload": {},
        }
    )

    # Inject a ModuleNotFoundError whose .name is a *different* module (side-effect dep),
    # not the target unit_module.  This simulates a valid module whose dependency fails.
    side_effect_dep_name = "some_missing_side_effect_dependency"
    side_effect_error = ModuleNotFoundError(
        f"No module named {side_effect_dep_name!r}",
        name=side_effect_dep_name,
    )

    with patch.object(
        realtime_module,
        "_import_module",
        side_effect=side_effect_error,
    ):
        with pytest.raises(ModuleNotFoundError) as exc_info:
            service._install_unit(active=active, process_id="test_proc_side_effect", item=item)  # type: ignore[attr-defined]

    assert exc_info.value is side_effect_error, (
        "A ModuleNotFoundError caused by an import side-effect inside an otherwise "
        "valid module (i.e. exc.name != unit_module) must NOT be caught and translated "
        "to SandboxRequestError(invalid_config).  It must propagate unchanged."
    )
    assert not isinstance(exc_info.value, error_type), (
        "Import side-effect ModuleNotFoundError must NOT become a SandboxRequestError."
    )
