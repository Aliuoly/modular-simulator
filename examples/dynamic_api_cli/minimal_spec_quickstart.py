from __future__ import annotations

from pathlib import Path
from typing import cast

from modular_simulation.cli import ModularCli
from modular_simulation.connection.hydraulics.hydraulic_compile import HydraulicCompileLifecycle
from modular_simulation.connection.hydraulics.hydraulic_solver import (
    HydraulicSystemDefinition,
    LinearResidualEquation,
)
from modular_simulation.connection.topology.network import ConnectionNetwork
from modular_simulation.connection.runtime.runtime import ConnectionRuntimeOrchestrator


def _linear_equation(
    residual_name: str,
    coefficients: dict[str, float],
    *,
    constant: float = 0.0,
) -> LinearResidualEquation:
    return LinearResidualEquation(
        residual_name=residual_name,
        coefficients=coefficients,
        constant=constant,
    )


def _valid_system() -> HydraulicSystemDefinition:
    return HydraulicSystemDefinition(
        equations=(),
        linear_residual_equations=(
            _linear_equation("ref", {"pressure": 1.0}, constant=-5.0),
            _linear_equation("balance", {"pressure": 1.0, "flow": -1.0}),
        ),
    )


def _network(runtime: ConnectionRuntimeOrchestrator) -> ConnectionNetwork:
    return ConnectionNetwork.from_single_process(
        compile_lifecycle=HydraulicCompileLifecycle(),
        hydraulic_system_builder=lambda topology: _valid_system(),
        runtime_orchestrator=runtime,
        process_id="reactor",
        inlet_ports=("feed",),
        outlet_ports=("product",),
    )


def run_demo() -> dict[str, object]:
    runtime = ConnectionRuntimeOrchestrator()
    network = _network(runtime)
    cli = ModularCli(network=network)

    spec_path = Path(__file__).with_name("minimal_spec.json")
    diff = cli.spec_diff(spec_path=str(spec_path))
    apply_result = cli.spec_apply(spec_path=str(spec_path))

    compiled = network.compiled
    if compiled is None:
        raise RuntimeError("compiled network unavailable after spec apply")

    diff_add = cast(list[object], diff["add"])
    diff_remove = cast(list[object], diff["remove"])
    diff_update = cast(list[object], diff["update"])
    applied_request_ids = cast(tuple[str, ...], apply_result["applied_request_ids"])

    edge_ids = tuple(edge.edge_id for edge in compiled.topology.edges)
    process_ids = tuple(node.process_id for node in compiled.topology.process_nodes)
    return {
        "diff_add": len(diff_add),
        "diff_remove": len(diff_remove),
        "diff_update": len(diff_update),
        "applied_request_ids": applied_request_ids,
        "graph_revision": str(compiled.graph_revision),
        "edge_ids": edge_ids,
        "process_ids": process_ids,
    }


if __name__ == "__main__":
    print(run_demo())
