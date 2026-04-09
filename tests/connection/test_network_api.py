from __future__ import annotations

# pyright: reportMissingImports=false, reportUnknownVariableType=false, reportUnknownMemberType=false, reportUnknownParameterType=false, reportUnknownArgumentType=false, reportUnknownLambdaType=false

from types import MappingProxyType

import numpy as np

import pytest

from modular_simulation.connection.hydraulics.hydraulic_compile import HydraulicCompileLifecycle
from modular_simulation.connection.hydraulics.hydraulic_solver import (
    HydraulicSystemDefinition,
    LinearResidualEquation,
)
from modular_simulation.connection.topology.network import ConnectionNetwork
from modular_simulation.connection.runtime.runtime import ConnectionRuntimeOrchestrator
from modular_simulation.connection.topology.process_binding import ProcessBinding
from modular_simulation.connection.runtime.connected_plant_orchestrator import (
    ConnectedPlantOrchestrator,
)
from modular_simulation.connection.runtime.connection_layer import TransportAndMixingUpdate
from modular_simulation.connection.topology.unit_process_wiring import create_subsystem_for_unit
from modular_simulation.thermodynamics.runtime_context import SimulationRuntimeContext
from modular_simulation.thermodynamics.stream import StreamData
from modular_simulation.unit_processes import (
    StagewiseDistillationColumn,
    ThermoTrayDistillationColumn,
)


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


def _valid_system() -> HydraulicSystemDefinition:
    return HydraulicSystemDefinition(
        equations=(),
        linear_residual_equations=(
            _linear_equation("ref", {"pressure": 1.0}, constant=-5.0),
            _linear_equation("balance", {"pressure": 1.0, "flow": -1.0}),
        ),
    )


def _network() -> ConnectionNetwork:
    network = ConnectionNetwork(
        compile_lifecycle=HydraulicCompileLifecycle(),
        hydraulic_system_builder=lambda topology: _valid_system(),
    )
    network.add_process("reactor", inlet_ports=("feed",), outlet_ports=("product",))
    network.add_boundary_source("feed_boundary")
    network.add_boundary_sink("product_boundary")
    _ = network.connect("feed_boundary", "reactor.feed")
    _ = network.connect("reactor.product", "product_boundary")
    return network


def test_public_api_entry_points_exist() -> None:
    network = ConnectionNetwork()

    assert callable(network.add_process)
    assert callable(network.add_boundary_source)
    assert callable(network.add_boundary_sink)
    assert callable(network.connect)
    assert callable(network.compile)
    assert callable(network.step)
    assert callable(network.queue_reconfiguration)
    assert callable(network.save_runtime_snapshot)
    assert callable(network.resume_from_snapshot)
    assert callable(network.list_process_specs)
    assert callable(network.list_boundary_specs)
    assert callable(network.list_connection_edges)
    assert callable(network.list_line_hydraulic_configs)
    assert callable(network.list_pending_valve_open_fractions)
    assert callable(network.list_pending_pump_speeds)
    assert callable(network.attach_line_valve)
    assert callable(network.attach_line_pump)
    assert callable(network.stage_valve_open_fraction_command)
    assert callable(network.stage_pump_speed_command)
    assert callable(network.from_single_process)
    assert callable(ConnectionRuntimeOrchestrator.for_system)


def test_query_surface_returns_deterministic_connection_views() -> None:
    network = _network()
    _ = network.compile()

    process_specs = network.list_process_specs()
    boundary_specs = network.list_boundary_specs()
    edges = network.list_connection_edges()
    line_configs = network.list_line_hydraulic_configs()

    assert tuple(item.process_id for item in process_specs) == ("reactor",)
    assert process_specs[0].inlet_ports == ("feed",)
    assert process_specs[0].outlet_ports == ("product",)
    assert tuple(item.boundary_id for item in boundary_specs) == (
        "feed_boundary",
        "product_boundary",
    )
    assert tuple(item.edge_id for item in edges) == ("edge_0001", "edge_0002")
    assert line_configs == ()
    assert network.list_pending_valve_open_fractions() == ()
    assert network.list_pending_pump_speeds() == ()


