from __future__ import annotations

# pyright: reportMissingTypeStubs=false

from collections.abc import Callable, Mapping
import importlib
from pathlib import Path
import re
import sys
from typing import cast

import numpy as np
import pytest

from modular_simulation.components.control_system import (
    ControlElement,
    ControllerMode,
    ControllerRuntimeWiringApi,
    Trajectory,
)
from modular_simulation.components.sensors import SampledDelayedSensor
from modular_simulation.connection.hydraulic_compile import (
    HydraulicCompileLifecycle,
)
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
from modular_simulation.unit_processes import (
    CSTR,
    ComponentSeparator,
    ConversionReactor,
    FlashDrum,
    HeaterCooler,
    ShortcutDistillation,
)

try:
    from tests.controller_contract_harness import (
        assert_controller_activation_rolls_back,
        build_canonical_pressure_pump_system,
        build_pressure_pump_system,
        build_scalar_cv_vector_mv_system,
    )
except ModuleNotFoundError:
    sys.path.append(str(Path(__file__).resolve().parents[1]))
    controller_contract_harness = importlib.import_module("controller_contract_harness")
    build_scalar_cv_vector_mv_system = cast(
        Callable[[], System],
        controller_contract_harness.build_scalar_cv_vector_mv_system,
    )
    build_canonical_pressure_pump_system = cast(
        Callable[[], System],
        controller_contract_harness.build_canonical_pressure_pump_system,
    )
    build_pressure_pump_system = cast(
        Callable[[], System],
        controller_contract_harness.build_pressure_pump_system,
    )
    assert_controller_activation_rolls_back = cast(
        Callable[..., None],
        controller_contract_harness.assert_controller_activation_rolls_back,
    )


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


def _runtime_with_dispatchers(
    system: System,
    *,
    solve_observer: Callable[[HydraulicSolveResult], None] | None = None,
) -> ConnectionRuntimeOrchestrator:
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
        result = compiled.hydraulic.solve()
        if solve_observer is not None:
            solve_observer(result)
        return result

    return ConnectionRuntimeOrchestrator(
        hydraulic_solve_step=hydraulic_solve_step,
        controller_mutation_dispatcher=controller_dispatcher,
        heat_actuator_command_provider=system.consume_pending_heat_actuator_rate_commands,
    )


def _build_system(
    process_model: ProcessModel,
) -> System:
    temperature_sensor = SampledDelayedSensor(
        name="temperature_sensor",
        measurement_tag="temperature",
        alias_tag="temperature",
        unit="K",
        sampling_period=0.0,
        deadtime=0.0,
    )
    heater = ControlElement(
        mv_tag="actuator/heat/heater_power",
        mv_trajectory=Trajectory(y0=0.0, t0=0.0),
        mv_range=(0.0, 20.0),
        mode=ControllerMode.MANUAL,
    )
    return System(
        dt=1.0,
        process_model=process_model,
        sensors=[temperature_sensor],
        calculations=[],
        control_elements=[heater],
        show_progress=False,
    )


def _require_float_attribute(instance: object, attribute_name: str) -> float:
    value = getattr(instance, attribute_name, None)
    if not isinstance(value, (int, float)):
        raise AssertionError(f"attribute '{attribute_name}' must be numeric")
    return float(value)


def test_pid_controller_reference_wiring_accepts_configured_external_heat_actuator(
    thermal_process_model: ProcessModel,
) -> None:
    system = _build_system(thermal_process_model)
    runtime = _runtime_with_dispatchers(system)
    network = _network(runtime)
    api = ControllerRuntimeWiringApi(network=network)

    assert (
        api.create_controller(
            controller_id="heater_pid",
            controller_type="PIDController",
            controller_module="modular_simulation.components.control_system.controllers",
            controller_config={
                "name": "heater_pid",
                "cv_range": (250.0, 350.0),
                "Kp": 5.0,
                "Ti": 5.0,
                "Td": 0.0,
            },
        )
        == "rq_0001"
    )
    assert (
        api.bind_controller_input(controller_id="heater_pid", signal_key="temperature") == "rq_0002"
    )
    assert (
        api.bind_controller_output(
            controller_id="heater_pid", actuator_tag="actuator/heat/heater_power"
        )
        == "rq_0003"
    )
    assert api.configure_controller_mode(controller_id="heater_pid", mode="auto") == "rq_0004"
    assert api.activate_controller(controller_id="heater_pid") == "rq_0005"

    step_result = cast(ConnectionRuntimeStepResult, network.step(macro_step_time_s=0.25))
    assert step_result.barrier_reconfiguration.applied_request_ids == (
        "rq_0001",
        "rq_0002",
        "rq_0003",
        "rq_0004",
        "rq_0005",
    )

    assert "heater_pid" in system.controller_bindings
    assert "temperature.ref" in system.point_registry
    assert "temperature.sp" not in system.point_registry

    _ = system.extend_controller_reference_trajectory("temperature", value=320.0)
    system.step(duration=1.0)

    assert _require_float_attribute(thermal_process_model, "heater_power") == 0.0
    pending_heat_commands = system.consume_pending_heat_actuator_rate_commands()
    assert "actuator/heat/heater_power" in pending_heat_commands
    assert pending_heat_commands["actuator/heat/heater_power"] > 0.0


