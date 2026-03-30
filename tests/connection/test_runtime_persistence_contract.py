from __future__ import annotations

# pyright: reportMissingImports=false, reportUnknownVariableType=false, reportUnknownMemberType=false, reportUnknownParameterType=false, reportUnknownArgumentType=false, reportUnknownLambdaType=false, reportPrivateUsage=false, reportUnusedCallResult=false

from collections.abc import Mapping
import pytest
from typing import cast

from modular_simulation.connection.hydraulics.hydraulic_compile import HydraulicCompileLifecycle
from modular_simulation.connection.hydraulics.hydraulic_solver import (
    HydraulicSystemDefinition,
    LinearResidualEquation,
)
from modular_simulation.connection.runtime.split_kernel_adapter import SplitKernelAdapter
from modular_simulation.connection.topology.network import ConnectionNetwork
from modular_simulation.connection.runtime.runtime import (
    ConnectionRuntimeOrchestrator,
    ConnectionRuntimeStepResult,
)
from modular_simulation.connection.runtime.runtime_persistence import (
    RUNTIME_SNAPSHOT_SCHEMA_MARKER,
    RUNTIME_SNAPSHOT_SCHEMA_VERSION,
    restore_runtime_snapshot_contract,
    runtime_replay_state_hash,
    save_runtime_snapshot_contract,
    validate_runtime_snapshot_contract,
)
from modular_simulation.connection.domain.state import MaterialState, PortCondition
from modular_simulation.framework.system import checkpoint_payload_checksum


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
    network.connect("feed_boundary", "reactor.feed")
    network.connect("reactor.product", "product_boundary")
    _ = network.compile()
    return network


def _port_condition(*, pressure: float, temperature: float, flow_rate: float) -> PortCondition:
    return PortCondition(
        state=MaterialState(
            pressure=pressure,
            temperature=temperature,
            mole_fractions=(0.7, 0.3),
            species_ids=("A", "B"),
        ),
        species_ids=("A", "B"),
        through_molar_flow_rate=flow_rate,
        macro_step_time_s=0.0,
    )


def _seed_port_condition_store(runtime: ConnectionRuntimeOrchestrator) -> None:
    runtime.record_latest_inlet_condition(
        node_id="reactor",
        port_name="feed",
        condition=_port_condition(pressure=120000.0, temperature=315.0, flow_rate=1.5),
    )
    runtime.record_latest_outlet_condition(
        node_id="reactor",
        port_name="product",
        condition=_port_condition(pressure=119500.0, temperature=325.0, flow_rate=1.4),
    )


def test_runtime_snapshot_round_trip_restores_queue_order_and_indexes() -> None:
    runtime = ConnectionRuntimeOrchestrator()
    network = _network(runtime)
    process_runtime_state: dict[str, object] = {
        "reactor": {"temperature": 345.0, "conversion": 0.34}
    }

    first_request = network.queue_reconfiguration(
        {
            "operation": "add_boundary_sink",
            "boundary_id": "purge_sink",
            "idempotency_key": "sink-key",
        }
    )
    second_request = network.queue_reconfiguration(
        {
            "operation": "batch_update",
            "mutations": [
                {
                    "operation": "add_process_port",
                    "process_id": "reactor",
                    "direction": "outlet",
                    "port_name": "purge",
                },
                {
                    "operation": "add_connection",
                    "source": "reactor.purge",
                    "target": "purge_sink",
                },
            ],
        }
    )
    assert (first_request, second_request) == ("rq_0001", "rq_0002")

    snapshot = save_runtime_snapshot_contract(
        runtime=runtime,
        network=network,
        process_runtime_state=process_runtime_state,
    )
    validated = validate_runtime_snapshot_contract(snapshot)
    assert validated.macro_step_index == 0
    assert validated.simulation_time_s == pytest.approx(0.0)

    runtime._simulation_time_s = 9.5
    runtime._macro_step_index = 19
    process_runtime_state["reactor"] = {"temperature": 300.0, "conversion": 0.10}
    _ = network.queue_reconfiguration(
        {
            "operation": "add_boundary_sink",
            "boundary_id": "waste_sink",
        }
    )

    restore_runtime_snapshot_contract(
        runtime=runtime,
        network=network,
        process_runtime_state_sink=process_runtime_state,
        snapshot=snapshot,
    )

    assert runtime._simulation_time_s == pytest.approx(0.0)
    assert runtime._macro_step_index == 0
    assert runtime._macro_step_active is False
    assert network._next_reconfiguration_index == 3
    assert network._next_revision_index == 2
    assert tuple(item.request_id for item in network._queued_reconfigurations) == (
        "rq_0001",
        "rq_0002",
    )
    assert process_runtime_state == {"reactor": {"conversion": 0.34, "temperature": 345.0}}


