from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import cast

import numpy as np
import pytest

from modular_simulation.components.sensors import SensorRuntimeBindingApi
from modular_simulation.connection.hydraulic_compile import HydraulicCompileLifecycle
from modular_simulation.connection.hydraulic_solver import (
    HydraulicSolveResult,
    HydraulicSystemDefinition,
    LinearResidualEquation,
)
from modular_simulation.connection.network import ConnectionNetwork
from modular_simulation.connection.runtime import (
    ConnectionRuntimeOrchestrator,
    ConnectionRuntimeStepResult,
)
from modular_simulation.framework.system import System
from modular_simulation.measurables.process_model import ProcessModel


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


def _runtime_with_dispatcher(
    system: System,
    *,
    solve_observer: Callable[[HydraulicSolveResult], None] | None = None,
) -> ConnectionRuntimeOrchestrator:
    def sensor_dispatcher(
        *,
        operation: str,
        mutation: Mapping[str, object],
        request_metadata: Mapping[str, object],
    ) -> None:
        system.apply_sensor_runtime_mutation(
            operation=operation,
            mutation=mutation,
            request_metadata=request_metadata,
        )

    def hydraulic_solve_step(
        *,
        network: ConnectionNetwork,
        macro_step_time_s: float,
    ) -> HydraulicSolveResult:
        del macro_step_time_s
        compiled = network.compiled
        if compiled is None or compiled.hydraulic is None:
            raise RuntimeError("compiled hydraulic graph is required")
        result = compiled.hydraulic.solve()
        if solve_observer is not None:
            solve_observer(result)
        return result

    return ConnectionRuntimeOrchestrator(
        hydraulic_solve_step=hydraulic_solve_step,
        sensor_mutation_dispatcher=sensor_dispatcher,
    )


def _build_system(process_model: ProcessModel) -> System:
    return System(
        dt=1.0,
        process_model=process_model,
        sensors=[],
        calculations=[],
        control_elements=[],
        show_progress=False,
    )


def test_sensor_create_bind_unbind_remove_through_barrier(
    thermal_process_model: ProcessModel,
) -> None:
    system = _build_system(thermal_process_model)
    runtime = _runtime_with_dispatcher(system)
    network = _network(runtime)
    api = SensorRuntimeBindingApi(network=network)

    create_request = api.create_sensor(
        sensor_id="temperature_sensor",
        signal_key="temperature",
        process_id="reactor",
        port_id="feed",
        sensor_config={"unit": "K", "sampling_period": 0.0, "deadtime": 0.0},
    )
    assert create_request == "rq_0001"

    first_step = network.step(macro_step_time_s=0.25)
    first_result = cast(ConnectionRuntimeStepResult, first_step)
    assert first_result.barrier_reconfiguration.applied_request_ids == ("rq_0001",)
    assert first_result.graph_revision == "graph_rev_0001"

    created_sensor = next(
        sensor for sensor in system.sensors if sensor.name == "temperature_sensor"
    )
    assert created_sensor.point.data.value == pytest.approx(300.0)
    assert created_sensor.point.data.ok
    assert "temperature_sensor" in system.point_registry

    setattr(thermal_process_model, "ambient_temperature", 292.0)
    bind_request = api.bind_sensor(
        sensor_id="temperature_sensor",
        signal_key="ambient_temperature",
        process_id="reactor",
        port_id="feed",
    )
    assert bind_request == "rq_0002"

    second_step = network.step(macro_step_time_s=0.25)
    second_result = cast(ConnectionRuntimeStepResult, second_step)
    assert second_result.barrier_reconfiguration.applied_request_ids == ("rq_0002",)
    assert second_result.graph_revision == "graph_rev_0001"

    _ = created_sensor.update(system.time)
    assert created_sensor.measurement_tag == "ambient_temperature"
    assert created_sensor.point.data.value == pytest.approx(292.0)
    assert created_sensor.point.data.ok
    assert system.sensor_bindings["temperature_sensor"].signal_key == "ambient_temperature"

    unbind_request = api.unbind_sensor(sensor_id="temperature_sensor")
    assert unbind_request == "rq_0003"

    third_step = network.step(macro_step_time_s=0.25)
    third_result = cast(ConnectionRuntimeStepResult, third_step)
    assert third_result.barrier_reconfiguration.applied_request_ids == ("rq_0003",)
    assert third_result.graph_revision == "graph_rev_0001"
    assert created_sensor.measurement_tag == ""
    assert not created_sensor.point.data.ok
    assert np.isnan(created_sensor.point.data.value)

    remove_request = api.remove_sensor(sensor_id="temperature_sensor")
    assert remove_request == "rq_0004"

    fourth_step = network.step(macro_step_time_s=0.25)
    fourth_result = cast(ConnectionRuntimeStepResult, fourth_step)
    assert fourth_result.barrier_reconfiguration.applied_request_ids == ("rq_0004",)
    assert fourth_result.graph_revision == "graph_rev_0001"
    assert not any(sensor.name == "temperature_sensor" for sensor in system.sensors)
    assert "temperature_sensor" not in system.point_registry