def test_controller_activation_rejects_unmapped_namespaced_heat_actuator_with_rollback(
    thermal_process_model: ProcessModel,
) -> None:
    system = _build_system(thermal_process_model)
    runtime = _runtime_with_dispatchers(system)
    network = _network(runtime)
    api = ControllerRuntimeWiringApi(network=network)

    _queue_pid_activation(
        api,
        controller_id="heater_pid",
        signal_key="temperature",
        actuator_tag="actuator/heat/unconfigured_heater",
    )

    assert_controller_activation_rolls_back(
        network,
        system,
        controller_id="heater_pid",
        absent_reference_tags=("temperature.ref",),
        error_match=re.escape(
            "reconfiguration transaction rollback: request 'rq_0005' mutation 1 failed: "
            + "controller 'heater_pid' references unknown actuator 'actuator/heat/unconfigured_heater'"
        )
        + ".*",
    )


def test_controller_reference_activation_rejects_stale_public_sp_signal_tag(
    thermal_process_model: ProcessModel,
) -> None:
    system = _build_system(thermal_process_model)
    runtime = _runtime_with_dispatchers(system)
    network = _network(runtime)
    api = ControllerRuntimeWiringApi(network=network)

    _ = api.create_controller(
        controller_id="heater_pid",
        controller_type="PIDController",
        controller_module="modular_simulation.components.control_system.controllers",
        controller_config={
            "name": "heater_pid",
            "cv_range": (250.0, 350.0),
            "Kp": 3.0,
            "Ti": 5.0,
            "Td": 0.0,
        },
    )
    _ = api.bind_controller_input(controller_id="heater_pid", signal_key="temperature.sp")
    _ = api.bind_controller_output(
        controller_id="heater_pid", actuator_tag="actuator/heat/heater_power"
    )
    _ = api.configure_controller_mode(controller_id="heater_pid", mode="auto")
    _ = api.activate_controller(controller_id="heater_pid")
    before_failure = network.save_runtime_snapshot()

    with pytest.raises(
        RuntimeError,
        match=(
            "reconfiguration transaction rollback: request 'rq_0005' mutation 1 failed: "
            + "controller 'heater_pid' input signal 'temperature.sp' is unresolved"
        ),
    ):
        _ = network.step(macro_step_time_s=0.25)

    assert network.save_runtime_snapshot() == before_failure
    assert system.control_elements[0].controller is None


def test_controller_activation_rejects_raw_physical_actuator_tag_with_rollback(
    thermal_process_model: ProcessModel,
) -> None:
    system = _build_system(thermal_process_model)
    runtime = _runtime_with_dispatchers(system)
    network = _network(runtime)
    api = ControllerRuntimeWiringApi(network=network)

    _queue_pid_activation(
        api,
        controller_id="heater_pid",
        signal_key="temperature",
        actuator_tag="(raw, CONTROLLED)_heater_power",
    )

    assert_controller_activation_rolls_back(
        network,
        system,
        controller_id="heater_pid",
        absent_reference_tags=("temperature.ref",),
        error_match=re.escape(
            "reconfiguration transaction rollback: request 'rq_0005' mutation 1 failed: "
            + "controller 'heater_pid' cannot bind actuator '(raw, CONTROLLED)_heater_power': "
            + "actuator '(raw, CONTROLLED)_heater_power' is not controller-bindable; expected canonical actuator namespace tag 'actuator/valve/<id>', 'actuator/pump/<id>', or 'actuator/heat/<id>'"
        )
        + ".*",
    )


def test_controller_activation_characterizes_direct_process_heater_power_rejection_with_rollback(
    thermal_process_model: ProcessModel,
) -> None:
    system = _build_system(thermal_process_model)
    runtime = _runtime_with_dispatchers(system)
    network = _network(runtime)
    api = ControllerRuntimeWiringApi(network=network)

    _queue_pid_activation(
        api,
        controller_id="heater_pid",
        signal_key="temperature",
        actuator_tag="heater_power",
    )

    assert_controller_activation_rolls_back(
        network,
        system,
        controller_id="heater_pid",
        absent_reference_tags=("temperature.ref",),
        error_match=re.escape(
            "reconfiguration transaction rollback: request 'rq_0005' mutation 1 failed: "
            + "controller 'heater_pid' cannot bind actuator 'heater_power': actuator 'heater_power' is not controller-bindable; expected canonical actuator namespace tag 'actuator/valve/<id>', 'actuator/pump/<id>', or 'actuator/heat/<id>'"
        )
        + ".*",
    )


