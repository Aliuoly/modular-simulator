from __future__ import annotations

# pyright: reportMissingImports=false, reportUnknownVariableType=false, reportUnknownMemberType=false, reportUnknownParameterType=false, reportMissingParameterType=false, reportUnknownArgumentType=false

from types import MappingProxyType

import numpy as np
import pytest

from modular_simulation.flowsheet import Flowsheet
from modular_simulation.connection.hydraulics.hydraulic_compile import (
    CompiledHydraulicGraph,
    HydraulicCompileLifecycle,
)
from modular_simulation.connection.hydraulics.hydraulic_element import (
    CanonicalNodePressureHydraulicElement,
    PipeHydraulicElement,
)
from modular_simulation.connection.hydraulics.hydraulic_solver import (
    ElementEquation,
    HydraulicPressureAnchorMetadata,
    HydraulicSystemDefinition,
    HydraulicTopologyLookup,
    LinearResidualEquation,
    build_index_maps,
)
from modular_simulation.connection.topology.network import ConnectionNetwork
from modular_simulation.thermodynamics.runtime_context import SimulationRuntimeContext
from modular_simulation.thermodynamics.hydraulic_participation import (
    HydraulicBalancingGroupSpec,
    HydraulicElementCouplingSpec,
    HydraulicIndexedStateRef,
    HydraulicParticipationSpec,
    HydraulicPortSpec,
    HydraulicRelationSpec,
    HydraulicScalarStateRef,
)
from modular_simulation.unit_processes import CSTR
from modular_simulation.unit_processes import FlashDrum
from modular_simulation.unit_processes import HeaterCooler
from modular_simulation.unit_processes.flow.pump import Pump
from modular_simulation.unit_processes.mixing.mixer import Mixer
from modular_simulation.unit_processes.separation.splitter import Splitter


def _linear_equation(
    residual_name: str,
    coefficients: dict[str, float],
    *,
    constant: float = 0.0,
) -> LinearResidualEquation:
    return LinearResidualEquation(
        residual_name=residual_name,
        coefficients=MappingProxyType(coefficients),
        constant=constant,
    )


def _install_hydraulic_participation_property(
    monkeypatch: pytest.MonkeyPatch,
    cls: type[object],
    getter,
) -> None:
    monkeypatch.setattr(cls, "hydraulic_participation", property(getter), raising=False)


def _linear_topology_system() -> HydraulicSystemDefinition:
    return HydraulicSystemDefinition(
        equations=(),
        linear_residual_equations=(
            _linear_equation("ref_upstream", {"pressure_upstream": 1.0}, constant=-120_000.0),
            _linear_equation(
                "head_balance",
                {"pressure_upstream": 1.0, "pressure_downstream": -1.0, "flow_linear": -1.0},
            ),
            _linear_equation("flow_target", {"flow_linear": 1.0}, constant=-50.0),
        ),
    )


def _branch_topology_system() -> HydraulicSystemDefinition:
    return HydraulicSystemDefinition(
        equations=(),
        linear_residual_equations=(
            _linear_equation("ref_mix", {"pressure_mix": 1.0}, constant=-110_000.0),
            _linear_equation(
                "head_feed_a",
                {"pressure_mix": 1.0, "flow_feed_a": -1.0},
                constant=-100_000.0,
            ),
            _linear_equation(
                "head_feed_b",
                {"pressure_mix": 1.0, "flow_feed_b": -1.0},
                constant=-95_000.0,
            ),
            _linear_equation(
                "mass_balance",
                {"flow_feed_a": 1.0, "flow_feed_b": 1.0, "flow_outlet": -1.0},
            ),
        ),
    )


def _feed_unit_junction_topology_system() -> HydraulicSystemDefinition:
    return HydraulicSystemDefinition(
        equations=(),
        linear_residual_equations=(
            _linear_equation(
                "feed_a_anchor",
                {"pressure__boundary_feed_a_outlet": 1.0},
                constant=-135_000.0,
            ),
            _linear_equation(
                "feed_b_anchor",
                {"pressure__boundary_feed_b_outlet": 1.0},
                constant=-128_000.0,
            ),
            _linear_equation(
                "unit_anchor",
                {"pressure__process_reactor_feed": 1.0},
                constant=-120_000.0,
            ),
            _linear_equation(
                "purge_anchor",
                {"pressure__boundary_purge_inlet": 1.0},
                constant=-122_000.0,
            ),
            _linear_equation(
                "head_feed_a",
                {
                    "pressure__boundary_feed_a_outlet": 1.0,
                    "pressure__junction_mix": -1.0,
                    "edge_feed_a": -1.0,
                },
            ),
            _linear_equation(
                "head_feed_b",
                {
                    "pressure__boundary_feed_b_outlet": 1.0,
                    "pressure__junction_mix": -1.0,
                    "edge_feed_b": -2.0,
                },
            ),
            _linear_equation(
                "head_unit",
                {
                    "pressure__junction_mix": 1.0,
                    "pressure__process_reactor_feed": -1.0,
                    "edge_unit": -1.0,
                },
            ),
            _linear_equation(
                "head_purge",
                {
                    "pressure__junction_mix": 1.0,
                    "pressure__boundary_purge_inlet": -1.0,
                    "edge_purge": -1.0,
                },
            ),
            _linear_equation(
                "pressure__junction_mix__mass_balance",
                {
                    "edge_feed_a": 1.0,
                    "edge_feed_b": 1.0,
                    "edge_purge": -1.0,
                    "edge_unit": -1.0,
                },
            ),
        ),
        topology_lookup=HydraulicTopologyLookup(
            line_flow_unknown_by_line=MappingProxyType(
                {
                    "edge_feed_a": "edge_feed_a",
                    "edge_feed_b": "edge_feed_b",
                    "edge_purge": "edge_purge",
                    "edge_unit": "edge_unit",
                }
            ),
            edge_source_pressure_unknown_by_line=MappingProxyType(
                {
                    "edge_feed_a": "pressure__boundary_feed_a_outlet",
                    "edge_feed_b": "pressure__boundary_feed_b_outlet",
                    "edge_purge": "pressure__junction_mix",
                    "edge_unit": "pressure__junction_mix",
                }
            ),
            edge_target_pressure_unknown_by_line=MappingProxyType(
                {
                    "edge_feed_a": "pressure__junction_mix",
                    "edge_feed_b": "pressure__junction_mix",
                    "edge_purge": "pressure__boundary_purge_inlet",
                    "edge_unit": "pressure__process_reactor_feed",
                }
            ),
            node_pressure_unknown_by_endpoint=MappingProxyType(
                {
                    "feed_a.outlet": "pressure__boundary_feed_a_outlet",
                    "feed_b.outlet": "pressure__boundary_feed_b_outlet",
                    "mix.inlet_a": "pressure__junction_mix",
                    "mix.inlet_b": "pressure__junction_mix",
                    "mix.outlet_purge": "pressure__junction_mix",
                    "mix.outlet_unit": "pressure__junction_mix",
                    "purge.inlet": "pressure__boundary_purge_inlet",
                    "reactor.feed": "pressure__process_reactor_feed",
                }
            ),
            node_pressure_unknown_by_junction=MappingProxyType({"mix": "pressure__junction_mix"}),
        ),
    )