def test_sensor_only_operations_do_not_change_hydraulic_solve_output(
    thermal_process_model: ProcessModel,
) -> None:
    system = _build_system(thermal_process_model)
    solve_unknowns: list[tuple[float, float]] = []

    def observe_solve(result: HydraulicSolveResult) -> None:
        solve_unknowns.append((result.unknowns["flow"], result.unknowns["pressure"]))

    runtime = _runtime_with_dispatcher(system, solve_observer=observe_solve)
    network = _network(runtime)
    api = SensorRuntimeBindingApi(network=network)

    baseline_step = network.step(macro_step_time_s=0.5)
    baseline_result = cast(ConnectionRuntimeStepResult, baseline_step)
    assert baseline_result.graph_revision == "graph_rev_0001"
    assert baseline_result.barrier_reconfiguration.applied_request_ids == ()

    request_id = api.create_sensor(
        sensor_id="flow_probe",
        signal_key="temperature",
        process_id="reactor",
        port_id="feed",
        sensor_config={"unit": "K"},
    )
    assert request_id == "rq_0001"

    sensor_step = network.step(macro_step_time_s=0.5)
    sensor_result = cast(ConnectionRuntimeStepResult, sensor_step)
    assert sensor_result.graph_revision == "graph_rev_0001"
    assert sensor_result.barrier_reconfiguration.applied_request_ids == ("rq_0001",)

    assert len(solve_unknowns) == 2
    assert solve_unknowns[1][0] == pytest.approx(solve_unknowns[0][0], abs=1.0e-12)
    assert solve_unknowns[1][1] == pytest.approx(solve_unknowns[0][1], abs=1.0e-12)

    compiled = network.compiled
    assert compiled is not None and compiled.hydraulic is not None
    assert compiled.graph_revision == "graph_rev_0001"
    assert compiled.hydraulic.graph_revision == "graph_rev_0001"


def test_sensor_operations_require_runtime_dispatcher() -> None:
    runtime = ConnectionRuntimeOrchestrator()
    network = _network(runtime)
    api = SensorRuntimeBindingApi(network=network)

    request_id = api.create_sensor(
        sensor_id="sensor_without_dispatcher",
        signal_key="temperature",
        process_id="reactor",
        port_id="feed",
        sensor_config={"unit": "K"},
    )
    assert request_id == "rq_0001"
    before_failure = network.save_runtime_snapshot()

    with pytest.raises(
        RuntimeError,
        match=(
            "reconfiguration transaction rollback: request 'rq_0001' mutation 1 failed: "
            + "sensor runtime mutation dispatcher is not configured for sensor operations"
        ),
    ):
        _ = network.step(macro_step_time_s=0.25)

    assert network.save_runtime_snapshot() == before_failure


def test_sensor_operation_zero_resistance_guard_rejects_hydraulic_fields(
    thermal_process_model: ProcessModel,
) -> None:
    system = _build_system(thermal_process_model)
    runtime = _runtime_with_dispatcher(system)
    network = _network(runtime)

    _ = network.queue_reconfiguration(
        {
            "operation": "bind_sensor",
            "sensor_id": "sensor_x",
            "signal_key": "temperature",
            "process_id": "reactor",
            "port_id": "feed",
            "radius_m": 0.1,
        }
    )
    queued_snapshot = network.save_runtime_snapshot()

    with pytest.raises(
        RuntimeError,
        match=(
            "reconfiguration transaction rollback: request 'rq_0001' mutation 1 failed: "
            + "operation 'bind_sensor' must not include hydraulic/topology fields"
        ),
    ):
        _ = network.step(macro_step_time_s=0.25)

    assert network.save_runtime_snapshot() == queued_snapshot