def test_controller_activation_rejects_unresolved_signal_tag(
    thermal_process_model: ProcessModel,
) -> None:
    system = _build_system(thermal_process_model)
    runtime = _runtime_with_dispatchers(system)
    network = _network(runtime)
    api = ControllerRuntimeWiringApi(network=network)

    _ = api.create_controller(
        controller_id="heater_pid",
        controller_type="PIDController",
        controller_module="modular_simulation.components.control_system.controllers",
        controller_config={
            "name": "heater_pid",
            "cv_range": (250.0, 350.0),
            "Kp": 3.0,
            "Ti": 5.0,
            "Td": 0.0,
        },
    )
    _ = api.bind_controller_input(controller_id="heater_pid", signal_key="unknown_tag")
    _ = api.bind_controller_output(
        controller_id="heater_pid", actuator_tag="actuator/heat/heater_power"
    )
    _ = api.configure_controller_mode(controller_id="heater_pid", mode="auto")
    _ = api.activate_controller(controller_id="heater_pid")
    before_failure = network.save_runtime_snapshot()

    with pytest.raises(
        RuntimeError,
        match=(
            "reconfiguration transaction rollback: request 'rq_0005' mutation 1 failed: "
            + "controller 'heater_pid' input signal 'unknown_tag' is unresolved"
        ),
    ):
        _ = network.step(macro_step_time_s=0.25)

    assert network.save_runtime_snapshot() == before_failure
    assert system.control_elements[0].controller is None


def test_controller_activation_rejects_removed_flash_pressure_tag_with_rollback() -> None:
    sensor = SampledDelayedSensor(
        name="flash_removed_pressure_sensor",
        measurement_tag="outlet_temperature",
        alias_tag="temperature",
        unit="K",
        sampling_period=0.0,
        deadtime=0.0,
    )
    control_element = ControlElement(
        mv_tag="inlet_flow",
        mv_trajectory=Trajectory(y0=0.0, t0=0.0),
        mv_range=(0.0, 20.0),
        mode=ControllerMode.MANUAL,
    )
    system = System(
        dt=1.0,
        process_model=FlashDrum(n_species=2),
        sensors=[sensor],
        calculations=[],
        control_elements=[control_element],
        show_progress=False,
    )
    runtime = _runtime_with_dispatchers(system)
    network = _network(runtime)
    api = ControllerRuntimeWiringApi(network=network)

    _queue_pid_activation(
        api,
        controller_id="flash_removed_pressure_controller",
        signal_key="temperature",
        actuator_tag="actuator/heat/flash_pressure",
    )
    before_failure = network.save_runtime_snapshot()

    with pytest.raises(
        RuntimeError,
        match=(
            "reconfiguration transaction rollback: request 'rq_0005' mutation 1 failed: "
            + "controller 'flash_removed_pressure_controller' references unknown actuator "
            + "'actuator/heat/flash_pressure'"
        ),
    ):
        _ = network.step(macro_step_time_s=0.25)

    assert network.save_runtime_snapshot() == before_failure
    assert system.control_elements[0].controller is None