def test_runtime_snapshot_round_trip_preserves_port_condition_store() -> None:
    runtime = ConnectionRuntimeOrchestrator()
    network = _network(runtime)
    process_runtime_state: dict[str, object] = {
        "reactor": {"temperature": 345.0, "conversion": 0.34}
    }
    _seed_port_condition_store(runtime)

    snapshot = save_runtime_snapshot_contract(
        runtime=runtime,
        network=network,
        process_runtime_state=process_runtime_state,
    )
    validated = validate_runtime_snapshot_contract(snapshot)
    # snapshot["snapshot"] is typed as object in some contexts; narrow it to a mapping before indexing
    snapshot_section = cast(dict[str, object], snapshot["snapshot"])
    from modular_simulation.connection.runtime.runtime_port_snapshot_store import (
        RuntimePortSnapshotPayload,
    )

    assert validated.port_condition_store == cast(
        RuntimePortSnapshotPayload, snapshot_section["port_condition_store"]
    )

    runtime.clear_latest_port_conditions()
    process_runtime_state["reactor"] = {"temperature": 300.0, "conversion": 0.10}

    restore_runtime_snapshot_contract(
        runtime=runtime,
        network=network,
        process_runtime_state_sink=process_runtime_state,
        snapshot=snapshot,
    )

    restored_inlet = runtime.get_latest_inlet_condition(node_id="reactor", port_name="feed")
    assert restored_inlet is not None
    assert restored_inlet.state.pressure == pytest.approx(120000.0)
    assert restored_inlet.through_molar_flow_rate == pytest.approx(1.5)

    restored_outlet = runtime.get_latest_outlet_condition(node_id="reactor", port_name="product")
    assert restored_outlet is not None
    assert restored_outlet.state.temperature == pytest.approx(325.0)
    assert restored_outlet.through_molar_flow_rate == pytest.approx(1.4)

    assert process_runtime_state == {"reactor": {"conversion": 0.34, "temperature": 345.0}}


def test_runtime_resume_preserves_monotonic_time_and_step_index_continuity() -> None:
    runtime = ConnectionRuntimeOrchestrator()
    network = _network(runtime)
    process_runtime_state: dict[str, object] = {}

    _ = network.step(macro_step_time_s=1.5)
    _ = network.step(macro_step_time_s=0.5)
    snapshot = save_runtime_snapshot_contract(
        runtime=runtime,
        network=network,
        process_runtime_state=process_runtime_state,
    )

    _ = network.step(macro_step_time_s=0.25)

    restore_runtime_snapshot_contract(
        runtime=runtime,
        network=network,
        process_runtime_state_sink=process_runtime_state,
        snapshot=snapshot,
    )
    resumed = cast(ConnectionRuntimeStepResult, network.step(macro_step_time_s=0.25))

    assert resumed.simulation_time_s == pytest.approx(2.25)
    assert resumed.macro_step_index == 3


def test_save_runtime_snapshot_rejects_active_macro_step_and_allows_barrier_capture() -> None:
    runtime = ConnectionRuntimeOrchestrator()
    network = _network(runtime)

    runtime._macro_step_active = True
    with pytest.raises(
        RuntimeError,
        match="runtime snapshot capture is unavailable during active macro-step execution",
    ):
        _ = network.save_runtime_snapshot()

    runtime._macro_step_active = False
    snapshot = network.save_runtime_snapshot()
    assert snapshot["schema"] == "connection_runtime_v1"


