from __future__ import annotations

# pyright: reportMissingTypeStubs=false, reportMissingImports=false, reportUnknownMemberType=false

"""Red tests for HoldingTank — Wave 1, Task 1.3.

All tests in this module are expected to FAIL before the HoldingTank
implementation exists (import error or AttributeError on unimplemented
attributes).  They define the observable boundaries that the implementation
must satisfy.
"""

import pytest
from modular_simulation.unit_processes.storage.holding_tank import HoldingTank  # type: ignore[import]
from modular_simulation.thermodynamics.stream import StreamData


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_tank(**kwargs: object) -> HoldingTank:
    """Construct a HoldingTank with sensible defaults for unit tests."""
    defaults: dict[str, object] = {}
    defaults.update(kwargs)
    return HoldingTank(**defaults)  # type: ignore[call-arg]


# ---------------------------------------------------------------------------
# Port shape contract
# ---------------------------------------------------------------------------


def test_holding_tank_has_exactly_one_inlet() -> None:
    """HoldingTank must expose exactly one inlet port named 'inlet'."""
    tank = _make_tank()
    assert tank.ports.inlets == ("inlet",)


def test_holding_tank_has_exactly_one_outlet() -> None:
    """HoldingTank must expose exactly one outlet port named 'outlet'."""
    tank = _make_tank()
    assert tank.ports.outlets == ("outlet",)


# ---------------------------------------------------------------------------
# Holdup accumulation
# ---------------------------------------------------------------------------


def test_holding_tank_accumulates_holdup_across_advance() -> None:
    """Incoming molar flow must increase the stored internal holdup each step.

    After one advance with positive inlet flow the holdup must be strictly
    greater than zero.
    """
    tank = _make_tank(inlet_flow=5.0, inlet_temperature=300.0, inlet_pressure=101325.0)
    dt = 1.0  # seconds
    holdup_before = float(tank.holdup_mol)

    tank.step(dt)

    assert float(tank.holdup_mol) > holdup_before


def test_holding_tank_holdup_is_non_negative_after_positive_inlet_step() -> None:
    """Holdup must remain non-negative after advancing with a positive inlet flow.

    After one step with inlet_flow > 0, holdup_mol must be >= 0.  This is a
    weak lower-bound: it confirms the accumulation path does not produce
    nonsense negative inventories.
    """
    inlet_flow = 3.0  # mol/s
    dt = 1.0  # seconds

    tank = _make_tank(inlet_flow=inlet_flow, inlet_temperature=300.0, inlet_pressure=101325.0)
    tank.step(dt)

    assert float(tank.holdup_mol) >= 0.0


# ---------------------------------------------------------------------------
# Material conservation: outlet may not invent material
# ---------------------------------------------------------------------------


def test_holding_tank_outlet_cannot_exceed_available_holdup() -> None:
    """Outlet flow must never exceed available holdup in the same simulated step.

    Start with zero holdup and zero inlet; after one step the outlet flow
    must also be zero.
    """
    tank = _make_tank(inlet_flow=0.0, inlet_temperature=300.0, inlet_pressure=101325.0)
    # Ensure holdup starts empty.
    assert float(tank.holdup_mol) == pytest.approx(0.0)

    tank.step(1.0)

    assert float(tank.outlet_flow) == pytest.approx(0.0)


def test_holding_tank_zero_holdup_yields_zero_outlet_flow() -> None:
    """Zero stored holdup must produce zero outlet flow regardless of inlet.

    This is the core 'cannot invent material' invariant.
    """
    tank = _make_tank(inlet_flow=0.0, inlet_temperature=300.0, inlet_pressure=101325.0)

    # holdup_mol must be 0.0 at construction with no stored material.
    assert float(tank.holdup_mol) == pytest.approx(0.0)

    tank.step(0.1)

    assert float(tank.outlet_flow) == pytest.approx(0.0)