@pytest.mark.parametrize(
    ("controller_id", "process_model", "actuator_tag", "error_fragment"),
    (
        (
            "heater_removed_duty_proxy_controller",
            HeaterCooler(n_species=2),
            "actuator/heat/duty_setpoint",
            "controller 'heater_removed_duty_proxy_controller' cannot bind actuator 'actuator/heat/duty_setpoint': actuator 'actuator/heat/duty_setpoint' is banned by contract",
        ),
        (
            "heater_removed_temperature_proxy_controller",
            HeaterCooler(n_species=2),
            "actuator/heat/target_temperature_setpoint",
            "controller 'heater_removed_temperature_proxy_controller' cannot bind actuator 'actuator/heat/target_temperature_setpoint': actuator 'actuator/heat/target_temperature_setpoint' is banned by contract",
        ),
        (
            "heater_hydraulic_drop_controller",
            HeaterCooler(n_species=2),
            "actuator/heat/pressure_drop",
            "controller 'heater_hydraulic_drop_controller' references unknown actuator 'actuator/heat/pressure_drop'",
        ),
        (
            "conversion_reactor_hydraulic_drop_controller",
            ConversionReactor(n_species=2),
            "actuator/heat/pressure_drop",
            "controller 'conversion_reactor_hydraulic_drop_controller' references unknown actuator 'actuator/heat/pressure_drop'",
        ),
    ),
)
def test_controller_activation_rejects_removed_or_demoted_thermal_proxy_actuators_with_rollback(
    controller_id: str,
    process_model: ProcessModel,
    actuator_tag: str,
    error_fragment: str,
) -> None:
    sensor = SampledDelayedSensor(
        name=f"{controller_id}_sensor",
        measurement_tag="outlet_temperature",
        alias_tag="temperature",
        unit="K",
        sampling_period=0.0,
        deadtime=0.0,
    )
    control_element = ControlElement(
        mv_tag="inlet_temperature",
        mv_trajectory=Trajectory(y0=300.0, t0=0.0),
        mv_range=(250.0, 450.0),
        mode=ControllerMode.MANUAL,
    )
    system = System(
        dt=1.0,
        process_model=process_model,
        sensors=[sensor],
        calculations=[],
        control_elements=[control_element],
        show_progress=False,
    )
    runtime = _runtime_with_dispatchers(system)
    network = _network(runtime)
    api = ControllerRuntimeWiringApi(network=network)

    _queue_pid_activation(
        api,
        controller_id=controller_id,
        signal_key="temperature",
        actuator_tag=actuator_tag,
    )
    before_failure = network.save_runtime_snapshot()

    with pytest.raises(
        RuntimeError,
        match=(
            "reconfiguration transaction rollback: request 'rq_0005' mutation 1 failed: "
            + error_fragment
        ),
    ):
        _ = network.step(macro_step_time_s=0.25)

    assert network.save_runtime_snapshot() == before_failure
    assert system.control_elements[0].controller is None


def test_controller_activation_rejects_scalar_vector_mismatch_with_rollback() -> None:
    system = build_scalar_cv_vector_mv_system()
    runtime = _runtime_with_dispatchers(system)
    network = _network(runtime)
    api = ControllerRuntimeWiringApi(network=network)

    _queue_pid_activation(
        api,
        controller_id="vector_mismatch_pid",
        signal_key="temperature",
        actuator_tag="actuator/heat/heater_power_vector",
    )
    before_failure = network.save_runtime_snapshot()

    with pytest.raises(
        RuntimeError,
        match=(
            "reconfiguration transaction rollback: request 'rq_0005' mutation 1 failed: "
            + "controller 'vector_mismatch_pid' input/output dimensionality is incompatible "
            + "with actuator 'actuator/heat/heater_power_vector'"
        ),
    ):
        _ = network.step(macro_step_time_s=0.25)

    assert network.save_runtime_snapshot() == before_failure
    assert system.control_elements[0].controller is None
    assert "temperature.ref" not in system.point_registry


def test_controller_activation_characterizes_raw_controlled_pump_speed_rejection_with_rollback() -> (
    None
):
    system = build_pressure_pump_system()
    runtime = _runtime_with_dispatchers(system)
    network = _network(runtime)
    api = ControllerRuntimeWiringApi(network=network)

    _queue_pid_activation(
        api,
        controller_id="pump_pid",
        signal_key="pressure",
        actuator_tag="(raw, CONTROLLED)_pump_speed",
    )

    assert_controller_activation_rolls_back(
        network,
        system,
        controller_id="pump_pid",
        absent_reference_tags=("pressure.ref",),
        error_match=re.escape(
            "reconfiguration transaction rollback: request 'rq_0005' mutation 1 failed: "
            + "controller 'pump_pid' cannot bind actuator '(raw, CONTROLLED)_pump_speed': actuator '(raw, CONTROLLED)_pump_speed' is not controller-bindable; expected canonical actuator namespace tag 'actuator/valve/<id>', 'actuator/pump/<id>', or 'actuator/heat/<id>'"
        )
        + ".*",
    )


def test_pid_controller_reference_wiring_accepts_configured_canonical_pump_actuator() -> None:
    system = build_canonical_pressure_pump_system()
    runtime = _runtime_with_dispatchers(system)
    network = _network(runtime)
    api = ControllerRuntimeWiringApi(network=network)

    _queue_pid_activation(
        api,
        controller_id="pump_pid",
        signal_key="pressure",
        actuator_tag="actuator/pump/recycle_pump",
    )

    step_result = cast(ConnectionRuntimeStepResult, network.step(macro_step_time_s=0.25))
    assert step_result.barrier_reconfiguration.applied_request_ids == (
        "rq_0001",
        "rq_0002",
        "rq_0003",
        "rq_0004",
        "rq_0005",
    )
    assert "pump_pid" in system.controller_bindings
    assert system.controller_bindings["pump_pid"].actuator_tag == "actuator/pump/recycle_pump"

    _ = system.extend_controller_reference_trajectory("pressure", value=150000.0)
    system.step(duration=1.0)

    actuator_command = system.point_registry["actuator/pump/recycle_pump"].data.value
    assert isinstance(actuator_command, (int, float, np.floating))
    assert float(actuator_command) > 20000.0