def _recycle_topology_system() -> HydraulicSystemDefinition:
    return HydraulicSystemDefinition(
        equations=(),
        linear_residual_equations=(
            _linear_equation("ref_a", {"pressure_a": 1.0}, constant=-150_000.0),
            _linear_equation(
                "head_recycle",
                {"pressure_a": 1.0, "pressure_b": -1.0, "flow_recycle": -1.0},
            ),
            _linear_equation("recycle_target", {"flow_recycle": 1.0}, constant=-25.0),
        ),
    )


def _disconnected_missing_reference_system() -> HydraulicSystemDefinition:
    return HydraulicSystemDefinition(
        equations=(),
        linear_residual_equations=(
            _linear_equation("ref_a", {"pressure_a": 1.0}, constant=-5.0),
            _linear_equation("balance_a", {"pressure_a": 1.0, "flow_a": -1.0}),
            _linear_equation("balance_b", {"pressure_b": 1.0, "flow_b": -1.0}),
            _linear_equation("mass_b", {"flow_b": 1.0}),
        ),
    )


@pytest.mark.parametrize(
    ("system_factory", "expected_unknowns", "expected_residuals"),
    (
        (
            _linear_topology_system,
            ("flow_linear", "pressure_downstream", "pressure_upstream"),
            ("flow_target", "head_balance", "ref_upstream"),
        ),
        (
            _branch_topology_system,
            ("flow_feed_a", "flow_feed_b", "flow_outlet", "pressure_mix"),
            ("head_feed_a", "head_feed_b", "mass_balance", "ref_mix"),
        ),
        (
            _recycle_topology_system,
            ("flow_recycle", "pressure_a", "pressure_b"),
            ("head_recycle", "recycle_target", "ref_a"),
        ),
    ),
)
def test_compile_bridge_produces_solver_inputs_with_deterministic_orders(
    system_factory,
    expected_unknowns: tuple[str, ...],
    expected_residuals: tuple[str, ...],
) -> None:
    lifecycle = HydraulicCompileLifecycle()
    compiled = lifecycle.compile(system=system_factory(), graph_revision="rev-bridge")

    bridge_inputs = compiled.build_solver_inputs()

    assert bridge_inputs.graph_revision == "rev-bridge"
    assert bridge_inputs.unknown_order == expected_unknowns
    assert bridge_inputs.residual_order == expected_residuals
    assert tuple(bridge_inputs.unknown_index_map) == expected_unknowns
    assert tuple(bridge_inputs.residual_index_map) == expected_residuals


def test_compile_bridge_solution_preserves_declared_unknown_residual_index_order() -> None:
    lifecycle = HydraulicCompileLifecycle()
    compiled = lifecycle.compile(system=_branch_topology_system(), graph_revision="rev-order")

    bridge_inputs = compiled.build_solver_inputs()
    unknown_index_map, residual_index_map = build_index_maps(bridge_inputs.system)

    assert tuple(sorted(unknown_index_map, key=unknown_index_map.__getitem__)) == (
        "flow_feed_a",
        "flow_feed_b",
        "flow_outlet",
        "pressure_mix",
    )
    assert tuple(sorted(residual_index_map, key=residual_index_map.__getitem__)) == (
        "head_feed_a",
        "head_feed_b",
        "mass_balance",
        "ref_mix",
    )


def test_compile_bridge_solve_runs_against_existing_solver_contract() -> None:
    lifecycle = HydraulicCompileLifecycle()
    compiled = lifecycle.compile(system=_linear_topology_system(), graph_revision="rev-solve")

    solved = compiled.solve(tolerance=1.0e-12, max_iterations=10)

    assert solved.converged
    assert solved.unknowns["pressure_upstream"] == pytest.approx(120_000.0)
    assert solved.unknowns["flow_linear"] == pytest.approx(50.0)
    assert solved.unknowns["pressure_downstream"] == pytest.approx(119_950.0)


def test_compile_bridge_preserves_component_specific_pressure_reference_diagnostics() -> None:
    system = _disconnected_missing_reference_system()
    unknown_index_map, residual_index_map = build_index_maps(system)
    compiled = CompiledHydraulicGraph(
        graph_revision="rev-diagnostic",
        system=system,
        unknown_order=tuple(sorted(unknown_index_map, key=unknown_index_map.__getitem__)),
        residual_order=tuple(sorted(residual_index_map, key=residual_index_map.__getitem__)),
    )

    messages: list[str] = []
    for _ in range(2):
        with pytest.raises(ValueError) as error:
            _ = compiled.solve()
        messages.append(str(error.value))

    assert messages[0] == messages[1]
    assert "missing pressure reference" in messages[0]
    assert "connected component 2" in messages[0]
    assert "pressure_b" in messages[0]