def test_restore_rejects_invalid_schema_without_mutating_active_state() -> None:
    runtime = ConnectionRuntimeOrchestrator()
    network = _network(runtime)
    process_runtime_state: dict[str, object] = {"reactor": {"temperature": 320.0}}
    _ = network.queue_reconfiguration(
        {
            "operation": "add_boundary_sink",
            "boundary_id": "purge_sink",
        }
    )
    before_restore = save_runtime_snapshot_contract(
        runtime=runtime,
        network=network,
        process_runtime_state=process_runtime_state,
    )
    invalid_snapshot = dict(before_restore)
    invalid_snapshot["schema_version"] = 999

    with pytest.raises(
        ValueError,
        match="invalid runtime snapshot payload: field 'schema_version' does not match expected version",
    ):
        restore_runtime_snapshot_contract(
            runtime=runtime,
            network=network,
            process_runtime_state_sink=process_runtime_state,
            snapshot=invalid_snapshot,
        )

    after_restore = save_runtime_snapshot_contract(
        runtime=runtime,
        network=network,
        process_runtime_state=process_runtime_state,
    )
    assert after_restore == before_restore


def test_restore_requires_barrier_inactive_and_is_atomic_when_process_validation_fails() -> None:
    runtime = ConnectionRuntimeOrchestrator()
    network = _network(runtime)
    process_runtime_state: dict[str, object] = {"reactor": {"temperature": 350.0}}
    snapshot = save_runtime_snapshot_contract(
        runtime=runtime,
        network=network,
        process_runtime_state=process_runtime_state,
    )

    runtime._macro_step_active = True
    with pytest.raises(
        RuntimeError,
        match="runtime snapshot restore is unavailable during active macro-step execution",
    ):
        restore_runtime_snapshot_contract(
            runtime=runtime,
            network=network,
            process_runtime_state_sink=process_runtime_state,
            snapshot=snapshot,
        )
    runtime._macro_step_active = False

    before_restore = save_runtime_snapshot_contract(
        runtime=runtime,
        network=network,
        process_runtime_state=process_runtime_state,
    )

    def _raise_on_process_state(payload: Mapping[str, object]) -> Mapping[str, object]:
        del payload
        raise ValueError("process state is invalid")

    with pytest.raises(ValueError, match="process state is invalid"):
        restore_runtime_snapshot_contract(
            runtime=runtime,
            network=network,
            process_runtime_state_sink=process_runtime_state,
            snapshot=snapshot,
            process_runtime_validator=_raise_on_process_state,
        )

    after_restore = save_runtime_snapshot_contract(
        runtime=runtime,
        network=network,
        process_runtime_state=process_runtime_state,
    )
    assert after_restore == before_restore


def test_restore_rejects_invalid_port_condition_payload_shape() -> None:
    runtime = ConnectionRuntimeOrchestrator()
    network = _network(runtime)
    process_runtime_state: dict[str, object] = {"reactor": {"temperature": 350.0}}
    _seed_port_condition_store(runtime)

    baseline_snapshot = save_runtime_snapshot_contract(
        runtime=runtime,
        network=network,
        process_runtime_state=process_runtime_state,
    )
    invalid_snapshot = dict(baseline_snapshot)
    invalid_snapshot_payload = dict(cast(dict[str, object], baseline_snapshot["snapshot"]))
    invalid_snapshot_payload["port_condition_store"] = {
        "inlets": {
            "reactor": {
                "feed": {
                    "state": {
                        "pressure": 120000.0,
                        "temperature": 315.0,
                        "mole_fractions": (0.7, 0.3),
                        "species_ids": ("A", "B"),
                    },
                    "species_ids": ("A", "B"),
                    "through_molar_flow_rate": "not-a-number",
                    "macro_step_time_s": 0.0,
                }
            }
        },
        "outlets": {},
    }
    invalid_snapshot["snapshot"] = invalid_snapshot_payload
    payload_without_checksum = dict(invalid_snapshot)
    payload_without_checksum.pop("integrity_checksum", None)
    invalid_snapshot["integrity_checksum"] = checkpoint_payload_checksum(payload_without_checksum)

    with pytest.raises(
        ValueError,
        match=(
            "invalid runtime snapshot payload: field "
            "'port_condition_store.inlets.reactor.feed.through_molar_flow_rate' is invalid"
        ),
    ):
        restore_runtime_snapshot_contract(
            runtime=runtime,
            network=network,
            process_runtime_state_sink=process_runtime_state,
            snapshot=invalid_snapshot,
        )

    assert (
        save_runtime_snapshot_contract(
            runtime=runtime,
            network=network,
            process_runtime_state=process_runtime_state,
        )
        == baseline_snapshot
    )


