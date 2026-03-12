from __future__ import annotations

# pyright: reportMissingTypeStubs=false

import json
from collections.abc import Mapping
from pathlib import Path
from tempfile import TemporaryDirectory
from types import MappingProxyType, SimpleNamespace
from typing import Annotated, cast, override

import numpy as np
from numpy.typing import NDArray

from modular_simulation.cli import ModularCli
from modular_simulation.components.control_system import (
    ControlElement,
    ControllerMode,
    ControllerRuntimeWiringApi,
    Trajectory,
)
from modular_simulation.components.sensors import SampledDelayedSensor, SensorRuntimeBindingApi
from modular_simulation.connection.domain_contracts import ValveConfig
from modular_simulation.connection.hydraulic_compile import (
    HydraulicCompileLifecycle,
)
from modular_simulation.connection.hydraulic_element import HydraulicElement, ValveHydraulicElement
from modular_simulation.connection.hydraulic_solver import (
    ElementEquation,
    HydraulicSolveResult,
    HydraulicSystemDefinition,
)
from modular_simulation.connection.network import ConnectionNetwork
from modular_simulation.connection.reconfiguration_api import (
    DynamicConnectionLineReconfigurationApi,
    DynamicUnitPortReconfigurationApi,
)
from modular_simulation.connection.runtime import (
    ConnectionRuntimeOrchestrator,
    ConnectionRuntimeStepResult,
)
from modular_simulation.framework.system import System
from modular_simulation.measurables.process_model import (
    ProcessModel,
    StateMetadata as M,
    StateType as T,
)
from modular_simulation.utils.typing import ArrayIndex


FloatArray = NDArray[np.float64]


class ThermalProcessModel(ProcessModel):
    temperature: Annotated[
        float, M(type=T.DIFFERENTIAL, unit="K", description="process temperature")
    ] = 300.0
    heat_flux: Annotated[float, M(type=T.ALGEBRAIC, unit="K/s", description="cooling rate")] = 0.0
    heater_power: Annotated[
        float, M(type=T.CONTROLLED, unit="K/s", description="heating input")
    ] = 0.0
    ambient_temperature: Annotated[
        float, M(type=T.CONSTANT, unit="K", description="ambient temperature")
    ] = 295.0
    cooling_rate: Annotated[
        float, M(type=T.CONSTANT, unit="1/s", description="linear cooling coefficient")
    ] = 0.2

    @staticmethod
    @override
    def calculate_algebraic_values(
        y: FloatArray,
        u: FloatArray,
        k: FloatArray,
        y_map: dict[str, ArrayIndex],
        u_map: dict[str, ArrayIndex],
        k_map: dict[str, ArrayIndex],
        algebraic_map: dict[str, ArrayIndex],
        algebraic_size: int,
    ) -> FloatArray:
        del u, u_map
        result: FloatArray = np.zeros(algebraic_size, dtype=np.float64)
        temperature = float(y[y_map["temperature"]])
        ambient = float(k[k_map["ambient_temperature"]])
        rate = float(k[k_map["cooling_rate"]])
        result[algebraic_map["heat_flux"]] = rate * (temperature - ambient)
        return result

    @staticmethod
    @override
    def differential_rhs(
        t: float,
        y: FloatArray,
        u: FloatArray,
        k: FloatArray,
        algebraic: FloatArray,
        y_map: dict[str, ArrayIndex],
        u_map: dict[str, ArrayIndex],
        k_map: dict[str, ArrayIndex],
        algebraic_map: dict[str, ArrayIndex],
    ) -> FloatArray:
        del t, y, k, y_map, k_map
        dy: FloatArray = np.zeros(1, dtype=np.float64)
        heater = float(u[u_map["heater_power"]])
        cooling = float(algebraic[algebraic_map["heat_flux"]])
        dy[0] = heater - cooling
        return dy