def test_controller_activation_rejects_canonical_pump_suffix_alias_without_exact_binding() -> None:
    system = build_pressure_pump_system()
    runtime = _runtime_with_dispatchers(system)
    network = _network(runtime)
    api = ControllerRuntimeWiringApi(network=network)

    _queue_pid_activation(
        api,
        controller_id="pump_pid",
        signal_key="pressure",
        actuator_tag="actuator/pump/pump_speed",
    )

    assert_controller_activation_rolls_back(
        network,
        system,
        controller_id="pump_pid",
        absent_reference_tags=("pressure.ref",),
        error_match=re.escape(
            "reconfiguration transaction rollback: request 'rq_0005' mutation 1 failed: "
            + "controller 'pump_pid' references unknown actuator 'actuator/pump/pump_speed'"
        )
        + ".*",
    )


def _queue_pid_activation(
    api: ControllerRuntimeWiringApi,
    *,
    controller_id: str,
    signal_key: str,
    actuator_tag: str,
) -> None:
    _ = api.create_controller(
        controller_id=controller_id,
        controller_type="PIDController",
        controller_module="modular_simulation.components.control_system.controllers",
        controller_config={
            "name": controller_id,
            "cv_range": (0.0, 1.0),
            "Kp": 3.0,
            "Ti": 5.0,
            "Td": 0.0,
        },
    )
    _ = api.bind_controller_input(controller_id=controller_id, signal_key=signal_key)
    _ = api.bind_controller_output(controller_id=controller_id, actuator_tag=actuator_tag)
    _ = api.configure_controller_mode(controller_id=controller_id, mode="auto")
    _ = api.activate_controller(controller_id=controller_id)


@pytest.mark.parametrize(
    (
        "controller_id",
        "process_model",
        "sensor_tag",
        "signal_key",
        "sensor_unit",
        "actuator_tag",
        "mv_range",
        "control_element_tag",
    ),
    (
        (
            "flash_banned_setpoint_controller",
            FlashDrum(n_species=2),
            "outlet_temperature",
            "temperature",
            "K",
            "actuator/heat/flash_temperature_setpoint",
            (250.0, 400.0),
            "inlet_flow",
        ),
    ),
)
def test_controller_activation_rejects_banned_setpoint_actuator_with_rollback(
    controller_id: str,
    process_model: ProcessModel,
    sensor_tag: str,
    signal_key: str,
    sensor_unit: str,
    actuator_tag: str,
    mv_range: tuple[float, float],
    control_element_tag: str,
) -> None:
    sensor = SampledDelayedSensor(
        name=f"{controller_id}_sensor",
        measurement_tag=sensor_tag,
        alias_tag=signal_key,
        unit=sensor_unit,
        sampling_period=0.0,
        deadtime=0.0,
    )
    control_element = ControlElement(
        mv_tag=control_element_tag,
        mv_trajectory=Trajectory(y0=mv_range[0], t0=0.0),
        mv_range=mv_range,
        mode=ControllerMode.MANUAL,
    )
    system = System(
        dt=1.0,
        process_model=process_model,
        sensors=[sensor],
        calculations=[],
        control_elements=[control_element],
        show_progress=False,
    )
    runtime = _runtime_with_dispatchers(system)
    network = _network(runtime)
    api = ControllerRuntimeWiringApi(network=network)

    _queue_pid_activation(
        api,
        controller_id=controller_id,
        signal_key=signal_key,
        actuator_tag=actuator_tag,
    )
    assert_controller_activation_rolls_back(
        network,
        system,
        controller_id=controller_id,
        absent_reference_tags=(f"{signal_key}.ref",),
        error_match=(
            "reconfiguration transaction rollback: request 'rq_0005' mutation 1 failed: "
            + f"controller '{controller_id}' cannot bind actuator '{actuator_tag}': "
            + f"actuator '{actuator_tag}' is banned by contract"
        ),
    )