def test_restore_preserves_idempotency_conflict_rejection_when_payload_is_unavailable() -> None:
    runtime = ConnectionRuntimeOrchestrator()
    network = _network(runtime)
    process_runtime_state: dict[str, object] = {}

    _ = network.queue_reconfiguration(
        {
            "operation": "add_boundary_sink",
            "boundary_id": "sink_a",
            "idempotency_key": "sink-key",
        }
    )
    _ = network.step(macro_step_time_s=0.5)
    snapshot = save_runtime_snapshot_contract(
        runtime=runtime,
        network=network,
        process_runtime_state=process_runtime_state,
    )

    _ = network.queue_reconfiguration(
        {
            "operation": "add_boundary_sink",
            "boundary_id": "sink_temp",
        }
    )

    restore_runtime_snapshot_contract(
        runtime=runtime,
        network=network,
        process_runtime_state_sink=process_runtime_state,
        snapshot=snapshot,
    )

    replay = network.queue_reconfiguration(
        {
            "operation": "add_boundary_sink",
            "boundary_id": "sink_b",
            "idempotency_key": "sink-key",
        }
    )
    assert replay == "rq_0002"

    with pytest.raises(
        RuntimeError,
        match=(
            "reconfiguration transaction rollback: request 'rq_0002' reuses "
            "idempotency_key 'sink-key' but committed payload is unavailable"
        ),
    ):
        _ = network.step(macro_step_time_s=0.5)

    assert "sink_b" not in network._boundary_specs
    assert tuple(item.request_id for item in network.queued_reconfigurations) == ("rq_0002",)


def test_schema_marker_and_version_are_explicit_and_stable() -> None:
    runtime = ConnectionRuntimeOrchestrator()
    network = _network(runtime)
    snapshot = save_runtime_snapshot_contract(
        runtime=runtime,
        network=network,
        process_runtime_state={},
    )

    assert snapshot["schema_marker"] == RUNTIME_SNAPSHOT_SCHEMA_MARKER
    assert snapshot["schema_version"] == RUNTIME_SNAPSHOT_SCHEMA_VERSION
    assert RUNTIME_SNAPSHOT_SCHEMA_VERSION == 3
    assert set(cast(dict[str, object], snapshot["snapshot"]).keys()) == {
        "runtime",
        "process_runtime_state",
        "port_condition_store",
        "transport_runtime_state",
        "connection_runtime_state",
    }


def test_runtime_replay_hash_changes_with_port_condition_store_content() -> None:
    runtime = ConnectionRuntimeOrchestrator()
    network = _network(runtime)
    process_runtime_state: dict[str, object] = {}
    _seed_port_condition_store(runtime)

    baseline_hash = runtime_replay_state_hash(
        tick=0,
        runtime=runtime,
        network=network,
        process_runtime_state=process_runtime_state,
    )

    runtime.record_latest_outlet_condition(
        node_id="reactor",
        port_name="product",
        condition=_port_condition(pressure=118000.0, temperature=325.0, flow_rate=1.4),
    )
    changed_hash = runtime_replay_state_hash(
        tick=0,
        runtime=runtime,
        network=network,
        process_runtime_state=process_runtime_state,
    )
    assert changed_hash != baseline_hash


def test_live_runtime_snapshot_schema_and_fields_remain_connection_runtime_v1() -> None:
    runtime = ConnectionRuntimeOrchestrator()
    network = _network(runtime)

    live_snapshot = network.save_runtime_snapshot()
    assert live_snapshot["schema"] == "connection_runtime_v1"
    assert set(live_snapshot.keys()) == {
        "schema",
        "simulation_time_s",
        "macro_step_index",
        "macro_step_active",
        "graph_revision",
        "queued_request_ids",
        "queued_request_count",
        "committed_idempotency_keys",
        "process_runtime_state",
        "transport_runtime_state",
    }
    assert "port_condition_store" not in live_snapshot