def _valve_system() -> HydraulicSystemDefinition:
    return HydraulicSystemDefinition(
        equations=(
            ElementEquation(
                name="eq_line_feed",
                element=cast(
                    HydraulicElement,
                    cast(object, ValveHydraulicElement()),
                ),
                inputs=MappingProxyType(
                    {
                        "upstream_pressure": 120_000.0,
                        "downstream_pressure": 100_000.0,
                    }
                ),
                parameters=MappingProxyType(
                    {
                        "valve_resistance": 1.0,
                        "delta": 1.0e-3,
                    }
                ),
                unknown_name_map=MappingProxyType({"flow_rate": "flow_line_feed"}),
                residual_name_map=MappingProxyType({"head_balance": "head_balance_line_feed"}),
            ),
        ),
        linear_residual_equations=(),
    )


def _build_system(process_model: ProcessModel) -> System:
    base_sensor = SampledDelayedSensor(
        name="temperature_sensor",
        measurement_tag="temperature",
        alias_tag="temperature",
        unit="K",
        sampling_period=0.0,
        deadtime=0.0,
    )
    heater = ControlElement(
        mv_tag="heater_power",
        mv_trajectory=Trajectory(y0=0.0, t0=0.0),
        mv_range=(0.0, 20.0),
        mode=ControllerMode.MANUAL,
    )
    return System(
        dt=1.0,
        process_model=process_model,
        sensors=[base_sensor],
        calculations=[],
        control_elements=[heater],
        show_progress=False,
    )