def test_from_single_process_bootstraps_compiled_network() -> None:
    runtime = ConnectionRuntimeOrchestrator()
    network = ConnectionNetwork.from_single_process(
        process_id="reactor",
        inlet_ports=("feed",),
        outlet_ports=("product",),
        compile_lifecycle=HydraulicCompileLifecycle(),
        hydraulic_system_builder=lambda topology: _valid_system(),
        runtime_orchestrator=runtime,
    )

    compiled = network.compiled
    assert compiled is not None
    assert compiled.topology.node_ids == ("feed_boundary", "product_boundary", "reactor")
    assert compiled.topology.edge_ids == ("edge_0001", "edge_0002")


def test_compile_delegates_to_topology_process_bindings_and_compile_artifact() -> None:
    compiled = _network().compile()

    assert compiled.topology.node_ids == ("feed_boundary", "product_boundary", "reactor")
    assert compiled.topology.edge_ids == ("edge_0001", "edge_0002")
    assert isinstance(compiled.process_bindings["reactor"], ProcessBinding)
    assert compiled.hydraulic is not None
    assert compiled.hydraulic.graph_revision == "graph_rev_0001"


def test_connect_rejects_malformed_endpoint_deterministically() -> None:
    network = ConnectionNetwork()
    network.add_process("reactor", inlet_ports=("feed",), outlet_ports=("product",))
    network.add_boundary_sink("sink")

    with pytest.raises(ValueError) as error:
        _ = network.connect("reactor", "sink")

    assert str(error.value) == (
        "invalid endpoint 'reactor': process endpoints must use '<node_id>.<port_name>' format"
    )


def test_connect_duplicate_edge_has_actionable_error() -> None:
    network = ConnectionNetwork()
    network.add_process("reactor", inlet_ports=("feed",), outlet_ports=("product",))
    network.add_boundary_source("feed")

    _ = network.connect("feed", "reactor.feed")

    with pytest.raises(ValueError) as error:
        _ = network.connect("feed", "reactor.feed")

    assert str(error.value) == (
        "duplicate connection 'feed.outlet->reactor.feed' already exists as edge_id 'edge_0001'"
    )


# ---------------------------------------------------------------------------
# Observability snapshot contract tests (task 1.1 — red boundary)
# ---------------------------------------------------------------------------


def test_observability_snapshot_method_exists_on_connection_network() -> None:
    """ConnectionNetwork must expose get_observability_snapshot as a callable."""
    network = ConnectionNetwork()
    assert callable(network.get_observability_snapshot)


def test_observability_snapshot_returns_mapping_without_runtime() -> None:
    """get_observability_snapshot returns a Mapping even without a runtime orchestrator."""
    network = ConnectionNetwork()

    snapshot = network.get_observability_snapshot()

    from collections.abc import Mapping as MappingABC

    assert isinstance(snapshot, MappingABC)


def test_observability_snapshot_top_level_keys_are_frozen() -> None:
    """Snapshot contains exactly the first-slice top-level keys: schema, graph_revision,
    runtime, queue, observables."""
    network = ConnectionNetwork()

    snapshot = network.get_observability_snapshot()

    assert set(snapshot.keys()) == {
        "schema",
        "graph_revision",
        "runtime",
        "queue",
        "observables",
    }


def test_observability_snapshot_schema_is_non_empty_string() -> None:
    """snapshot['schema'] is a non-empty string contract marker."""
    network = ConnectionNetwork()

    snapshot = network.get_observability_snapshot()

    assert isinstance(snapshot["schema"], str)
    assert snapshot["schema"]


def test_observability_snapshot_graph_revision_is_none_before_compile() -> None:
    """graph_revision is None when the network has not been compiled."""
    network = ConnectionNetwork()

    snapshot = network.get_observability_snapshot()

    assert snapshot["graph_revision"] is None


def test_observability_snapshot_graph_revision_reflects_compiled_state() -> None:
    """graph_revision matches the compiled network's graph_revision after compile."""
    network = _network()
    network.compile()

    snapshot = network.get_observability_snapshot()

    assert snapshot["graph_revision"] == "graph_rev_0001"