def test_compile_bridge_exposes_deterministic_topology_lookup_helpers() -> None:
    system = HydraulicSystemDefinition(
        equations=(),
        linear_residual_equations=(
            _linear_equation(
                "ref_source",
                {"pressure__boundary_feed_outlet": 1.0},
                constant=-120_000.0,
            ),
            _linear_equation(
                "ref_target",
                {"pressure__process_reactor_feed": 1.0},
                constant=-110_000.0,
            ),
            _linear_equation(
                "head_balance",
                {
                    "pressure__boundary_feed_outlet": 1.0,
                    "pressure__process_reactor_feed": -1.0,
                    "edge_0001": -1.0,
                },
            ),
        ),
        topology_lookup=HydraulicTopologyLookup(
            line_flow_unknown_by_line=MappingProxyType({"edge_0001": "edge_0001"}),
            edge_source_pressure_unknown_by_line=MappingProxyType(
                {"edge_0001": "pressure__boundary_feed_outlet"}
            ),
            edge_target_pressure_unknown_by_line=MappingProxyType(
                {"edge_0001": "pressure__process_reactor_feed"}
            ),
            node_pressure_unknown_by_endpoint=MappingProxyType(
                {
                    "feed.outlet": "pressure__boundary_feed_outlet",
                    "reactor.feed": "pressure__process_reactor_feed",
                }
            ),
            node_pressure_unknown_by_junction=MappingProxyType({}),
        ),
        pressure_anchor_metadata=(
            HydraulicPressureAnchorMetadata(
                pressure_unknown_name="pressure__boundary_feed_outlet",
                residual_name="ref_source",
                pressure_value=120_000.0,
                topology_label="feed.outlet",
            ),
            HydraulicPressureAnchorMetadata(
                pressure_unknown_name="pressure__process_reactor_feed",
                residual_name="ref_target",
                pressure_value=110_000.0,
                topology_label="reactor.feed",
            ),
        ),
    )

    compiled = HydraulicCompileLifecycle().compile(system=system, graph_revision="rev-lookup")
    solved = compiled.solve(tolerance=1.0e-12, max_iterations=10)

    assert compiled.resolve_line_flow(
        line_id="edge_0001", hydraulic_result=solved
    ) == pytest.approx(10_000.0)
    assert compiled.resolve_line_source_pressure(
        line_id="edge_0001", hydraulic_result=solved
    ) == pytest.approx(120_000.0)
    assert compiled.resolve_line_target_pressure(
        line_id="edge_0001", hydraulic_result=solved
    ) == pytest.approx(110_000.0)
    assert compiled.resolve_endpoint_pressure(
        endpoint_id="reactor.feed", hydraulic_result=solved
    ) == pytest.approx(110_000.0)


def test_compile_bridge_solves_feed_unit_and_explicit_junction_mass_balance() -> None:
    compiled = HydraulicCompileLifecycle().compile(
        system=_feed_unit_junction_topology_system(),
        graph_revision="rev-feed-unit-junction",
    )

    solved = compiled.solve(tolerance=1.0e-12, max_iterations=12)

    assert solved.converged
    assert compiled.resolve_junction_pressure(
        junction_id="mix",
        hydraulic_result=solved,
    ) == pytest.approx(126_000.0)
    assert compiled.resolve_endpoint_pressure(
        endpoint_id="reactor.feed",
        hydraulic_result=solved,
    ) == pytest.approx(120_000.0)
    assert compiled.resolve_line_flow(
        line_id="edge_feed_a",
        hydraulic_result=solved,
    ) == pytest.approx(9_000.0)
    assert compiled.resolve_line_flow(
        line_id="edge_feed_b",
        hydraulic_result=solved,
    ) == pytest.approx(1_000.0)
    assert compiled.resolve_line_flow(
        line_id="edge_unit",
        hydraulic_result=solved,
    ) == pytest.approx(6_000.0)
    assert compiled.resolve_line_flow(
        line_id="edge_purge",
        hydraulic_result=solved,
    ) == pytest.approx(4_000.0)
    flow_feed_a = compiled.resolve_line_flow(line_id="edge_feed_a", hydraulic_result=solved)
    flow_feed_b = compiled.resolve_line_flow(line_id="edge_feed_b", hydraulic_result=solved)
    flow_unit = compiled.resolve_line_flow(line_id="edge_unit", hydraulic_result=solved)
    flow_purge = compiled.resolve_line_flow(line_id="edge_purge", hydraulic_result=solved)
    assert flow_feed_a is not None
    assert flow_feed_b is not None
    assert flow_unit is not None
    assert flow_purge is not None
    assert (flow_feed_a + flow_feed_b - flow_unit - flow_purge) == pytest.approx(0.0)
    assert {equation.residual_name for equation in compiled.system.linear_residual_equations} >= {
        "pressure__junction_mix__mass_balance",
        "feed_a_anchor",
        "unit_anchor",
    }


def test_passive_unit_ports_do_not_compile_as_implicit_pressure_anchors() -> None:
    flowsheet = Flowsheet(
        context=SimulationRuntimeContext.create(species_names=["water", "ethanol"])
    )
    flowsheet.add_unit("heater", HeaterCooler(n_species=2))

    assert (
        flowsheet._resolve_hydraulic_anchor_pressure(
            node_id="heater",
            port_name="inlet",
            topology=None,
        )
        is None
    )
    assert (
        flowsheet._resolve_hydraulic_anchor_pressure(
            node_id="heater",
            port_name="outlet",
            topology=None,
        )
        is None
    )


def test_vector_boundary_pressures_are_not_inferred_as_unit_port_anchors_without_declaration() -> (
    None
):
    flowsheet = Flowsheet(
        context=SimulationRuntimeContext.create(species_names=["water", "ethanol"])
    )
    flowsheet.add_unit(
        "mixer",
        Mixer(
            n_inlets=2,
            n_species=2,
            inlet_pressures=np.asarray([150_000.0, 145_000.0], dtype=np.float64),
        ),
    )

    assert (
        flowsheet._resolve_hydraulic_anchor_pressure(
            node_id="mixer",
            port_name="inlet_1",
            topology=None,
        )
        is None
    )
    assert (
        flowsheet._resolve_hydraulic_anchor_pressure(
            node_id="mixer",
            port_name="inlet_2",
            topology=None,
        )
        is None
    )
    assert (
        flowsheet._resolve_hydraulic_anchor_pressure(
            node_id="mixer",
            port_name="outlet",
            topology=None,
        )
        is None
    )