def test_restore_process_runtime_state_with_dimension_change_allows_subsequent_step() -> None:
    """Restoring 2-species HoldingTank state into a fresh 1-species tank must
    rebuild cached ProcessModel views so the next step() does not crash with a
    shape mismatch.  Regression test for the missing _rebuild_cached_state_views
    call in ConnectedPlantOrchestrator.restore_process_runtime_state().
    """
    from dataclasses import dataclass

    import numpy as np

    from modular_simulation.connection.runtime.connected_plant_orchestrator import (
        ConnectedPlantOrchestrator,
    )
    from modular_simulation.connection.topology.subsystem_descriptor import (
        SubsystemRuntimeDescriptor,
    )
    from modular_simulation.unit_processes.storage.holding_tank import HoldingTank

    # A minimal subsystem wrapper that exposes .system.process_model to the orchestrator.
    @dataclass
    class _TankSystem:
        process_model: HoldingTank

    @dataclass
    class _TankSubsystem:
        descriptor: SubsystemRuntimeDescriptor
        system: _TankSystem

        def run_sensor_phase(self) -> None:
            pass

        def run_calculation_phase(self) -> None:
            pass

        def run_controller_phase(self) -> None:
            pass

        def run_process_phase(self, duration: float) -> None:
            pass

    runtime = ConnectionRuntimeOrchestrator()
    network = _network(runtime)

    # The tank starts with 1 species (default).
    tank = HoldingTank()
    assert tank.holdup_component_moles.size == 1

    subsystem = _TankSubsystem(
        descriptor=SubsystemRuntimeDescriptor(
            descriptor_id="tank_ss",
            process_id="reactor",
            inlet_ports=("feed",),
            outlet_ports=("product",),
            publication_map={},
        ),
        system=_TankSystem(process_model=tank),
    )
    orchestrator = ConnectedPlantOrchestrator(
        subsystems=(subsystem,),
        network=network,
        runtime_orchestrator=runtime,
    )

    # Build a 2-species state payload (as exported by ConnectedPlantOrchestrator).
    two_species_payload = {
        "reactor": {
            "holdup_component_moles": [1.5, 0.5],
            "holdup_temperature": 320.0,
            "holdup_pressure": 115000.0,
            "inlet_flow": 0.0,
            "inlet_temperature": 298.15,
            "inlet_pressure": 101325.0,
            "inlet_composition": [0.75, 0.25],
            "requested_outlet_flow_mol_s": 0.0,
            "imposed_outlet_flow_mol_s": 0.0,
            "resolved_outlet_flow_mol_s": 0.0,
            "outlet_temperature": 320.0,
            "outlet_pressure": 115000.0,
            "outlet_composition": [0.75, 0.25],
            "_holdup_species_ids": ["A", "B"],
            "_inlet_species_ids": ["A", "B"],
            "_outlet_species_ids": ["A", "B"],
        }
    }

    # Restore the 2-species state into the 1-species tank.
    orchestrator.restore_process_runtime_state(two_species_payload)

    # After restore, the array fields should reflect the 2-species payload.
    assert tank.holdup_component_moles.size == 2

    # Calling step() must not raise a shape-mismatch ValueError.
    # Before the fix this raises:
    #   ValueError: could not broadcast input array from shape (2,) into shape (1,)
    tank.step(1.0)

    # Verify the tank state is consistent after the step:
    # holdup_component_moles must still be a 2-element array (species dimension preserved).
    assert tank.holdup_component_moles.size == 2