def test_holding_tank_outlet_flow_is_bounded_by_holdup_available_at_step_start() -> None:
    """With zero inlet and non-zero stored holdup, discharge for the step must
    not exceed the holdup available at the start of that step.

    This proves the frozen contract without imposing any extra same-step
    discharge timing rule on how newly arrived material may be handled.
    """
    tank_a = _make_tank(inlet_flow=10.0, inlet_temperature=300.0, inlet_pressure=101325.0)
    assert float(tank_a.holdup_mol) == pytest.approx(0.0)

    tank_a.step(1.0)

    # Advance again with zero inlet. The outlet flow for this second step must
    # not exceed the holdup that was available at the start of the step.
    holdup_at_start_of_b = float(tank_a.holdup_mol)
    assert holdup_at_start_of_b > 0.0

    tank_a.inlet_flow = 0.0  # type: ignore[assignment]
    tank_a.step(1.0)

    outlet_in_b = float(tank_a.outlet_flow)
    assert outlet_in_b >= 0.0
    assert outlet_in_b <= holdup_at_start_of_b + 1e-9  # outlet cannot exceed available holdup


def test_holding_tank_zero_inlet_discharge_uses_stored_material_state() -> None:
    """Discharging stored holdup with zero inlet must use stored state.

    The second step discharges holdup that was stored in the first step.
    Even if the current inlet carries placeholder state, outlet state for the
    discharge step must match the stored material state.
    """
    tank = _make_tank()

    stored_stream = StreamData(
        temperature=320.0,
        pressure=180_000.0,
        mole_fractions=(0.2, 0.8),
        molar_flow_rate=4.0,
    )
    tank.apply_inlet("inlet", stored_stream)
    tank.step(2.0)

    placeholder_stream = StreamData(
        temperature=500.0,
        pressure=90_000.0,
        mole_fractions=(1.0,),
        molar_flow_rate=0.0,
    )
    tank.apply_inlet("inlet", placeholder_stream)
    tank.step(2.0)

    outlet = tank.get_outlet_stream("outlet")
    assert outlet.molar_flow_rate == pytest.approx(4.0)
    assert outlet.temperature == pytest.approx(320.0)
    assert outlet.pressure == pytest.approx(180_000.0)
    assert outlet.mole_fractions == pytest.approx((0.2, 0.8))


# ---------------------------------------------------------------------------
# Hydraulic participation
# ---------------------------------------------------------------------------


def test_holding_tank_declares_explicit_hydraulic_participation() -> None:
    """HoldingTank must expose a non-None hydraulic_participation with the
    exact port spec required for a connected-network compile without relying
    on undeclared passive-port inference.

    The spec must include:
    - pressure_state ports for 'inlet' and 'outlet',
    - at least one balancing group covering ('inlet', 'outlet').
    """
    tank = _make_tank()

    hp = tank.hydraulic_participation

    assert hp is not None
    assert "inlet" in hp.ports
    assert "outlet" in hp.ports
    assert hp.ports["inlet"].role == "pressure_state"
    assert hp.ports["outlet"].role == "pressure_state"
    assert hp.ports["inlet"].pressure_state is not None
    assert hp.ports["outlet"].pressure_state is not None


def test_holding_tank_hydraulic_participation_has_inlet_outlet_balancing_group() -> None:
    """The balancing group must span both 'inlet' and 'outlet' so the hydraulic
    solver can emit the required flow-balance equation for the unit.
    """
    tank = _make_tank()
    hp = tank.hydraulic_participation

    assert hp is not None
    groups = hp.balancing_groups
    assert len(groups) >= 1
    group_port_sets = [set(g.ports) for g in groups]
    assert {"inlet", "outlet"} in group_port_sets


def test_holding_tank_hydraulic_participation_has_exactly_one_balancing_group() -> None:
    """The spec freezes exactly one balancing group over (inlet, outlet).

    No additional groups are permitted: exactly one group, and it must span
    both 'inlet' and 'outlet'.
    """
    tank = _make_tank()
    hp = tank.hydraulic_participation

    assert hp is not None
    groups = hp.balancing_groups
    assert len(groups) == 1
    assert set(groups[0].ports) == {"inlet", "outlet"}