def test_observability_snapshot_runtime_section_shape() -> None:
    """runtime section contains simulation_time_s (float), macro_step_index (int),
    macro_step_active (bool)."""
    network = ConnectionNetwork()

    snapshot = network.get_observability_snapshot()
    runtime = snapshot["runtime"]

    from collections.abc import Mapping as MappingABC

    assert isinstance(runtime, MappingABC)
    assert "simulation_time_s" in runtime
    assert "macro_step_index" in runtime
    assert "macro_step_active" in runtime
    assert isinstance(runtime["simulation_time_s"], float)
    assert isinstance(runtime["macro_step_index"], int)
    assert isinstance(runtime["macro_step_active"], bool)


def test_observability_snapshot_queue_section_shape() -> None:
    """queue section contains queued_request_ids, queued_request_count (int),
    and committed_idempotency_keys."""
    network = ConnectionNetwork()

    snapshot = network.get_observability_snapshot()
    queue = snapshot["queue"]

    from collections.abc import Mapping as MappingABC

    assert isinstance(queue, MappingABC)
    assert "queued_request_ids" in queue
    assert "queued_request_count" in queue
    assert "committed_idempotency_keys" in queue
    assert isinstance(queue["queued_request_count"], int)


def test_observability_snapshot_queue_count_matches_queued_ids_length() -> None:
    """queued_request_count equals len(queued_request_ids) at all times."""
    network = ConnectionNetwork()
    _ = network.queue_reconfiguration({"operation": "add_boundary_source"})
    _ = network.queue_reconfiguration({"operation": "add_boundary_sink"})

    snapshot = network.get_observability_snapshot()
    queue = snapshot["queue"]

    assert queue["queued_request_count"] == len(queue["queued_request_ids"])
    assert queue["queued_request_count"] == 2


def test_observability_snapshot_observables_section_shape() -> None:
    """observables section contains published_measurements and plant_calculation_outputs
    as numeric mappings."""
    network = ConnectionNetwork()

    snapshot = network.get_observability_snapshot()
    observables = snapshot["observables"]

    from collections.abc import Mapping as MappingABC

    assert isinstance(observables, MappingABC)
    assert "published_measurements" in observables
    assert "plant_calculation_outputs" in observables
    assert "process_state_values" in observables
    assert isinstance(observables["published_measurements"], MappingABC)
    assert isinstance(observables["plant_calculation_outputs"], MappingABC)
    assert isinstance(observables["process_state_values"], MappingABC)