def _runtime_with_dispatchers(system: System) -> ConnectionRuntimeOrchestrator:
    def sensor_dispatcher(
        *, operation: str, mutation: Mapping[str, object], request_metadata: Mapping[str, object]
    ) -> None:
        system.apply_sensor_runtime_mutation(
            operation=operation,
            mutation=mutation,
            request_metadata=request_metadata,
        )

    def controller_dispatcher(
        *, operation: str, mutation: Mapping[str, object], request_metadata: Mapping[str, object]
    ) -> None:
        system.apply_controller_runtime_mutation(
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
        return compiled.hydraulic.solve()

    return ConnectionRuntimeOrchestrator(
        hydraulic_solve_step=hydraulic_solve_step,
        sensor_mutation_dispatcher=sensor_dispatcher,
        controller_mutation_dispatcher=controller_dispatcher,
    )


def _network(runtime: ConnectionRuntimeOrchestrator) -> ConnectionNetwork:
    network = ConnectionNetwork(
        compile_lifecycle=HydraulicCompileLifecycle(),
        hydraulic_system_builder=lambda topology: _valve_system(),
        runtime_orchestrator=runtime,
    )
    network.add_process("reactor", inlet_ports=("feed",), outlet_ports=("product",))
    network.add_boundary_source("feed_boundary")
    network.add_boundary_sink("product_boundary")
    _ = network.connect("feed_boundary", "reactor.feed")
    _ = network.connect("reactor.product", "product_boundary")
    _ = network.compile()
    return network


def _attached_model() -> ThermalProcessModel:
    model = ThermalProcessModel()
    dummy_system = SimpleNamespace(
        solver_options={"method": "RK45", "rtol": 1e-8, "atol": 1e-10},
        use_numba=False,
        numba_options={},
    )
    model.attach_system(cast(System, cast(object, dummy_system)))
    return model


def run_demo() -> dict[str, object]:
    process_model = _attached_model()
    system = _build_system(process_model)
    runtime = _runtime_with_dispatchers(system)
    network = _network(runtime)

    unit_api = DynamicUnitPortReconfigurationApi(network=network)
    line_api = DynamicConnectionLineReconfigurationApi(network=network)
    sensor_api = SensorRuntimeBindingApi(network=network)
    controller_api = ControllerRuntimeWiringApi(network=network)

    request_ids = (
        unit_api.add_inlet(process_id="reactor", port_id="recycle"),
        unit_api.add_outlet(process_id="reactor", port_id="purge"),
        network.queue_reconfiguration(
            {
                "operation": "add_boundary_sink",
                "boundary_id": "purge_boundary",
            }
        ),
        line_api.connect_line(
            source="reactor.purge",
            target="purge_boundary.inlet",
            line_id="purge_line",
        ),
        line_api.configure_line_geometry(
            line_id="purge_line",
            radius_m=0.05,
            length_m=2.0,
            equation_name="eq_line_feed",
            resistance_parameter_name="valve_resistance",
        ),
        line_api.use_derived_resistance(line_id="purge_line"),
        line_api.attach_line_valve(
            line_id="purge_line",
            valve=ValveConfig(
                valve_id="purge_valve",
                minimum_open_fraction=0.1,
                maximum_open_fraction=1.0,
                initial_open_fraction=0.6,
            ),
        ),
        sensor_api.create_sensor(
            sensor_id="runtime_temp_probe",
            signal_key="temperature",
            process_id="reactor",
            port_id="feed",
            sensor_config={"unit": "K", "sampling_period": 0.0, "deadtime": 0.0},
        ),
        controller_api.create_controller(
            controller_id="heater_pid",
            controller_type="PIDController",
            controller_module="modular_simulation.components.control_system.controllers",
            controller_config={
                "name": "heater_pid",
                "cv_range": (250.0, 350.0),
                "Kp": 4.0,
                "Ti": 5.0,
                "Td": 0.0,
            },
        ),
        controller_api.bind_controller_input(
            controller_id="heater_pid",
            signal_key="temperature",
        ),
        controller_api.bind_controller_output(
            controller_id="heater_pid",
            actuator_tag="heater_power",
        ),
        controller_api.configure_controller_mode(
            controller_id="heater_pid",
            mode="auto",
        ),
        controller_api.activate_controller(controller_id="heater_pid"),
    )
    apply_result = cast(ConnectionRuntimeStepResult, network.step(macro_step_time_s=0.25))
    _ = request_ids

    _ = system.extend_controller_reference_trajectory("temperature", value=320.0)
    system.step(duration=1.0)
    heater_power = float(process_model.heater_power)
    if heater_power <= 0.0:
        raise RuntimeError("controller loop failed to move heater_power above zero")

    api_checkpoint = network.save_runtime_snapshot()
    _ = network.queue_reconfiguration(
        {
            "operation": "batch_update",
            "mutations": [
                {
                    "operation": "set_valve_open_fraction",
                    "line_id": "purge_line",
                    "open_fraction": 0.8,
                }
            ],
        }
    )
    _ = network.step(macro_step_time_s=0.25)
    network.resume_from_snapshot(snapshot=api_checkpoint)
    api_round_trip_ok = network.save_runtime_snapshot() == api_checkpoint

    cli = ModularCli(network=network)
    cli_checkpoint = cli.save()
    with TemporaryDirectory() as tmp_dir:
        checkpoint_path = Path(tmp_dir) / "checkpoint.json"
        _ = checkpoint_path.write_text(json.dumps(cli_checkpoint), encoding="utf-8")
        _ = network.queue_reconfiguration(
            {
                "operation": "add_boundary_sink",
                "boundary_id": "transient_sink",
            }
        )
        _ = network.step(macro_step_time_s=0.25)
        cli.load(str(checkpoint_path))
    continue_request = network.queue_reconfiguration(
        {
            "operation": "batch_update",
            "mutations": [
                {
                    "operation": "set_valve_open_fraction",
                    "line_id": "purge_line",
                    "open_fraction": 0.7,
                }
            ],
        }
    )
    continue_result = cast(ConnectionRuntimeStepResult, network.step(macro_step_time_s=0.25))
    cli_round_trip_ok = continue_result.barrier_reconfiguration.applied_request_ids == (
        continue_request,
    )

    return {
        "applied_request_ids": tuple(apply_result.barrier_reconfiguration.applied_request_ids),
        "heater_power": heater_power,
        "api_round_trip_ok": api_round_trip_ok,
        "cli_round_trip_ok": cli_round_trip_ok,
    }


if __name__ == "__main__":
    print(run_demo())
