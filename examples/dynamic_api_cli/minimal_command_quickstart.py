from __future__ import annotations

from typing import cast

from modular_simulation.cli import ModularCli
from modular_simulation.connection.domain_contracts import JunctionProcess
from modular_simulation.connection.hydraulic_compile import HydraulicCompileLifecycle
from modular_simulation.connection.hydraulic_solver import (
    HydraulicSystemDefinition,
    LinearResidualEquation,
)
from modular_simulation.connection.network import ConnectionNetwork
from modular_simulation.connection.reconfiguration_api import (
    DynamicConnectionLineReconfigurationApi,
    DynamicUnitPortReconfigurationApi,
)
from modular_simulation.connection.runtime import ConnectionRuntimeOrchestrator
from modular_simulation.connection.runtime import ConnectionRuntimeStepResult


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
    network = ConnectionNetwork(
        compile_lifecycle=HydraulicCompileLifecycle(),
        hydraulic_system_builder=lambda topology: _valid_system(),
        runtime_orchestrator=runtime,
    )
    network.add_process("reactor", inlet_ports=("feed",), outlet_ports=("product",))
    network.add_boundary_source("feed_boundary")
    network.add_boundary_sink("product_boundary")
    _ = network.connect("feed_boundary", "reactor.feed")
    _ = network.connect("reactor.product", "product_boundary")
    _ = network.compile()
    return network


def run_demo() -> dict[str, object]:
    runtime = ConnectionRuntimeOrchestrator()
    network = _network(runtime)

    cli = ModularCli(network=network)
    unit_api = DynamicUnitPortReconfigurationApi(network=network)
    line_api = DynamicConnectionLineReconfigurationApi(network=network)

    command_request_ids = (
        cli.add_unit("reactor_b", ("feed",), ("product",)),
        cli.connect("reactor.product", "reactor_b.feed", line_id="edge_reactor_b"),
    )
    command_apply = cast(ConnectionRuntimeStepResult, network.step(macro_step_time_s=0.0))

    junction = JunctionProcess(
        junction_id="mix_junction",
        inlet_port_ids=("in",),
        outlet_port_id="out",
    )
    request_ids = (
        unit_api.add_junction_process(junction),
        network.queue_reconfiguration(
            {
                "operation": "add_boundary_sink",
                "boundary_id": "junction_sink",
            }
        ),
        line_api.connect_line(
            source="reactor_b.product",
            target="mix_junction.in",
            line_id="edge_mix_in",
        ),
        line_api.connect_line(
            source="mix_junction.out",
            target="junction_sink.inlet",
            line_id="edge_mix_out",
        ),
    )
    api_apply = cast(ConnectionRuntimeStepResult, network.step(macro_step_time_s=0.0))

    compiled = network.compiled
    if compiled is None:
        raise RuntimeError("compiled network unavailable after quickstart apply")

    process_ids = tuple(node.process_id for node in compiled.topology.process_nodes)
    boundary_ids = tuple(node.boundary_id for node in compiled.topology.boundary_nodes)

    return {
        "command_request_ids": command_request_ids,
        "command_applied": tuple(command_apply.barrier_reconfiguration.applied_request_ids),
        "api_request_ids": request_ids,
        "api_applied": tuple(api_apply.barrier_reconfiguration.applied_request_ids),
        "graph_revision": str(compiled.graph_revision),
        "process_ids": process_ids,
        "boundary_ids": boundary_ids,
    }


if __name__ == "__main__":
    print(run_demo())