@pytest.mark.parametrize(
    (
        "controller_id",
        "process_model",
        "sensor_tag",
        "signal_key",
        "sensor_unit",
        "actuator_tag",
        "mv_range",
        "control_element_tag",
        "error_fragment",
    ),
    (
        (
            "separator_removed_split_fraction_controller",
            ComponentSeparator(
                n_species=2,
                configured_split_fraction_targets=np.array([0.5, 0.5], dtype=np.float64),
            ),
            "outlet_1_flow",
            "separator_flow",
            "mol/s",
            "actuator/heat/split_fractions",
            (0.0, 10.0),
            "inlet_flow",
            "controller 'separator_removed_split_fraction_controller' references unknown actuator 'actuator/heat/split_fractions'",
        ),
        (
            "distillation_removed_reflux_ratio_controller",
            ShortcutDistillation(n_species=2, light_key_index=0, heavy_key_index=1),
            "minimum_reflux_ratio",
            "minimum_reflux",
            "",
            "actuator/heat/reflux_ratio_setpoint",
            (0.0, 10.0),
            "inlet_flow",
            "controller 'distillation_removed_reflux_ratio_controller' cannot bind actuator 'actuator/heat/reflux_ratio_setpoint': actuator 'actuator/heat/reflux_ratio_setpoint' is banned by contract",
        ),
        (
            "distillation_removed_lk_recovery_controller",
            ShortcutDistillation(n_species=2, light_key_index=0, heavy_key_index=1),
            "minimum_reflux_ratio",
            "minimum_reflux",
            "",
            "actuator/heat/light_key_distillate_recovery",
            (0.0, 10.0),
            "inlet_flow",
            "controller 'distillation_removed_lk_recovery_controller' references unknown actuator 'actuator/heat/light_key_distillate_recovery'",
        ),
        (
            "distillation_removed_hk_recovery_controller",
            ShortcutDistillation(n_species=2, light_key_index=0, heavy_key_index=1),
            "minimum_reflux_ratio",
            "minimum_reflux",
            "",
            "actuator/heat/heavy_key_bottoms_recovery",
            (0.0, 10.0),
            "inlet_flow",
            "controller 'distillation_removed_hk_recovery_controller' references unknown actuator 'actuator/heat/heavy_key_bottoms_recovery'",
        ),
        (
            "distillation_removed_reflux_factor_controller",
            ShortcutDistillation(n_species=2, light_key_index=0, heavy_key_index=1),
            "minimum_reflux_ratio",
            "minimum_reflux",
            "",
            "actuator/heat/reflux_ratio_factor",
            (0.0, 10.0),
            "inlet_flow",
            "controller 'distillation_removed_reflux_factor_controller' references unknown actuator 'actuator/heat/reflux_ratio_factor'",
        ),
    ),
)
def test_controller_activation_rejects_removed_separator_and_distillation_pseudo_actuators_with_rollback(
    controller_id: str,
    process_model: ProcessModel,
    sensor_tag: str,
    signal_key: str,
    sensor_unit: str,
    actuator_tag: str,
    mv_range: tuple[float, float],
    control_element_tag: str,
    error_fragment: str,
) -> None:
    sensor = SampledDelayedSensor(
        name=f"{controller_id}_sensor",
        measurement_tag=sensor_tag,
        alias_tag=signal_key,
        unit=sensor_unit,
        sampling_period=0.0,
        deadtime=0.0,
    )
    control_element = ControlElement(
        mv_tag=control_element_tag,
        mv_trajectory=Trajectory(y0=mv_range[0], t0=0.0),
        mv_range=mv_range,
        mode=ControllerMode.MANUAL,
    )
    system = System(
        dt=1.0,
        process_model=process_model,
        sensors=[sensor],
        calculations=[],
        control_elements=[control_element],
        show_progress=False,
    )
    runtime = _runtime_with_dispatchers(system)
    network = _network(runtime)
    api = ControllerRuntimeWiringApi(network=network)

    _queue_pid_activation(
        api,
        controller_id=controller_id,
        signal_key=signal_key,
        actuator_tag=actuator_tag,
    )
    before_failure = network.save_runtime_snapshot()

    with pytest.raises(
        RuntimeError,
        match=(
            "reconfiguration transaction rollback: request 'rq_0005' mutation 1 failed: "
            + error_fragment
        ),
    ):
        _ = network.step(macro_step_time_s=0.25)

    assert network.save_runtime_snapshot() == before_failure
    assert system.control_elements[0].controller is None