def test_explicit_unit_port_anchor_satisfies_feed_presence_validation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_hydraulic_participation_property(
        monkeypatch,
        HeaterCooler,
        lambda self: HydraulicParticipationSpec(
            ports={
                "inlet": HydraulicPortSpec(
                    role="fixed_pressure_anchor",
                    pressure_state=HydraulicScalarStateRef("inlet_pressure"),
                    fixed_value_state=HydraulicScalarStateRef("inlet_pressure"),
                ),
                "outlet": HydraulicPortSpec(
                    role="pressure_state",
                    pressure_state=HydraulicScalarStateRef("outlet_pressure"),
                ),
            },
            balancing_groups=(
                HydraulicBalancingGroupSpec(name="through_unit", ports=("inlet", "outlet")),
            ),
            relations=(
                HydraulicRelationSpec(
                    name="pressure_drop",
                    kind="pressure_drop",
                    ports=("inlet", "outlet"),
                    parameter_state=HydraulicScalarStateRef("pressure_drop"),
                ),
            ),
        ),
    )

    context = SimulationRuntimeContext.create(species_names=["water", "ethanol"])
    flowsheet = Flowsheet(context=context)
    heater_a = HeaterCooler(n_species=2)
    heater_b = HeaterCooler(n_species=2)
    heater_a.inlet_pressure = 150_000.0
    flowsheet.add_unit("heater_a", heater_a)
    flowsheet.add_unit("heater_b", heater_b)
    flowsheet.connect("heater_a", "heater_b")
    flowsheet.connect("heater_b", "heater_a")

    resolved_connections = flowsheet._resolved_connections_for_validation()

    flowsheet._validate_pressure_boundary_presence(resolved_connections=resolved_connections)


def test_flowsheet_compile_recognizes_declared_unit_pressure_drop_relation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_hydraulic_participation_property(
        monkeypatch,
        HeaterCooler,
        lambda self: HydraulicParticipationSpec(
            ports={
                "inlet": HydraulicPortSpec(
                    role="pressure_state",
                    pressure_state=HydraulicScalarStateRef("inlet_pressure"),
                ),
                "outlet": HydraulicPortSpec(
                    role="pressure_state",
                    pressure_state=HydraulicScalarStateRef("outlet_pressure"),
                ),
            },
            balancing_groups=(
                HydraulicBalancingGroupSpec(name="through_unit", ports=("inlet", "outlet")),
            ),
            relations=(
                HydraulicRelationSpec(
                    name="unit_pressure_drop",
                    kind="pressure_drop",
                    ports=("inlet", "outlet"),
                    parameter_state=HydraulicScalarStateRef("pressure_drop"),
                ),
            ),
        ),
    )

    context = SimulationRuntimeContext.create(species_names=["water", "ethanol"])
    flowsheet = Flowsheet(context=context)
    heater = HeaterCooler(n_species=2, pressure_drop=2_500.0)
    flowsheet.add_unit("heater", heater)
    flowsheet.add_feed_from_values(
        "feed",
        T=300.0,
        P=120_500.0,
        z=(0.5, 0.5),
        flow=1.0,
    )
    flowsheet.connect("feed", "heater")
    flowsheet.add_sink("product")
    flowsheet.connect("heater", "product")

    plant = flowsheet.compile()

    compiled = plant._network.compiled
    assert compiled is not None and compiled.hydraulic is not None
    residuals = {
        equation.residual_name: equation
        for equation in compiled.hydraulic.system.linear_residual_equations
    }
    relation = residuals["unit__heater__pressure_relation"]

    assert relation.coefficients == {
        "pressure__declared_heater_inlet_pressure": 1.0,
        "pressure__declared_heater_outlet_pressure": -1.0,
    }
    assert relation.constant == pytest.approx(-2_500.0)
    assert all(
        anchor.topology_label != "heater.inlet"
        for anchor in compiled.hydraulic.system.pressure_anchor_metadata
    )