def test_observability_snapshot_process_state_values_numerically_match_runtime_shortcut_state() -> (
    None
):
    context = SimulationRuntimeContext.create(species_names=["methanol", "ethanol", "water"])

    column = StagewiseDistillationColumn(
        n_species=3,
        active_contact_height_m=4.0,
        shell_diameter_m=1.0,
        feed_stage_indices=(1, 3),
        column_pressure_pa=150000.0,
    )
    subsystem = create_subsystem_for_unit(
        unit=column,
        unit_id="legacy_shortcut_item",
        dt=0.1,
        runtime_context=context,
    )
    column.attach_system(type("_S", (), {"solver_options": {}})())
    column.apply_inlet(
        "feed_1",
        StreamData(
            temperature=345.0,
            pressure=150000.0,
            mole_fractions=(0.5, 0.3, 0.2),
            molar_flow_rate=8.0,
        ),
    )
    column.apply_inlet(
        "feed_2",
        StreamData(
            temperature=340.0,
            pressure=150000.0,
            mole_fractions=(0.2, 0.5, 0.3),
            molar_flow_rate=4.0,
        ),
    )

    runtime = ConnectionRuntimeOrchestrator(
        hydraulic_solve_step=(
            lambda *, network, macro_step_time_s: network.compiled.hydraulic.solve()  # type: ignore[union-attr]
        ),
        transport_and_mixing_step=(
            lambda *, network, hydraulic_result, macro_step_time_s: TransportAndMixingUpdate(
                transport_results={}
            )
        ),
        boundary_propagation_step=(
            lambda *, network, hydraulic_result, transport_and_mixing_update, macro_step_time_s: {}
        ),
        runtime_context=context,
    )
    network = ConnectionNetwork(
        compile_lifecycle=HydraulicCompileLifecycle(),
        hydraulic_system_builder=lambda topology: _valid_system(),
        runtime_orchestrator=runtime,
    )
    network.add_process(
        "legacy_shortcut_item",
        inlet_ports=subsystem.descriptor.inlet_ports,
        outlet_ports=subsystem.descriptor.outlet_ports,
    )
    network.add_boundary_source("feed")
    network.add_boundary_source("feed_b")
    network.add_boundary_source("reflux")
    network.add_boundary_sink("dist")
    network.add_boundary_sink("bot")
    network.add_boundary_sink("reflux_sink")
    _ = network.connect("feed", "legacy_shortcut_item.feed_1")
    _ = network.connect("feed_b", "legacy_shortcut_item.feed_2")
    _ = network.connect("reflux", "legacy_shortcut_item.reflux_return")
    _ = network.connect("legacy_shortcut_item.distillate", "dist")
    _ = network.connect("legacy_shortcut_item.bottoms", "bot")
    _ = network.connect("legacy_shortcut_item.reflux_outlet", "reflux_sink")
    _ = network.compile()

    orchestrator = ConnectedPlantOrchestrator(
        subsystems=(subsystem,),
        network=network,
        runtime_orchestrator=runtime,
        runtime_context=context,
    )
    _ = orchestrator.step(macro_step_time_s=0.2)

    process_state_values = network.get_observability_snapshot()["observables"][
        "process_state_values"
    ]
    assert process_state_values["legacy_shortcut_item/column_pressure_pa"] == pytest.approx(
        column.column_pressure_pa
    )
    assert process_state_values["legacy_shortcut_item/distillate_flow_mol_s"] == pytest.approx(
        column.distillate_flow
    )
    assert process_state_values["legacy_shortcut_item/bottoms_flow_mol_s"] == pytest.approx(
        column.bottoms_flow
    )