@pytest.mark.parametrize(
    (
        "controller_id",
        "process_model",
        "sensor_tag",
        "signal_key",
        "sensor_unit",
        "actuator_tag",
        "mv_range",
        "control_element_tag",
    ),
    (
        (
            "separator_configured_split_fraction_controller",
            ComponentSeparator(
                n_species=2,
                configured_split_fraction_targets=np.array([0.5, 0.5], dtype=np.float64),
            ),
            "outlet_1_flow",
            "separator_flow",
            "mol/s",
            "configured_split_fraction_targets",
            (0.0, 10.0),
            "inlet_flow",
        ),
        (
            "distillation_configured_lk_recovery_controller",
            ShortcutDistillation(n_species=2, light_key_index=0, heavy_key_index=1),
            "minimum_reflux_ratio",
            "minimum_reflux",
            "",
            "configured_light_key_distillate_recovery_target",
            (0.0, 10.0),
            "inlet_flow",
        ),
        (
            "distillation_configured_hk_recovery_controller",
            ShortcutDistillation(n_species=2, light_key_index=0, heavy_key_index=1),
            "minimum_reflux_ratio",
            "minimum_reflux",
            "",
            "configured_heavy_key_bottoms_recovery_target",
            (0.0, 10.0),
            "inlet_flow",
        ),
        (
            "distillation_configured_reflux_target_controller",
            ShortcutDistillation(n_species=2, light_key_index=0, heavy_key_index=1),
            "minimum_reflux_ratio",
            "minimum_reflux",
            "",
            "configured_reflux_ratio_target",
            (0.0, 10.0),
            "inlet_flow",
        ),
        (
            "distillation_configured_reflux_factor_controller",
            ShortcutDistillation(n_species=2, light_key_index=0, heavy_key_index=1),
            "minimum_reflux_ratio",
            "minimum_reflux",
            "",
            "configured_minimum_reflux_ratio_factor",
            (0.0, 10.0),
            "inlet_flow",
        ),
    ),
)
def test_controller_activation_rejects_configured_separator_and_distillation_specs_with_rollback(
    controller_id: str,
    process_model: ProcessModel,
    sensor_tag: str,
    signal_key: str,
    sensor_unit: str,
    actuator_tag: str,
    mv_range: tuple[float, float],
    control_element_tag: str,
) -> None:
    sensor = SampledDelayedSensor(
        name=f"{controller_id}_sensor",
        measurement_tag=sensor_tag,
        alias_tag=signal_key,
        unit=sensor_unit,
        sampling_period=0.0,
        deadtime=0.0,
    )
    control_element = ControlElement(
        mv_tag=control_element_tag,
        mv_trajectory=Trajectory(y0=mv_range[0], t0=0.0),
        mv_range=mv_range,
        mode=ControllerMode.MANUAL,
    )
    system = System(
        dt=1.0,
        process_model=process_model,
        sensors=[sensor],
        calculations=[],
        control_elements=[control_element],
        show_progress=False,
    )
    runtime = _runtime_with_dispatchers(system)
    network = _network(runtime)
    api = ControllerRuntimeWiringApi(network=network)

    _queue_pid_activation(
        api,
        controller_id=controller_id,
        signal_key=signal_key,
        actuator_tag=actuator_tag,
    )
    before_failure = network.save_runtime_snapshot()

    with pytest.raises(
        RuntimeError,
        match=(
            "reconfiguration transaction rollback: request 'rq_0005' mutation 1 failed: "
            + f"controller '{controller_id}' cannot bind actuator '{actuator_tag}': "
            + f"actuator '{actuator_tag}' is not controller-bindable"
        ),
    ):
        _ = network.step(macro_step_time_s=0.25)

    assert network.save_runtime_snapshot() == before_failure
    assert system.control_elements[0].controller is None


@pytest.mark.parametrize(
    (
        "controller_id",
        "process_model",
        "sensor_tag",
        "signal_key",
        "sensor_unit",
        "actuator_tag",
        "mv_range",
        "error_fragment",
        "control_element_tag",
    ),
    (
        (
            "flash_raw_banned_setpoint_controller",
            FlashDrum(n_species=2),
            "outlet_temperature",
            "temperature",
            "K",
            "(raw, CONTROLLED)_flash_temperature_setpoint",
            (250.0, 400.0),
            "is not controller-bindable; expected canonical actuator namespace tag 'actuator/valve/<id>', 'actuator/pump/<id>', or 'actuator/heat/<id>'",
            "inlet_flow",
        ),
        (
            "flash_raw_removed_pressure_controller",
            FlashDrum(n_species=2),
            "outlet_temperature",
            "temperature",
            "K",
            "(raw, ALGEBRAIC)_flash_pressure",
            (50000.0, 200000.0),
            "is not controller-bindable; expected canonical actuator namespace tag 'actuator/valve/<id>', 'actuator/pump/<id>', or 'actuator/heat/<id>'",
            "inlet_flow",
        ),
    ),
)
def test_controller_activation_rejects_raw_pseudo_actuator_tags_with_rollback(
    controller_id: str,
    process_model: ProcessModel,
    sensor_tag: str,
    signal_key: str,
    sensor_unit: str,
    actuator_tag: str,
    mv_range: tuple[float, float],
    error_fragment: str,
    control_element_tag: str,
) -> None:
    sensor = SampledDelayedSensor(
        name=f"{controller_id}_sensor",
        measurement_tag=sensor_tag,
        alias_tag=signal_key,
        unit=sensor_unit,
        sampling_period=0.0,
        deadtime=0.0,
    )
    control_element = ControlElement(
        mv_tag=control_element_tag,
        mv_trajectory=Trajectory(y0=mv_range[0], t0=0.0),
        mv_range=mv_range,
        mode=ControllerMode.MANUAL,
    )
    system = System(
        dt=1.0,
        process_model=process_model,
        sensors=[sensor],
        calculations=[],
        control_elements=[control_element],
        show_progress=False,
    )
    runtime = _runtime_with_dispatchers(system)
    network = _network(runtime)
    api = ControllerRuntimeWiringApi(network=network)

    _queue_pid_activation(
        api,
        controller_id=controller_id,
        signal_key=signal_key,
        actuator_tag=actuator_tag,
    )
    expected_error = (
        f"controller '{controller_id}' cannot bind actuator '{actuator_tag}': "
        + f"actuator '{actuator_tag}' {error_fragment}"
    )

    assert_controller_activation_rolls_back(
        network,
        system,
        controller_id=controller_id,
        absent_reference_tags=(f"{signal_key}.ref",),
        error_match=(
            re.escape(
                "reconfiguration transaction rollback: request 'rq_0005' mutation 1 failed: "
                + expected_error
            )
            + ".*"
        ),
    )