def test_declared_pressure_drop_conflicting_with_declared_fixed_port_anchors_fails_clearly(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_hydraulic_participation_property(
        monkeypatch,
        HeaterCooler,
        lambda self: HydraulicParticipationSpec(
            ports={
                "inlet": HydraulicPortSpec(
                    role="fixed_pressure_anchor",
                    pressure_state=HydraulicScalarStateRef("inlet_pressure"),
                    fixed_value_state=HydraulicScalarStateRef("inlet_pressure"),
                ),
                "outlet": HydraulicPortSpec(
                    role="fixed_pressure_anchor",
                    pressure_state=HydraulicScalarStateRef("outlet_pressure"),
                    fixed_value_state=HydraulicScalarStateRef("outlet_pressure"),
                ),
            },
            balancing_groups=(
                HydraulicBalancingGroupSpec(name="through_unit", ports=("inlet", "outlet")),
            ),
            relations=(
                HydraulicRelationSpec(
                    name="declared_pressure_drop",
                    kind="pressure_drop",
                    ports=("inlet", "outlet"),
                    parameter_state=HydraulicScalarStateRef("pressure_drop"),
                ),
            ),
        ),
    )

    context = SimulationRuntimeContext.create(species_names=["water", "ethanol"])
    flowsheet = Flowsheet(context=context)
    heater = HeaterCooler(n_species=2, pressure_drop=500.0)
    flowsheet.add_unit("heater", heater)
    heater.inlet_pressure = 150_000.0
    heater.outlet_pressure = 149_000.0
    flowsheet.add_feed_from_values(
        "feed",
        T=300.0,
        P=151_000.0,
        z=(0.5, 0.5),
        flow=1.0,
    )
    flowsheet.connect("feed", "heater")
    flowsheet.add_sink("product")
    flowsheet.connect("heater", "product")

    with pytest.raises(ValueError, match="conflicting unit hydraulic boundary conditions") as error:
        _ = flowsheet.compile()

    message = str(error.value)
    assert "heater" in message
    assert "heater.inlet" in message
    assert "heater.outlet" in message
    assert "declared_pressure_drop" in message
    assert "inferred pressure_drop" not in message


def test_direct_unit_port_fan_in_requires_explicit_junction(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Wave 4.2 migrated the real Splitter to declare a balancing group over
    # (inlet, outlet_1, outlet_2, ...), which intentionally admits direct fan-in at
    # splitter.inlet.  To keep exercising the pre-admission illegal-direct-fan-in
    # path we monkeypatch Splitter with a participation spec that declares all ports
    # as pressure_state but intentionally omits balancing_groups — so the direct
    # multi-edge connection at inlet remains unsupported and must fail early.
    _install_hydraulic_participation_property(
        monkeypatch,
        Splitter,
        lambda self: HydraulicParticipationSpec(
            ports={
                "inlet": HydraulicPortSpec(
                    role="pressure_state",
                    pressure_state=HydraulicScalarStateRef("inlet_pressure"),
                ),
                "outlet_1": HydraulicPortSpec(
                    role="pressure_state",
                    pressure_state=HydraulicIndexedStateRef("outlet_pressures", 0),
                ),
                "outlet_2": HydraulicPortSpec(
                    role="pressure_state",
                    pressure_state=HydraulicIndexedStateRef("outlet_pressures", 1),
                ),
            },
            relations=(
                HydraulicRelationSpec(
                    name="split_equal_pressure",
                    kind="pressure_equal",
                    ports=("inlet", "outlet_1", "outlet_2"),
                ),
            ),
        ),
    )

    context = SimulationRuntimeContext.create(species_names=["water", "ethanol"])
    flowsheet = Flowsheet(context=context)
    flowsheet.add_unit("splitter", Splitter(n_species=2, n_outlets=2))
    flowsheet.add_feed_from_values("feed_a", T=300.0, P=130_000.0, z=(0.5, 0.5), flow=1.0)
    flowsheet.add_feed_from_values("feed_b", T=300.0, P=125_000.0, z=(0.5, 0.5), flow=1.0)
    flowsheet.connect("feed_a", "splitter.inlet")
    flowsheet.connect("feed_b", "splitter.inlet")

    with pytest.raises(
        ValueError,
        match=r"direct unit-port fan-in/fan-out is illegal at splitter\.inlet",
    ) as error:
        _ = flowsheet.compile()

    assert "explicit junction" in str(error.value)


def test_direct_unit_port_fan_out_requires_explicit_junction(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_hydraulic_participation_property(
        monkeypatch,
        HeaterCooler,
        lambda self: HydraulicParticipationSpec(
            ports={
                "inlet": HydraulicPortSpec(
                    role="pressure_state",
                    pressure_state=HydraulicScalarStateRef("inlet_pressure"),
                ),
                "outlet": HydraulicPortSpec(
                    role="pressure_state",
                    pressure_state=HydraulicScalarStateRef("outlet_pressure"),
                ),
            },
            relations=(
                HydraulicRelationSpec(
                    name="pressure_drop",
                    kind="pressure_drop",
                    ports=("inlet", "outlet"),
                    parameter_state=HydraulicScalarStateRef("pressure_drop"),
                ),
            ),
        ),
    )

    context = SimulationRuntimeContext.create(species_names=["water", "ethanol"])
    flowsheet = Flowsheet(context=context)
    flowsheet.add_unit("heater", HeaterCooler(n_species=2))
    flowsheet.add_unit("cooler_a", HeaterCooler(n_species=2))
    flowsheet.add_unit("cooler_b", HeaterCooler(n_species=2))
    flowsheet.add_feed_from_values("feed", T=300.0, P=130_000.0, z=(0.5, 0.5), flow=1.0)
    flowsheet.connect("feed", "heater")
    flowsheet.connect("heater.outlet", "cooler_a.inlet")
    flowsheet.connect("heater.outlet", "cooler_b.inlet")

    with pytest.raises(
        ValueError,
        match=r"direct unit-port fan-in/fan-out is illegal at heater\.outlet",
    ) as error:
        _ = flowsheet.compile()

    assert "unit model that declares the required hydraulic balancing semantics" in str(error.value)


def test_element_coupled_direct_unit_port_fan_out_requires_explicit_junction() -> None:
    context = SimulationRuntimeContext.create(species_names=["water", "ethanol"])
    flowsheet = Flowsheet(context=context)
    flowsheet.add_unit("pump", Pump(n_species=2))
    flowsheet.add_feed_from_values("feed", T=300.0, P=130_000.0, z=(0.5, 0.5), flow=1.0)
    flowsheet.add_sink("product_a")
    flowsheet.add_sink("product_b")
    flowsheet.connect("feed", "pump")
    flowsheet.connect("pump.outlet", "product_a")
    flowsheet.connect("pump.outlet", "product_b")

    with pytest.raises(
        ValueError,
        match=r"direct unit-port fan-in/fan-out is illegal at pump\.outlet",
    ) as error:
        _ = flowsheet.compile()

    assert "explicit junction" in str(error.value)


def test_connected_heater_cooler_without_hydraulic_participation_fails_compile_with_remediation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_hydraulic_participation_property(monkeypatch, HeaterCooler, lambda self: None)

    context = SimulationRuntimeContext.create(species_names=["water", "ethanol"])
    flowsheet = Flowsheet(context=context)
    flowsheet.add_unit("heater", HeaterCooler(n_species=2))
    flowsheet.add_feed_from_values("feed", T=300.0, P=130_000.0, z=(0.5, 0.5), flow=1.0)
    flowsheet.add_sink("product")
    flowsheet.connect("feed", "heater")
    flowsheet.connect("heater", "product")

    with pytest.raises(ValueError) as error:
        _ = flowsheet.compile()

    message = str(error.value)
    assert "heater" in message
    assert "HeaterCooler" in message
    assert "hydraulic_participation" in message
    assert "add" in message


@pytest.mark.parametrize(
    ("unit_factory", "unit_id", "expected_state", "expected_index"),
    (
        (
            lambda: Mixer(n_inlets=2, n_species=2),
            "mixer",
            "inlet_pressures",
            99,
        ),
        (
            lambda: Splitter(n_outlets=2, n_species=2),
            "splitter",
            "outlet_pressures",
            99,
        ),
    ),
)
def test_invalid_indexed_pressure_ref_fails_with_state_and_index_named(
    monkeypatch: pytest.MonkeyPatch,
    unit_factory,
    unit_id: str,
    expected_state: str,
    expected_index: int,
) -> None:
    if unit_id == "mixer":
        _install_hydraulic_participation_property(
            monkeypatch,
            Mixer,
            lambda self: HydraulicParticipationSpec(
                ports={
                    "inlet_1": HydraulicPortSpec(
                        role="pressure_state",
                        pressure_state=HydraulicIndexedStateRef("inlet_pressures", expected_index),
                    ),
                    "inlet_2": HydraulicPortSpec(
                        role="pressure_state",
                        pressure_state=HydraulicIndexedStateRef("inlet_pressures", 1),
                    ),
                    "outlet": HydraulicPortSpec(
                        role="pressure_state",
                        pressure_state=HydraulicScalarStateRef("outlet_pressure"),
                    ),
                },
                balancing_groups=(
                    HydraulicBalancingGroupSpec(
                        name="mixing_group",
                        ports=("inlet_1", "inlet_2", "outlet"),
                    ),
                ),
                relations=(
                    HydraulicRelationSpec(
                        name="mixing_equal_pressure",
                        kind="pressure_equal",
                        ports=("inlet_1", "inlet_2", "outlet"),
                    ),
                ),
            ),
        )
    else:
        _install_hydraulic_participation_property(
            monkeypatch,
            Splitter,
            lambda self: HydraulicParticipationSpec(
                ports={
                    "inlet": HydraulicPortSpec(
                        role="pressure_state",
                        pressure_state=HydraulicScalarStateRef("inlet_pressure"),
                    ),
                    "outlet_1": HydraulicPortSpec(
                        role="pressure_state",
                        pressure_state=HydraulicIndexedStateRef("outlet_pressures", 0),
                    ),
                    "outlet_2": HydraulicPortSpec(
                        role="pressure_state",
                        pressure_state=HydraulicIndexedStateRef("outlet_pressures", expected_index),
                    ),
                },
                balancing_groups=(
                    HydraulicBalancingGroupSpec(
                        name="split_group",
                        ports=("inlet", "outlet_1", "outlet_2"),
                    ),
                ),
                relations=(
                    HydraulicRelationSpec(
                        name="split_equal_pressure",
                        kind="pressure_equal",
                        ports=("inlet", "outlet_1", "outlet_2"),
                    ),
                ),
            ),
        )

    context = SimulationRuntimeContext.create(species_names=["water", "ethanol"])
    flowsheet = Flowsheet(context=context)
    flowsheet.add_unit(unit_id, unit_factory())

    if unit_id == "mixer":
        flowsheet.add_feed_from_values("feed_a", T=300.0, P=130_000.0, z=(0.5, 0.5), flow=1.0)
        flowsheet.add_feed_from_values("feed_b", T=300.0, P=125_000.0, z=(0.5, 0.5), flow=1.0)
        flowsheet.add_sink("product")
        flowsheet.connect("feed_a", "mixer.inlet_1")
        flowsheet.connect("feed_b", "mixer.inlet_2")
        flowsheet.connect("mixer", "product")
    else:
        flowsheet.add_feed_from_values("feed", T=300.0, P=130_000.0, z=(0.5, 0.5), flow=1.0)
        flowsheet.add_sink("product_a")
        flowsheet.add_sink("product_b")
        flowsheet.connect("feed", "splitter")
        flowsheet.connect("splitter.outlet_1", "product_a")
        flowsheet.connect("splitter.outlet_2", "product_b")

    with pytest.raises(ValueError) as error:
        _ = flowsheet.compile()

    message = str(error.value)
    assert expected_state in message
    assert str(expected_index) in message


def test_declared_flash_drum_shared_outlet_pressure_refs_share_one_compiled_unknown(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_hydraulic_participation_property(
        monkeypatch,
        FlashDrum,
        lambda self: HydraulicParticipationSpec(
            ports={
                "inlet": HydraulicPortSpec(
                    role="pressure_state",
                    pressure_state=HydraulicScalarStateRef("inlet_pressure"),
                ),
                "vapor_outlet": HydraulicPortSpec(
                    role="fixed_pressure_anchor",
                    pressure_state=HydraulicScalarStateRef("outlet_pressure"),
                    fixed_value_state=HydraulicScalarStateRef("imposed_pressure"),
                ),
                "liquid_outlet": HydraulicPortSpec(
                    role="fixed_pressure_anchor",
                    pressure_state=HydraulicScalarStateRef("outlet_pressure"),
                    fixed_value_state=HydraulicScalarStateRef("imposed_pressure"),
                ),
            },
            balancing_groups=(
                HydraulicBalancingGroupSpec(
                    name="flash_balance",
                    ports=("inlet", "vapor_outlet", "liquid_outlet"),
                ),
            ),
        ),
    )

    context = SimulationRuntimeContext.create(species_names=["water", "ethanol"])
    flowsheet = Flowsheet(context=context)
    flowsheet.add_unit("flash", FlashDrum(n_species=2, thermal_mode="isothermal"))
    flowsheet.add_feed_from_values("feed", T=300.0, P=130_000.0, z=(0.5, 0.5), flow=1.0)
    flowsheet.add_sink("vapor_product")
    flowsheet.add_sink("liquid_product")
    flowsheet.connect("feed", "flash")
    flowsheet.connect("flash.vapor_outlet", "vapor_product")
    flowsheet.connect("flash.liquid_outlet", "liquid_product")

    plant = flowsheet.compile()

    compiled = plant._network.compiled
    assert compiled is not None and compiled.hydraulic is not None
    lookup = compiled.hydraulic.system.topology_lookup
    assert lookup is not None
    assert (
        lookup.node_pressure_unknown_by_endpoint["flash.vapor_outlet"]
        == lookup.node_pressure_unknown_by_endpoint["flash.liquid_outlet"]
    )
    relation_names = {
        equation.residual_name for equation in compiled.hydraulic.system.linear_residual_equations
    }
    assert not any(
        residual_name.startswith("unit__flash__pressure_relation")
        for residual_name in relation_names
    )


def test_hydraulic_participation_missing_port_is_not_treated_as_implicitly_passive(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_hydraulic_participation_property(
        monkeypatch,
        HeaterCooler,
        lambda self: HydraulicParticipationSpec(
            ports={
                "inlet": HydraulicPortSpec(
                    role="pressure_state",
                    pressure_state=HydraulicScalarStateRef("inlet_pressure"),
                ),
            },
        ),
    )

    context = SimulationRuntimeContext.create(species_names=["water", "ethanol"])
    flowsheet = Flowsheet(context=context)
    flowsheet.add_unit("heater", HeaterCooler(n_species=2))
    flowsheet.add_feed_from_values("feed", T=300.0, P=130_000.0, z=(0.5, 0.5), flow=1.0)
    flowsheet.add_sink("product")
    flowsheet.connect("feed", "heater")
    flowsheet.connect("heater", "product")

    with pytest.raises(ValueError) as error:
        _ = flowsheet.compile()

    message = str(error.value)
    assert "heater" in message
    assert "declared ports must match UnitProcessPorts exactly" in message
    assert "outlet" in message
    assert "add" in message


def test_declared_splitter_direct_fan_in_is_admitted_but_heater_without_balancing_group_fan_out_still_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_hydraulic_participation_property(
        monkeypatch,
        Splitter,
        lambda self: HydraulicParticipationSpec(
            ports={
                "inlet": HydraulicPortSpec(
                    role="pressure_state",
                    pressure_state=HydraulicScalarStateRef("inlet_pressure"),
                ),
                "outlet_1": HydraulicPortSpec(
                    role="pressure_state",
                    pressure_state=HydraulicIndexedStateRef("outlet_pressures", 0),
                ),
                "outlet_2": HydraulicPortSpec(
                    role="pressure_state",
                    pressure_state=HydraulicIndexedStateRef("outlet_pressures", 1),
                ),
            },
            balancing_groups=(
                HydraulicBalancingGroupSpec(
                    name="direct_attachment_group",
                    ports=("inlet", "outlet_1", "outlet_2"),
                ),
            ),
            relations=(
                HydraulicRelationSpec(
                    name="declared_split_equal_pressure",
                    kind="pressure_equal",
                    ports=("inlet", "outlet_1", "outlet_2"),
                ),
            ),
        ),
    )

    context = SimulationRuntimeContext.create(species_names=["water", "ethanol"])
    fan_in_flowsheet = Flowsheet(context=context)
    fan_in_flowsheet.add_unit("splitter", Splitter(n_species=2, n_outlets=2))
    fan_in_flowsheet.add_feed_from_values("feed_a", T=300.0, P=130_000.0, z=(0.5, 0.5), flow=1.0)
    fan_in_flowsheet.add_feed_from_values("feed_b", T=300.0, P=125_000.0, z=(0.5, 0.5), flow=1.0)
    fan_in_flowsheet.add_sink("product_a")
    fan_in_flowsheet.add_sink("product_b")
    fan_in_flowsheet.connect("feed_a", "splitter.inlet")
    fan_in_flowsheet.connect("feed_b", "splitter.inlet")
    fan_in_flowsheet.connect("splitter.outlet_1", "product_a")
    fan_in_flowsheet.connect("splitter.outlet_2", "product_b")

    plant = fan_in_flowsheet.compile()

    compiled = plant._network.compiled
    assert compiled is not None and compiled.hydraulic is not None
    relation_names = {
        equation.residual_name for equation in compiled.hydraulic.system.linear_residual_equations
    }
    assert "pressure__process_splitter_inlet__mass_balance" not in relation_names
    assert "pressure__declared_splitter_inlet_pressure__mass_balance" not in relation_names
    assert "unit__splitter__flow_balance__01" in relation_names
    lookup = compiled.hydraulic.system.topology_lookup
    assert lookup.endpoint_role_by_endpoint["splitter.inlet"] == "pressure_state"
    assert lookup.endpoint_role_by_endpoint["splitter.outlet_1"] == "pressure_state"
    assert lookup.endpoint_role_by_endpoint["splitter.outlet_2"] == "pressure_state"
    assert lookup.balancing_group_name_by_endpoint["splitter.inlet"] == "direct_attachment_group"
    assert lookup.balancing_group_name_by_endpoint["splitter.outlet_1"] == "direct_attachment_group"
    assert lookup.balancing_group_name_by_endpoint["splitter.outlet_2"] == "direct_attachment_group"

    _install_hydraulic_participation_property(
        monkeypatch,
        HeaterCooler,
        lambda self: HydraulicParticipationSpec(
            ports={
                "inlet": HydraulicPortSpec(
                    role="pressure_state",
                    pressure_state=HydraulicScalarStateRef("inlet_pressure"),
                ),
                "outlet": HydraulicPortSpec(
                    role="pressure_state",
                    pressure_state=HydraulicScalarStateRef("outlet_pressure"),
                ),
            },
            relations=(
                HydraulicRelationSpec(
                    name="pressure_drop",
                    kind="pressure_drop",
                    ports=("inlet", "outlet"),
                    parameter_state=HydraulicScalarStateRef("pressure_drop"),
                ),
            ),
        ),
    )

    fan_out_flowsheet = Flowsheet(context=context)
    fan_out_flowsheet.add_unit("heater", HeaterCooler(n_species=2))
    fan_out_flowsheet.add_unit("cooler_a", HeaterCooler(n_species=2))
    fan_out_flowsheet.add_unit("cooler_b", HeaterCooler(n_species=2))
    fan_out_flowsheet.add_feed_from_values("feed", T=300.0, P=130_000.0, z=(0.5, 0.5), flow=1.0)
    fan_out_flowsheet.connect("feed", "heater")
    fan_out_flowsheet.connect("heater.outlet", "cooler_a.inlet")
    fan_out_flowsheet.connect("heater.outlet", "cooler_b.inlet")

    with pytest.raises(ValueError) as error:
        _ = fan_out_flowsheet.compile()

    message = str(error.value)
    assert "heater.outlet" in message
    assert "explicit junction" in message


@pytest.mark.parametrize(
    ("getter", "expected_fragments"),
    (
        (
            lambda self: HydraulicParticipationSpec(
                ports={
                    "inlet": HydraulicPortSpec(role="passive"),
                    "outlet": HydraulicPortSpec(
                        role="pressure_state",
                        pressure_state=HydraulicScalarStateRef("outlet_pressure"),
                    ),
                },
                relations=(
                    HydraulicRelationSpec(
                        name="passive_overlap_relation",
                        kind="pressure_equal",
                        ports=("inlet", "outlet"),
                    ),
                ),
            ),
            ("inlet", "passive_overlap_relation"),
        ),
        (
            lambda self: HydraulicParticipationSpec(
                ports={
                    "inlet": HydraulicPortSpec(
                        role="pressure_state",
                        pressure_state=HydraulicScalarStateRef("inlet_pressure"),
                    ),
                    "outlet": HydraulicPortSpec(
                        role="pressure_state",
                        pressure_state=HydraulicScalarStateRef("outlet_pressure"),
                    ),
                },
                balancing_groups=(
                    HydraulicBalancingGroupSpec(name="duplicate_group", ports=("inlet", "outlet")),
                    HydraulicBalancingGroupSpec(name="duplicate_group", ports=("inlet", "outlet")),
                ),
            ),
            ("duplicate_group", "balancing"),
        ),
        (
            lambda self: HydraulicParticipationSpec(
                ports={
                    "inlet": HydraulicPortSpec(
                        role="pressure_state",
                        pressure_state=HydraulicScalarStateRef("inlet_pressure"),
                    ),
                    "outlet": HydraulicPortSpec(
                        role="pressure_state",
                        pressure_state=HydraulicScalarStateRef("outlet_pressure"),
                    ),
                },
                element_couplings=(
                    HydraulicElementCouplingSpec(
                        name="duplicate_coupling",
                        port="outlet",
                        ports=("inlet", "outlet"),
                    ),
                    HydraulicElementCouplingSpec(
                        name="duplicate_coupling",
                        port="outlet",
                        ports=("inlet", "outlet"),
                    ),
                ),
            ),
            ("duplicate_coupling", "coupling"),
        ),
        (
            lambda self: HydraulicParticipationSpec(
                ports={
                    "inlet": HydraulicPortSpec(role="passive"),
                    "outlet": HydraulicPortSpec(
                        role="pressure_state",
                        pressure_state=HydraulicScalarStateRef("outlet_pressure"),
                    ),
                },
                element_couplings=(
                    HydraulicElementCouplingSpec(
                        name="passive_coupling",
                        port="outlet",
                        ports=("inlet", "outlet"),
                    ),
                ),
            ),
            ("inlet", "passive_coupling"),
        ),
    ),
)
def test_invalid_hydraulic_participation_overlap_names_offending_port_group_or_coupling(
    monkeypatch: pytest.MonkeyPatch,
    getter,
    expected_fragments: tuple[str, str],
) -> None:
    _install_hydraulic_participation_property(monkeypatch, HeaterCooler, getter)

    context = SimulationRuntimeContext.create(species_names=["water", "ethanol"])
    flowsheet = Flowsheet(context=context)
    flowsheet.add_unit("heater", HeaterCooler(n_species=2))
    flowsheet.add_feed_from_values("feed", T=300.0, P=130_000.0, z=(0.5, 0.5), flow=1.0)
    flowsheet.add_sink("product")
    flowsheet.connect("feed", "heater")
    flowsheet.connect("heater", "product")

    with pytest.raises(ValueError) as error:
        _ = flowsheet.compile()

    message = str(error.value)
    for fragment in expected_fragments:
        assert fragment in message


def test_plain_process_model_subclass_without_hydraulic_participation_fails_compile(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Wave 2: connected units without hydraulic_participation must fail compile
    regardless of base class. CSTR is a plain ProcessModel subclass that has not
    declared hydraulic_participation; it must be rejected at compile with remediation guidance.
    """
    _install_hydraulic_participation_property(monkeypatch, CSTR, lambda self: None)

    context = SimulationRuntimeContext.create(species_names=["water", "ethanol"])
    flowsheet = Flowsheet(context=context)
    cstr = CSTR(n_species=2)
    cstr.inlet_pressure = 120_000.0
    flowsheet.add_unit("reactor", cstr)
    flowsheet.add_feed_from_values("feed", T=300.0, P=130_000.0, z=(0.5, 0.5), flow=1.0)
    flowsheet.connect("feed", "reactor")

    with pytest.raises(ValueError) as error:
        flowsheet.compile()

    message = str(error.value)
    assert "reactor" in message
    assert "CSTR" in message
    assert "hydraulic_participation" in message
    assert "add" in message


def test_line_geometry_defaults_to_canonical_line_equation_name() -> None:
    system = HydraulicSystemDefinition(
        equations=(
            ElementEquation(
                name="edge_0001",
                element=CanonicalNodePressureHydraulicElement(wrapped=PipeHydraulicElement()),
                inputs=MappingProxyType({}),
                parameters=MappingProxyType({"pipe_resistance": 1.0, "delta": 1.0e-3}),
                unknown_name_map=MappingProxyType(
                    {
                        "flow_rate": "edge_0001",
                        "upstream_pressure": "pressure_feed",
                        "downstream_pressure": "pressure_reactor",
                    }
                ),
                residual_name_map=MappingProxyType({"head_balance": "edge_0001_head_balance"}),
            ),
        ),
        linear_residual_equations=(
            _linear_equation("feed_anchor", {"pressure_feed": 1.0}, constant=-120_000.0),
            _linear_equation(
                "reactor_anchor",
                {"pressure_reactor": 1.0},
                constant=-100_000.0,
            ),
        ),
    )
    network = ConnectionNetwork(
        compile_lifecycle=HydraulicCompileLifecycle(),
        hydraulic_system_builder=lambda topology: system,
    )
    network.add_process("reactor", inlet_ports=("feed",), outlet_ports=("product",))
    network.add_boundary_source("feed_boundary")
    network.add_boundary_sink("product_boundary")
    line_id = network.connect("feed_boundary", "reactor.feed")

    network.configure_line_geometry(line_id=line_id, radius_m=0.05, length_m=2.0)
    compiled = network.compile()

    [config] = network.list_line_hydraulic_configs()
    assert config.line_id == line_id
    assert config.equation_name == line_id
    assert compiled.hydraulic is not None
    equation = compiled.hydraulic.system.equations[0]
    assert equation.name == line_id
    assert equation.parameters["pipe_resistance"] == pytest.approx(2.0 / (0.05**4))