def test_observability_snapshot_process_state_values_numerically_match_runtime_stagewise_state() -> (
    None
):
    context = SimulationRuntimeContext.create(species_names=["methanol", "ethanol", "water"])

    column = StagewiseDistillationColumn(
        n_species=3,
        active_contact_height_m=6.0,
        shell_diameter_m=1.1,
        feed_stage_indices=(1, 4),
        column_pressure_pa=160000.0,
    )
    subsystem = create_subsystem_for_unit(
        unit=column,
        unit_id="stage_col",
        dt=0.1,
        runtime_context=context,
    )
    column.attach_system(type("_S", (), {"solver_options": {}})())
    column.apply_inlet(
        "feed_1",
        StreamData(
            temperature=350.0,
            pressure=160000.0,
            mole_fractions=(0.65, 0.25, 0.10),
            molar_flow_rate=7.0,
        ),
    )
    column.apply_inlet(
        "feed_2",
        StreamData(
            temperature=340.0,
            pressure=160000.0,
            mole_fractions=(0.15, 0.30, 0.55),
            molar_flow_rate=5.0,
        ),
    )

    runtime = ConnectionRuntimeOrchestrator(
        hydraulic_solve_step=(
            lambda *, network, macro_step_time_s: network.compiled.hydraulic.solve()  # type: ignore[union-attr]
        ),
        transport_and_mixing_step=(
            lambda *, network, hydraulic_result, macro_step_time_s: TransportAndMixingUpdate(
                transport_results={}
            )
        ),
        boundary_propagation_step=(
            lambda *, network, hydraulic_result, transport_and_mixing_update, macro_step_time_s: {}
        ),
        runtime_context=context,
    )
    network = ConnectionNetwork(
        compile_lifecycle=HydraulicCompileLifecycle(),
        hydraulic_system_builder=lambda topology: _valid_system(),
        runtime_orchestrator=runtime,
    )
    network.add_process(
        "stage_col",
        inlet_ports=subsystem.descriptor.inlet_ports,
        outlet_ports=subsystem.descriptor.outlet_ports,
    )
    network.add_boundary_source("feed_a")
    network.add_boundary_source("feed_b")
    network.add_boundary_sink("dist")
    network.add_boundary_sink("bot")
    _ = network.connect("feed_a", "stage_col.feed_1")
    _ = network.connect("feed_b", "stage_col.feed_2")
    _ = network.connect("stage_col.distillate", "dist")
    _ = network.connect("stage_col.bottoms", "bot")
    _ = network.compile()

    orchestrator = ConnectedPlantOrchestrator(
        subsystems=(subsystem,),
        network=network,
        runtime_orchestrator=runtime,
        runtime_context=context,
    )
    _ = orchestrator.step(macro_step_time_s=0.2)

    process_state_values = network.get_observability_snapshot()["observables"][
        "process_state_values"
    ]
    assert process_state_values["stage_col/column_pressure_pa"] == pytest.approx(
        column.column_pressure_pa
    )
    assert process_state_values["stage_col/active_contact_height_m"] == pytest.approx(
        column.active_contact_height_m
    )
    assert process_state_values["stage_col/shell_diameter_m"] == pytest.approx(
        column.shell_diameter_m
    )
    assert process_state_values["stage_col/distillate_flow_mol_s"] == pytest.approx(
        column.distillate_flow
    )
    assert process_state_values["stage_col/bottoms_flow_mol_s"] == pytest.approx(
        column.bottoms_flow
    )
    assert process_state_values["stage_col/condenser_duty_W"] == pytest.approx(
        column.condenser_duty_W
    )
    assert process_state_values["stage_col/reboiler_duty_W"] == pytest.approx(
        column.reboiler_duty_W
    )
    assert process_state_values["stage_col/condenser_duty_request_W"] == pytest.approx(
        column.condenser_duty_request_W
    )
    assert process_state_values["stage_col/reboiler_duty_request_W"] == pytest.approx(
        column.reboiler_duty_request_W
    )
    assert process_state_values["stage_col/realized_condensed_flow_mol_s"] == pytest.approx(
        column.realized_condensed_flow_mol_s
    )
    assert process_state_values["stage_col/realized_reboiler_boilup_flow_mol_s"] == pytest.approx(
        column.realized_reboiler_boilup_flow_mol_s
    )
    assert process_state_values["stage_col/reflux_return_flow_mol_s"] == pytest.approx(
        column.reflux_return_flow
    )
    assert process_state_values["stage_col/distillate_withdrawal_flow_mol_s"] == pytest.approx(
        column.distillate_withdrawal_flow
    )
    assert process_state_values["stage_col/bottoms_withdrawal_flow_mol_s"] == pytest.approx(
        column.bottoms_withdrawal_flow
    )
    assert process_state_values["stage_col/reflux_outlet_flow_mol_s"] == pytest.approx(
        column.reflux_outlet_flow
    )
    assert process_state_values["stage_col/feed_1/stage_index"] == pytest.approx(
        float(column.feed_stage_indices[0])
    )
    assert process_state_values["stage_col/feed_2/stage_index"] == pytest.approx(
        float(column.feed_stage_indices[1])
    )

    cas_ids = context.species_registry.cas_list
    feed_matrix = column.feed_compositions.reshape(column.n_feeds, column.n_species)
    for idx, cas_id in enumerate(cas_ids):
        assert process_state_values[
            f"stage_col/distillate_mole_fraction/{cas_id}"
        ] == pytest.approx(float(column.distillate_composition[idx]))
        assert process_state_values[f"stage_col/bottoms_mole_fraction/{cas_id}"] == pytest.approx(
            float(column.bottoms_composition[idx])
        )
        assert process_state_values[f"stage_col/feed_1/mole_fraction/{cas_id}"] == pytest.approx(
            float(feed_matrix[0, idx])
        )
        assert process_state_values[f"stage_col/feed_2/mole_fraction/{cas_id}"] == pytest.approx(
            float(feed_matrix[1, idx])
        )