@pytest.mark.parametrize(
    (
        "controller_id",
        "process_model",
        "sensor_tag",
        "signal_key",
        "sensor_unit",
        "actuator_tag",
        "mv_range",
        "control_element_tag",
    ),
    (
        (
            "flash_imposed_pressure_controller",
            FlashDrum(n_species=2),
            "outlet_temperature",
            "temperature",
            "K",
            "imposed_pressure",
            (50000.0, 200000.0),
            "inlet_flow",
        ),
        (
            "flash_imposed_temperature_controller",
            FlashDrum(n_species=2),
            "outlet_temperature",
            "temperature",
            "K",
            "imposed_temperature",
            (250.0, 400.0),
            "inlet_flow",
        ),
        (
            "cstr_jacket_temperature_controller",
            CSTR(n_species=2),
            "outlet_temperature",
            "temperature",
            "K",
            "jacket_temperature",
            (250.0, 450.0),
            "inlet_flow",
        ),
        (
            "heater_pressure_drop_controller",
            HeaterCooler(n_species=2),
            "outlet_temperature",
            "temperature",
            "K",
            "pressure_drop",
            (0.0, 100000.0),
            "inlet_flow",
        ),
        (
            "heater_external_heat_duty_controller",
            HeaterCooler(n_species=2),
            "outlet_temperature",
            "temperature",
            "K",
            "external_heat_duty",
            (-100000.0, 100000.0),
            "inlet_flow",
        ),
        (
            "heater_external_outlet_temperature_controller",
            HeaterCooler(n_species=2),
            "outlet_temperature",
            "temperature",
            "K",
            "external_outlet_temperature",
            (250.0, 450.0),
            "inlet_flow",
        ),
    ),
)
def test_controller_activation_rejects_non_physical_actuator_contract_with_rollback(
    controller_id: str,
    process_model: ProcessModel,
    sensor_tag: str,
    signal_key: str,
    sensor_unit: str,
    actuator_tag: str,
    mv_range: tuple[float, float],
    control_element_tag: str,
) -> None:
    sensor = SampledDelayedSensor(
        name=f"{controller_id}_sensor",
        measurement_tag=sensor_tag,
        alias_tag=signal_key,
        unit=sensor_unit,
        sampling_period=0.0,
        deadtime=0.0,
    )
    control_element = ControlElement(
        mv_tag=control_element_tag,
        mv_trajectory=Trajectory(y0=mv_range[0], t0=0.0),
        mv_range=mv_range,
        mode=ControllerMode.MANUAL,
    )
    system = System(
        dt=1.0,
        process_model=process_model,
        sensors=[sensor],
        calculations=[],
        control_elements=[control_element],
        show_progress=False,
    )
    runtime = _runtime_with_dispatchers(system)
    network = _network(runtime)
    api = ControllerRuntimeWiringApi(network=network)

    _queue_pid_activation(
        api,
        controller_id=controller_id,
        signal_key=signal_key,
        actuator_tag=actuator_tag,
    )
    before_failure = network.save_runtime_snapshot()

    with pytest.raises(
        RuntimeError,
        match=(
            "reconfiguration transaction rollback: request 'rq_0005' mutation 1 failed: "
            + f"controller '{controller_id}' cannot bind actuator '{actuator_tag}': "
            + f"actuator '{actuator_tag}' is not controller-bindable"
        ),
    ):
        _ = network.step(macro_step_time_s=0.25)

    assert network.save_runtime_snapshot() == before_failure
    assert system.control_elements[0].controller is None
