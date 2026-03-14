from __future__ import annotations

# pyright: reportMissingTypeStubs=false

from collections.abc import Mapping
from types import MappingProxyType
from typing import cast

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
from modular_simulation.connection.runtime_persistence import (
    restore_runtime_snapshot_contract,
    runtime_replay_state_hash,
    save_runtime_snapshot_contract,
)
from modular_simulation.framework.system import System
from modular_simulation.measurables.process_model import ProcessModel


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
    heat_actuator_element = ControlElement(
        mv_tag="actuator/heat/purge_heater",
        mv_trajectory=Trajectory(y0=0.0, t0=0.0),
        mv_range=(0.0, 20.0),
        mode=ControllerMode.MANUAL,
    )
    return System(
        dt=1.0,
        process_model=process_model,
        sensors=[base_sensor],
        calculations=[],
        control_elements=[heat_actuator_element],
        show_progress=False,
    )


def _runtime_with_dispatchers(system: System) -> ConnectionRuntimeOrchestrator:
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

    def controller_dispatcher(
        *,
        operation: str,
        mutation: Mapping[str, object],
        request_metadata: Mapping[str, object],
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
        pending_valve_commands = network.consume_pending_valve_open_fraction_commands()
        hydraulic = compiled.hydraulic
        if pending_valve_commands:
            hydraulic = hydraulic.with_valve_commands(pending_valve_commands)
            network.replace_compiled_hydraulic(hydraulic=hydraulic)
        pending_heat_commands = network.consume_pending_heat_actuator_rate_commands()
        if pending_heat_commands:
            network.apply_heat_actuator_rate_commands(pending_heat_commands)
        return hydraulic.solve()

    return ConnectionRuntimeOrchestrator(
        hydraulic_solve_step=hydraulic_solve_step,
        sensor_mutation_dispatcher=sensor_dispatcher,
        controller_mutation_dispatcher=controller_dispatcher,
        heat_actuator_command_provider=system.consume_pending_heat_actuator_rate_commands,
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


def _require_float_attribute(instance: object, attribute_name: str) -> float:
    value = getattr(instance, attribute_name, None)
    if not isinstance(value, (int, float)):
        raise AssertionError(f"attribute '{attribute_name}' must be numeric")
    return float(value)


def test_dynamic_process_network_workflow_valve_actuation_end_to_end(
    thermal_process_model: ProcessModel,
) -> None:
    system = _build_system(thermal_process_model)
    runtime = _runtime_with_dispatchers(system)
    network = _network(runtime)

    unit_api = DynamicUnitPortReconfigurationApi(network=network)
    line_api = DynamicConnectionLineReconfigurationApi(network=network)
    sensor_api = SensorRuntimeBindingApi(network=network)
    controller_api = ControllerRuntimeWiringApi(network=network)
    request_ids = [
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
            expected_revision="graph_rev_0001",
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
        line_api.attach_line_heat_actuator(
            line_id="purge_line",
            heat_actuator_id="purge_heater",
            initial_heat_rate=0.0,
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
            actuator_tag="actuator/heat/purge_heater",
        ),
        controller_api.configure_controller_mode(
            controller_id="heater_pid",
            mode="auto",
        ),
        controller_api.activate_controller(controller_id="heater_pid"),
    ]
    expected_request_ids = tuple(f"rq_{index:04d}" for index in range(1, 15))
    assert tuple(request_ids) == expected_request_ids

    apply_result = cast(ConnectionRuntimeStepResult, network.step(macro_step_time_s=0.25))
    assert apply_result.barrier_reconfiguration.applied_request_ids == expected_request_ids
    assert apply_result.barrier_reconfiguration.skipped_request_ids == ()
    assert apply_result.graph_revision == "graph_rev_0002"

    compiled = network.compiled
    assert compiled is not None and compiled.hydraulic is not None
    boundary_ids = tuple(node.boundary_id for node in compiled.topology.boundary_nodes)
    assert boundary_ids == ("feed_boundary", "product_boundary", "purge_boundary")
    edge_by_id = {
        edge.edge_id: (
            f"{edge.source.node_id}.{edge.source.port_name}",
            f"{edge.target.node_id}.{edge.target.port_name}",
        )
        for edge in compiled.topology.edges
    }
    assert edge_by_id["purge_line"] == ("reactor.purge", "purge_boundary.inlet")
    valve_state = compiled.hydraulic.valve_state_by_line["purge_line"]
    assert valve_state.valve_id == "purge_valve"
    assert abs(valve_state.current_open_fraction - 0.6) < 1.0e-12
    assert network.list_line_heat_actuator_ids() == (("purge_line", "purge_heater"),)
    assert network.list_heat_actuator_rates() == (("purge_line", 0.0),)

    assert "runtime_temp_probe" in system.sensor_bindings
    assert system.sensor_bindings["runtime_temp_probe"].signal_key == "temperature"
    assert "heater_pid" in system.controller_bindings
    assert system.controller_bindings["heater_pid"].actuator_tag == "actuator/heat/purge_heater"
    assert system.controller_bindings["heater_pid"].mode == "auto"
    assert system.control_elements[0].controller is not None

    _ = system.extend_controller_reference_trajectory("temperature", value=320.0)
    system.step(duration=1.0)
    assert _require_float_attribute(thermal_process_model, "heater_power") == 0.0

    controller_continue_result = cast(
        ConnectionRuntimeStepResult, network.step(macro_step_time_s=0.25)
    )
    assert controller_continue_result.barrier_reconfiguration.applied_request_ids == ()
    assert network.list_heat_actuator_rates() == (("purge_line", 20.0),)

    process_runtime_state: dict[str, object] = {
        "reactor": {
            "temperature": _require_float_attribute(thermal_process_model, "temperature"),
        }
    }
    checkpoint = save_runtime_snapshot_contract(
        runtime=runtime,
        network=network,
        process_runtime_state=process_runtime_state,
    )
    assert checkpoint["graph_revision"] == "graph_rev_0002"
    assert checkpoint["pending_command_journal"] == []

    first_continue_request = line_api.set_valve_open_fraction(
        actuator_tag="actuator/valve/purge_valve",
        open_fraction=0.8,
    )
    assert first_continue_request == "rq_0015"
    first_continue_result = cast(ConnectionRuntimeStepResult, network.step(macro_step_time_s=0.25))
    assert first_continue_result.barrier_reconfiguration.applied_request_ids == ("rq_0015",)
    compiled_after_first_continue = network.compiled
    assert compiled_after_first_continue is not None
    assert compiled_after_first_continue.graph_revision == "graph_rev_0002"
    assert compiled_after_first_continue.hydraulic is not None
    assert (
        compiled_after_first_continue.hydraulic.valve_state_by_line[
            "purge_line"
        ].current_open_fraction
        == 0.8
    )
    first_continue_hash = runtime_replay_state_hash(
        tick=13,
        runtime=runtime,
        network=network,
        process_runtime_state=process_runtime_state,
    )

    second_continue_request = line_api.set_heat_actuator_rate(
        actuator_tag="actuator/heat/purge_heater",
        heat_rate=7.5,
    )
    assert second_continue_request == "rq_0016"
    second_continue_result = cast(ConnectionRuntimeStepResult, network.step(macro_step_time_s=0.25))
    assert second_continue_result.barrier_reconfiguration.applied_request_ids == ("rq_0016",)
    compiled_after_second_continue = network.compiled
    assert compiled_after_second_continue is not None
    assert compiled_after_second_continue.graph_revision == "graph_rev_0002"
    assert network.list_heat_actuator_rates() == (("purge_line", 7.5),)

    _ = network.queue_reconfiguration(
        {
            "operation": "add_boundary_sink",
            "boundary_id": "transient_sink",
        }
    )
    runtime.set_runtime_state(
        simulation_time_s=99.0,
        macro_step_index=99,
        macro_step_active=False,
        committed_idempotency_keys=runtime.committed_idempotency_keys,
    )
    restore_runtime_snapshot_contract(
        runtime=runtime,
        network=network,
        process_runtime_state_sink=process_runtime_state,
        snapshot=checkpoint,
    )

    restored_checkpoint = save_runtime_snapshot_contract(
        runtime=runtime,
        network=network,
        process_runtime_state=process_runtime_state,
    )
    assert restored_checkpoint == checkpoint

    replay_continue_request = line_api.set_valve_open_fraction(
        actuator_tag="actuator/valve/purge_valve",
        open_fraction=0.8,
    )
    assert replay_continue_request == "rq_0015"
    replay_continue_result = cast(ConnectionRuntimeStepResult, network.step(macro_step_time_s=0.25))
    assert replay_continue_result.barrier_reconfiguration.applied_request_ids == ("rq_0015",)
    replay_continue_hash = runtime_replay_state_hash(
        tick=13,
        runtime=runtime,
        network=network,
        process_runtime_state=process_runtime_state,
    )
    assert replay_continue_hash == first_continue_hash

    replay_second_continue_request = line_api.set_heat_actuator_rate(
        actuator_tag="actuator/heat/purge_heater",
        heat_rate=7.5,
    )
    assert replay_second_continue_request == "rq_0016"
    replay_second_continue_result = cast(
        ConnectionRuntimeStepResult, network.step(macro_step_time_s=0.25)
    )
    assert replay_second_continue_result.barrier_reconfiguration.applied_request_ids == ("rq_0016",)
    assert network.list_heat_actuator_rates() == (("purge_line", 7.5),)