def test_observability_snapshot_process_state_values_match_runtime_thermo_tray_state() -> None:
    context = SimulationRuntimeContext.create(species_names=["n-hexane", "n-heptane", "n-octane"])

    column = ThermoTrayDistillationColumn(
        n_species=3,
        species_selector=np.asarray((3.0, 4.0, 5.0), dtype=np.float64),
        n_trays=6,
        feed_tray_indices=(3,),
        p_top_pa=150000.0,
        delta_p_tray_pa=500.0,
    )
    subsystem = create_subsystem_for_unit(
        unit=column,
        unit_id="thermo_col",
        dt=0.1,
        runtime_context=context,
    )
    column.attach_system(type("_S", (), {"solver_options": {}})())
    column.apply_inlet(
        "feed_1",
        StreamData(
            temperature=385.0,
            pressure=150000.0,
            mole_fractions=(1.0 / 3.0, 1.0 / 3.0, 1.0 / 3.0),
            molar_flow_rate=2.0,
        ),
    )
    column.condenser_duty_request_W = -100000.0
    column.reboiler_duty_request_W = 100000.0
    column.reflux_withdrawal_flow = 1.5
    column.distillate_withdrawal_flow = 0.8
    column.bottoms_withdrawal_flow = 1.1

    runtime = ConnectionRuntimeOrchestrator(
        hydraulic_solve_step=(
            lambda *, network, macro_step_time_s: network.compiled.hydraulic.solve()  # type: ignore[union-attr]
        ),
        transport_and_mixing_step=(
            lambda *, network, hydraulic_result, macro_step_time_s: TransportAndMixingUpdate(
                transport_results={}
            )
        ),
        boundary_propagation_step=(
            lambda *, network, hydraulic_result, transport_and_mixing_update, macro_step_time_s: {}
        ),
        runtime_context=context,
    )
    network = ConnectionNetwork(
        compile_lifecycle=HydraulicCompileLifecycle(),
        hydraulic_system_builder=lambda topology: _valid_system(),
        runtime_orchestrator=runtime,
    )
    network.add_process(
        "thermo_col",
        inlet_ports=subsystem.descriptor.inlet_ports,
        outlet_ports=subsystem.descriptor.outlet_ports,
    )
    network.add_boundary_source("feed")
    network.add_boundary_sink("dist")
    network.add_boundary_sink("bot")
    _ = network.connect("feed", "thermo_col.feed_1")
    _ = network.connect("thermo_col.distillate", "dist")
    _ = network.connect("thermo_col.bottoms", "bot")
    _ = network.compile()

    orchestrator = ConnectedPlantOrchestrator(
        subsystems=(subsystem,),
        network=network,
        runtime_orchestrator=runtime,
        runtime_context=context,
    )
    _ = orchestrator.step(macro_step_time_s=0.2)

    process_state_values = network.get_observability_snapshot()["observables"][
        "process_state_values"
    ]
    assert process_state_values["thermo_col/top_pressure_pa"] == pytest.approx(
        column.headspace_pressure_pa
    )
    assert process_state_values["thermo_col/headspace_pressure_pa"] == pytest.approx(
        column.headspace_pressure_pa
    )
    assert process_state_values["thermo_col/bottom_pressure_pa"] == pytest.approx(
        column.bottom_pressure_pa
    )
    assert process_state_values["thermo_col/realized_condensed_flow_mol_s"] == pytest.approx(
        column.realized_condensed_flow
    )
    assert process_state_values["thermo_col/non_condensed_flow_mol_s"] == pytest.approx(
        column.non_condensed_flow
    )
    assert process_state_values["thermo_col/distillate_source_pressure_pa"] == pytest.approx(
        column.distillate_source_pressure_pa
    )
    assert process_state_values["thermo_col/reflux_source_pressure_pa"] == pytest.approx(
        column.reflux_source_pressure_pa
    )
    assert process_state_values["thermo_col/condenser_drum_temperature_K"] == pytest.approx(
        column.condenser_drum_temperature
    )
    assert process_state_values["thermo_col/condenser_bubble_temperature_K"] >= 0.0
    assert process_state_values["thermo_col/condenser_subcooling_K"] == pytest.approx(
        process_state_values["thermo_col/condenser_bubble_temperature_K"]
        - process_state_values["thermo_col/condenser_drum_temperature_K"],
        rel=1e-9,
        abs=1e-9,
    )