def test_live_runtime_snapshot_round_trip_preserves_transport_owner_state() -> None:
    runtime = ConnectionRuntimeOrchestrator()
    network = _network(runtime)

    runtime.restore_transport_runtime_state(
        {
            "edge_states": [
                {
                    "edge_id": "edge_0001",
                    "composition": [0.8, 0.2],
                    "temperature": 315.0,
                }
            ],
            "previous_edge_flow_rates": [{"edge_id": "edge_0001", "flow_rate": 1.25}],
            "junction_states": [
                {
                    "junction_id": "mix",
                    "state": {
                        "pressure": 120000.0,
                        "temperature": 310.0,
                        "mole_fractions": [0.6, 0.4],
                    },
                }
            ],
        }
    )

    snapshot = network.save_runtime_snapshot()

    runtime.restore_transport_runtime_state({})
    network.resume_from_snapshot(snapshot=snapshot)

    assert runtime.export_transport_runtime_state() == {
        "edge_states": [
            {
                "edge_id": "edge_0001",
                "composition": [0.8, 0.2],
                "temperature": 315.0,
            }
        ],
        "previous_edge_flow_rates": [{"edge_id": "edge_0001", "flow_rate": 1.25}],
        "junction_states": [
            {
                "junction_id": "mix",
                "state": {
                    "pressure": 120000.0,
                    "temperature": 310.0,
                    "mole_fractions": (0.6, 0.4),
                    "species_ids": None,
                    "phase": None,
                    "enthalpy_molar": None,
                    "entropy_molar": None,
                },
            }
        ],
    }


def test_runtime_snapshot_round_trip_restores_holding_tank_process_runtime_state() -> None:
    runtime = ConnectionRuntimeOrchestrator()
    network = _network(runtime)
    process_runtime_state: dict[str, object] = {
        "tank": {
            "holdup_mol": 2.75,
            "holdup_temperature": 312.0,
            "holdup_pressure": 121000.0,
            "holdup_composition": [0.2, 0.8],
            "holdup_species_ids": ["A", "B"],
            "requested_outlet_flow_mol_s": 1.2,
            "resolved_outlet_flow_mol_s": 1.1,
        }
    }

    snapshot = save_runtime_snapshot_contract(
        runtime=runtime,
        network=network,
        process_runtime_state=process_runtime_state,
    )

    process_runtime_state.clear()
    process_runtime_state["tank"] = {"holdup_mol": -1.0}

    restore_runtime_snapshot_contract(
        runtime=runtime,
        network=network,
        process_runtime_state_sink=process_runtime_state,
        snapshot=snapshot,
    )

    assert process_runtime_state == {
        "tank": {
            "holdup_composition": [0.2, 0.8],
            "holdup_mol": 2.75,
            "holdup_pressure": 121000.0,
            "holdup_species_ids": ["A", "B"],
            "holdup_temperature": 312.0,
            "requested_outlet_flow_mol_s": 1.2,
            "resolved_outlet_flow_mol_s": 1.1,
        }
    }


def test_adapter_delay_restore_survives_checkpoint_reload_and_post_edit_recovery() -> None:
    runtime = ConnectionRuntimeOrchestrator()
    network = _network(runtime)
    adapter = SplitKernelAdapter(network=network, runtime_orchestrator=runtime)
    process_runtime_state: dict[str, object] = {}

    delay_bundle = {
        "transport_runtime_state": {
            "edge_states": [
                {
                    "edge_id": "edge_0001",
                    "composition": [0.8, 0.2],
                    "temperature": 315.0,
                }
            ],
            "previous_edge_flow_rates": [{"edge_id": "edge_0001", "flow_rate": 1.25}],
            "junction_states": [
                {
                    "junction_id": "mix",
                    "state": {
                        "pressure": 120000.0,
                        "temperature": 310.0,
                        "mole_fractions": [0.6, 0.4],
                    },
                }
            ],
        }
    }
    adapter.restore_delay_state(delay_bundle)
    expected_transport_runtime_state = adapter.capture_delay_state()["transport_runtime_state"]

    checkpoint = save_runtime_snapshot_contract(
        runtime=runtime,
        network=network,
        process_runtime_state=process_runtime_state,
    )

    runtime.restore_transport_runtime_state({})
    restore_runtime_snapshot_contract(
        runtime=runtime,
        network=network,
        process_runtime_state_sink=process_runtime_state,
        snapshot=checkpoint,
    )
    assert (
        adapter.capture_delay_state()["transport_runtime_state"] == expected_transport_runtime_state
    )

    runtime.restore_transport_runtime_state({})
    network.recover_from_checkpoint_after_edit(snapshot=checkpoint)
    assert (
        adapter.capture_delay_state()["transport_runtime_state"] == expected_transport_runtime_state
    )
