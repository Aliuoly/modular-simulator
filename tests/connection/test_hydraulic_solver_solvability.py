from __future__ import annotations

# pyright: reportMissingImports=false, reportUnknownVariableType=false, reportUnknownMemberType=false, reportUnknownParameterType=false, reportUnknownArgumentType=false, reportUnknownLambdaType=false, reportMissingParameterType=false

import importlib
from types import MappingProxyType

import pytest

hydraulic_compile = importlib.import_module(
    "modular_simulation.connection.hydraulics.hydraulic_compile"
)
hydraulic_solver = importlib.import_module(
    "modular_simulation.connection.hydraulics.hydraulic_solver"
)
network = importlib.import_module("modular_simulation.connection.topology.network")

ConnectionNetwork = network.ConnectionNetwork
HydraulicCompileLifecycle = hydraulic_compile.HydraulicCompileLifecycle
HydraulicPressureAnchorMetadata = hydraulic_solver.HydraulicPressureAnchorMetadata
HydraulicSystemDefinition = hydraulic_solver.HydraulicSystemDefinition
LinearResidualEquation = hydraulic_solver.LinearResidualEquation


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


def _compile_hydraulic_via_network(system: HydraulicSystemDefinition):
    connection_network = ConnectionNetwork(
        compile_lifecycle=HydraulicCompileLifecycle(),
        hydraulic_system_builder=lambda topology: system,
    )
    connection_network.add_process(
        "solver_process",
        inlet_ports=("feed",),
        outlet_ports=("product",),
    )
    connection_network.add_boundary_source("source")
    connection_network.add_boundary_sink("sink")
    connection_network.connect("source", "solver_process.feed")
    connection_network.connect("solver_process.product", "sink")
    compiled = connection_network.compile()
    assert compiled.hydraulic is not None
    return compiled.hydraulic


def test_missing_pressure_reference_in_connected_component_fails_fast() -> None:
    system = HydraulicSystemDefinition(
        equations=(),
        linear_residual_equations=(
            _linear_equation("head_balance", {"pressure_node": 1.0, "flow_branch": -1.0}),
            _linear_equation("mass_balance", {"flow_branch": 1.0}),
        ),
    )

    with pytest.raises(ValueError) as error:
        _ = _compile_hydraulic_via_network(system)

    message = str(error.value)
    assert "missing pressure reference" in message
    assert "pressure_node" in message


def test_disconnected_component_without_reference_reports_component_deterministically() -> None:
    system = HydraulicSystemDefinition(
        equations=(),
        linear_residual_equations=(
            _linear_equation("ref_a", {"pressure_a": 1.0}, constant=-5.0),
            _linear_equation("balance_a", {"pressure_a": 1.0, "flow_a": -1.0}),
            _linear_equation("balance_b", {"pressure_b": 1.0, "flow_b": -1.0}),
            _linear_equation("mass_b", {"flow_b": 1.0}),
        ),
    )

    with pytest.raises(ValueError) as error:
        _ = _compile_hydraulic_via_network(system)

    message = str(error.value)
    assert "missing pressure reference" in message
    assert "connected component 2" in message
    assert "pressure_b" in message


def test_disconnected_components_with_references_solve_deterministically() -> None:
    system = HydraulicSystemDefinition(
        equations=(),
        linear_residual_equations=(
            _linear_equation("ref_a", {"pressure_a": 1.0}, constant=-5.0),
            _linear_equation("balance_a", {"pressure_a": 1.0, "flow_a": -1.0}),
            _linear_equation("ref_b", {"pressure_b": 1.0}, constant=-7.0),
            _linear_equation("balance_b", {"pressure_b": 1.0, "flow_b": -1.0}),
        ),
    )

    result = _compile_hydraulic_via_network(system).solve(tolerance=1.0e-12, max_iterations=10)

    assert result.converged
    assert result.unknowns["pressure_a"] == pytest.approx(5.0)
    assert result.unknowns["flow_a"] == pytest.approx(5.0)
    assert result.unknowns["pressure_b"] == pytest.approx(7.0)
    assert result.unknowns["flow_b"] == pytest.approx(7.0)


def test_connected_component_dof_mismatch_is_detected_before_newton() -> None:
    system = HydraulicSystemDefinition(
        equations=(),
        linear_residual_equations=(
            _linear_equation("r1", {"u": 1.0}),
            _linear_equation("r2", {"u": -1.0}),
            _linear_equation("s1", {"v1": 1.0, "v2": 1.0}),
        ),
    )

    with pytest.raises(ValueError) as error:
        _ = _compile_hydraulic_via_network(system)

    message = str(error.value)
    assert "DOF mismatch" in message
    assert "connected component" in message


def test_singular_jacobian_fails_with_actionable_message() -> None:
    system = HydraulicSystemDefinition(
        equations=(),
        linear_residual_equations=(
            _linear_equation("eq_1", {"x": 1.0, "y": 1.0}),
            _linear_equation("eq_2", {"x": 2.0, "y": 2.0}),
        ),
    )

    compiled = _compile_hydraulic_via_network(system)

    with pytest.raises(ValueError) as error:
        _ = compiled.solve()

    message = str(error.value)
    assert "Jacobian is singular or underdetermined" in message
    assert "rank" in message


def test_conflicting_anchor_metadata_fails_with_actionable_message() -> None:
    system = HydraulicSystemDefinition(
        equations=(),
        linear_residual_equations=(
            _linear_equation("head_a", {"pressure_node": 1.0, "flow_a": -1.0}),
            _linear_equation("head_b", {"pressure_node": 1.0, "flow_b": -1.0}),
            _linear_equation("closure", {"flow_a": 1.0, "flow_b": -1.0}),
        ),
        pressure_anchor_metadata=(
            HydraulicPressureAnchorMetadata(
                pressure_unknown_name="pressure_node",
                residual_name="anchor_a",
                pressure_value=110.0,
                topology_label="feed.outlet",
            ),
            HydraulicPressureAnchorMetadata(
                pressure_unknown_name="pressure_node",
                residual_name="anchor_b",
                pressure_value=130.0,
                topology_label="unit.inlet",
            ),
        ),
    )

    with pytest.raises(ValueError) as error:
        _ = _compile_hydraulic_via_network(system)

    message = str(error.value)
    assert "conflicting hydraulic anchors" in message
    assert "pressure_node" in message
    assert "feed.outlet=110" in message
    assert "unit.inlet=130" in message