def test_observability_snapshot_is_distinct_from_save_runtime_snapshot() -> None:
    """get_observability_snapshot() result is a distinct read model from
    save_runtime_snapshot() — does NOT expose persistence/checksum fields."""
    from modular_simulation.connection.runtime.runtime import ConnectionRuntimeOrchestrator

    runtime = ConnectionRuntimeOrchestrator()
    network = _network()
    # Attach runtime so save_runtime_snapshot works
    network2 = ConnectionNetwork(
        compile_lifecycle=HydraulicCompileLifecycle(),
        hydraulic_system_builder=lambda topology: _valid_system(),
        runtime_orchestrator=runtime,
    )
    network2.add_process("reactor", inlet_ports=("feed",), outlet_ports=("product",))
    network2.add_boundary_source("feed_boundary")
    network2.add_boundary_sink("product_boundary")
    _ = network2.connect("feed_boundary", "reactor.feed")
    _ = network2.connect("reactor.product", "product_boundary")
    _ = network2.compile()

    observability_snapshot = network2.get_observability_snapshot()

    # The observability snapshot must expose the first-slice sections
    assert "schema" in observability_snapshot
    assert "runtime" in observability_snapshot
    assert "queue" in observability_snapshot
    assert "observables" in observability_snapshot

    # The observability snapshot is not a persistence payload —
    # it does not expose replay-specific fields like 'pending_command_journal'
    assert "pending_command_journal" not in observability_snapshot
    assert "committed_idempotency_payloads" not in observability_snapshot


def test_observability_snapshot_does_not_leak_mutable_runtime_structures() -> None:
    """Mutating returned sequences/mappings does not affect the network state."""
    network = ConnectionNetwork()
    _ = network.queue_reconfiguration({"operation": "add_boundary_source"})

    snapshot = network.get_observability_snapshot()
    queue = snapshot["queue"]

    # queued_request_ids should be a safe copy (tuple or list), not a direct
    # reference to internal state.  Verify re-reading produces the same data.
    ids_first_read = queue["queued_request_ids"]
    snapshot2 = network.get_observability_snapshot()
    ids_second_read = snapshot2["queue"]["queued_request_ids"]

    assert tuple(ids_first_read) == tuple(ids_second_read)
    # Ensure the ids are actually present
    assert len(ids_first_read) == 1


def test_observability_snapshot_does_not_contain_policy_fields() -> None:
    """First-slice snapshot contains only substrate-owned sections — no pricing,
    scoring, tutorial, or ledger fields."""
    network = ConnectionNetwork()

    snapshot = network.get_observability_snapshot()

    forbidden_keys = {"price", "score", "ledger", "tutorial", "economics", "cash", "inventory"}
    assert not (set(snapshot.keys()) & forbidden_keys), (
        f"Policy fields found in substrate snapshot: {set(snapshot.keys()) & forbidden_keys}"
    )


def test_queue_reconfiguration_and_runtime_placeholders_are_deterministic() -> None:
    network = ConnectionNetwork()

    queued = network.queue_reconfiguration({"operation": "add_connection"})
    assert queued == "rq_0001"

    with pytest.raises(ValueError) as malformed_error:
        _ = network.queue_reconfiguration({})
    assert str(malformed_error.value) == (
        "invalid reconfiguration request: expected mapping with non-empty string field 'operation'"
    )

    with pytest.raises(RuntimeError) as step_error:
        _ = network.step(macro_step_time_s=1.0)
    assert str(step_error.value) == (
        "runtime step is unavailable: runtime orchestrator not configured for ConnectionNetwork"
    )

    with pytest.raises(RuntimeError) as snapshot_error:
        _ = network.save_runtime_snapshot()
    assert str(snapshot_error.value) == (
        "runtime snapshot is unavailable: runtime orchestrator not configured for ConnectionNetwork"
    )

    with pytest.raises(ValueError) as payload_error:
        network.resume_from_snapshot(snapshot=[])
    assert str(payload_error.value) == "invalid snapshot payload: expected mapping"

    with pytest.raises(RuntimeError) as resume_error:
        _ = network.resume_from_snapshot(snapshot={})
    assert str(resume_error.value) == (
        "runtime resume is unavailable: runtime orchestrator not configured for ConnectionNetwork"
    )