# ---------------------------------------------------------------------------
# Connected-network compile proof
# ---------------------------------------------------------------------------


def test_holding_tank_same_step_inflow_supports_same_step_withdrawal() -> None:
    """Inflow arriving in the same step may support an equal withdrawal.

    An empty tank receiving 10 mol/s inlet and a requested outlet demand of
    10 mol/s over 1 second must:
    - produce a positive outlet flow (material flows through),
    - leave holdup >= 0 (conservation is not violated).

    This is the same-step timing rule the spec explicitly allows: the ODE
    integration sees the inlet throughout the step, so the bulk inventory
    is transiently non-zero and can support the simultaneous draw.
    """
    tank = _make_tank(inlet_flow=10.0, inlet_temperature=300.0, inlet_pressure=101325.0)
    tank.apply_requested_outlet_through_flow_demand("outlet", 10.0)
    assert float(tank.holdup_mol) == pytest.approx(0.0)

    tank.step(1.0)

    assert float(tank.outlet_flow) > 0.0
    assert float(tank.holdup_mol) >= 0.0


def test_holding_tank_requested_outlet_is_capped_by_holdup_plus_same_step_inflow() -> None:
    """Requested outlet demand must not overdraw beyond physically available moles.

    For an empty tank with 10 mol/s inlet over 1 second, the maximum physically
    withdrawable amount in the same step is 10 mol. A 20 mol/s requested demand
    must therefore be capped to <= 10 mol/s realized outlet.
    """
    tank = _make_tank(inlet_flow=10.0, inlet_temperature=300.0, inlet_pressure=101325.0)
    tank.apply_requested_outlet_through_flow_demand("outlet", 20.0)
    assert float(tank.holdup_mol) == pytest.approx(0.0)

    tank.step(1.0)

    assert float(tank.outlet_flow) <= 10.0 + 1e-6
    assert float(tank.holdup_mol) >= 0.0


def test_holding_tank_empty_pass_through_uses_inlet_temperature_and_pressure() -> None:
    """Near-empty pass-through must expose inlet T/P, not stale stored bulk T/P."""
    tank = _make_tank(inlet_flow=5.0, inlet_temperature=355.0, inlet_pressure=155000.0)
    tank.apply_requested_outlet_through_flow_demand("outlet", 5.0)

    # Keep the tank in pass-through mode (near-empty with balanced in/out).
    assert float(tank.holdup_mol) == pytest.approx(0.0)
    tank.step(1.0)

    outlet = tank.get_outlet_stream("outlet")
    assert outlet.temperature == pytest.approx(355.0)
    assert outlet.pressure == pytest.approx(155000.0)


def test_holding_tank_compiles_as_ordinary_connected_process_node() -> None:
    """HoldingTank must compile successfully as an ordinary two-port process
    node in a minimal feed → tank → sink flowsheet.

    This proves that explicit hydraulic participation is correctly declared
    and accepted by the hydraulic compile lifecycle without hidden topology
    exceptions.
    """
    from modular_simulation.connection.runtime.connected_plant_orchestrator import (
        ConnectedPlantOrchestrator,
    )
    from modular_simulation.flowsheet import Flowsheet
    from modular_simulation.thermodynamics.runtime_context import SimulationRuntimeContext

    context = SimulationRuntimeContext.create(species_names=["methane", "ethane"])
    flowsheet = Flowsheet(context=context, dt=0.5)

    tank = HoldingTank()  # type: ignore[call-arg]
    flowsheet.add_unit("tank", tank)
    flowsheet.add_feed_from_values("feed", T=300.0, P=150_000.0, z=(0.7, 0.3), flow=4.0)
    flowsheet.add_sink("product")

    flowsheet.connect("feed", "tank")
    flowsheet.connect("tank", "product")

    plant = flowsheet.compile()

    assert isinstance(plant, ConnectedPlantOrchestrator)


def test_holding_tank_two_step_sequence_does_not_crash_when_inlet_widens_species_dimension() -> (
    None
):
    """Running two macro-steps on a feed→tank→sink flowsheet where the feed carries
    two species must not raise a ValueError on step 2.

    Regression for: runtime transport lag cache retains stale 1-species composition
    after step 1 caches the initial (1-species default) edge state.  On step 2 the
    advected state reflects the now-2-species tank outlet, causing
    ``_update_lag_transport_state`` to raise
    ``ValueError: current_state and advected_state composition lengths must match``.

    The fix must be in the runtime transport-state resolution path, not in HoldingTank.
    """
    from modular_simulation.flowsheet import Flowsheet
    from modular_simulation.thermodynamics.runtime_context import SimulationRuntimeContext

    # HoldingTank defaults to 1 species; the feed carries 2 species.
    # Step 1: boundary propagation widens the tank to 2 species at the end of the step.
    # Step 2: transport step sees 2-species advected state but (before the fix) a
    #         stale 1-species cached lag state, triggering the length mismatch error.
    context = SimulationRuntimeContext.create(species_names=["methane", "ethane"])
    flowsheet = Flowsheet(context=context, dt=1.0)

    tank = HoldingTank()  # type: ignore[call-arg]
    flowsheet.add_unit("tank", tank)
    flowsheet.add_feed_from_values("feed", T=300.0, P=150_000.0, z=(0.6, 0.4), flow=5.0)
    flowsheet.add_sink("sink")
    flowsheet.connect("feed", "tank")
    flowsheet.connect("tank", "sink")

    plant = flowsheet.compile()

    # Step 1 must succeed.
    _ = plant.step(macro_step_time_s=1.0)

    # Step 2 must also succeed (before the fix this raises ValueError).
    _ = plant.step(macro_step_time_s=1.0)


def test_holding_tank_published_measurements_are_all_numeric_after_species_widening() -> None:
    """After a HoldingTank widens species dimension (step 1 with a 2-species feed),
    get_observability_observables() must return a published_measurements mapping
    whose values are all plain Python floats (not ndarrays).

    Regression for: _derive_publication_map() includes array-valued states
    (holdup_component_moles, outlet_composition) in the publication map, and
    Subsystem._make_publication_value_getter() calls float(source_getter()).
    After the tank widens to 2 species, float(ndarray_of_shape_2) raises
    TypeError: only length-1 arrays can be converted to Python scalars.
    """
    from modular_simulation.connection.runtime.connected_plant_orchestrator import (
        ConnectedPlantOrchestrator,
    )
    from modular_simulation.flowsheet import Flowsheet
    from modular_simulation.thermodynamics.runtime_context import SimulationRuntimeContext

    context = SimulationRuntimeContext.create(species_names=["methane", "ethane"])
    flowsheet = Flowsheet(context=context, dt=1.0)

    tank = HoldingTank()  # type: ignore[call-arg]
    flowsheet.add_unit("tank", tank)
    flowsheet.add_feed_from_values("feed", T=300.0, P=150_000.0, z=(0.6, 0.4), flow=5.0)
    flowsheet.add_sink("sink")
    flowsheet.connect("feed", "tank")
    flowsheet.connect("tank", "sink")

    plant = flowsheet.compile()
    assert isinstance(plant, ConnectedPlantOrchestrator)

    # Step 1 widens the tank from 1-species default to 2 species.
    _ = plant.step(macro_step_time_s=1.0)

    # Reading observability after species widening must not raise TypeError.
    # Before the fix this crashes:
    #   TypeError: only length-1 arrays can be converted to Python scalars
    observables = plant.get_observability_observables()

    published_measurements = observables["published_measurements"]
    # Every value must be a plain float, not an ndarray.
    for tag, value in published_measurements.items():
        assert isinstance(value, float), (
            f"published_measurements['{tag}'] is {type(value).__name__}, expected float"
        )

    # Array-shaped states must NOT appear in published_measurements.
    assert not any("component_moles" in tag for tag in published_measurements), (
        "holdup_component_moles (ndarray) must not appear in published_measurements"
    )
    assert not any("composition" in tag and "tank" in tag for tag in published_measurements), (
        "outlet_composition (ndarray) must not appear in published_measurements"
    )
