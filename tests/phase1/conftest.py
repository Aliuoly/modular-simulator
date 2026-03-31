from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass

import pytest

from modular_simulation.connection.domain.phase1_failure_semantics import (
    ClassifiedRuntimeEvidence,
    ScenarioManifestRow,
    ScenarioClass,
    build_default_phase1_scenario_manifest,
)
from modular_simulation.connection.domain.state import MaterialState, PortCondition
from modular_simulation.connection.hydraulics.hydraulic_compile import (
    HydraulicCompileLifecycle,
)
from modular_simulation.connection.hydraulics.hydraulic_solver import (
    HydraulicSystemDefinition,
    LinearResidualEquation,
)
from modular_simulation.connection.runtime.connection_layer import (
    MACRO_COUPLING_SEQUENCE,
    MacroStepBookkeeping,
)
from modular_simulation.connection.runtime.runtime import ConnectionRuntimeOrchestrator
from modular_simulation.connection.runtime.runtime_persistence import (
    runtime_replay_state_hash,
    save_runtime_snapshot_contract,
)
from modular_simulation.connection.topology.network import ConnectionNetwork


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


@dataclass(frozen=True)
class Phase1RuntimeFixture:
    runtime: ConnectionRuntimeOrchestrator
    network: ConnectionNetwork
    process_runtime_state: dict[str, object]


@dataclass(frozen=True)
class Phase1ScenarioEvidence:
    scenario: ScenarioManifestRow
    evidence: ClassifiedRuntimeEvidence
    bookkeeping_expectation: MacroStepBookkeepingExpectation
    selected_ticks: tuple[int, ...]


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


@dataclass(frozen=True)
class MacroStepBookkeepingExpectation:
    macro_step_time_s: float
    macro_step_index: int | None = None
    executed_sequence: tuple[str, str, str] = MACRO_COUPLING_SEQUENCE
    updated_port_keys: tuple[str, ...] = ()
    transport_fallback_keys: tuple[str, ...] = ()
    junction_fallback_keys: tuple[str, ...] = ()
    used_fallback: bool = False
    picard_gate_enabled: bool = False
    picard_iterations_used: int = 0
    picard_converged: bool = True
    picard_last_residual: float | None = None

    def assert_matches(self, bookkeeping: MacroStepBookkeeping) -> None:
        assert bookkeeping.macro_step_time_s == pytest.approx(self.macro_step_time_s)
        assert bookkeeping.macro_step_index == self.macro_step_index
        assert bookkeeping.executed_sequence == self.executed_sequence
        assert bookkeeping.updated_port_keys == self.updated_port_keys
        assert bookkeeping.transport_fallback_keys == self.transport_fallback_keys
        assert bookkeeping.junction_fallback_keys == self.junction_fallback_keys
        assert bookkeeping.used_fallback is self.used_fallback
        assert bookkeeping.picard_gate_enabled is self.picard_gate_enabled
        assert bookkeeping.picard_iterations_used == self.picard_iterations_used
        assert bookkeeping.picard_converged is self.picard_converged
        assert bookkeeping.picard_last_residual == self.picard_last_residual


def build_phase1_runtime_fixture() -> Phase1RuntimeFixture:
    """Create a minimal checkpoint-first runtime fixture for uv pytest usage."""

    runtime = ConnectionRuntimeOrchestrator()
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
    process_runtime_state: dict[str, object] = {
        "reactor": {"conversion": 0.34, "temperature": 345.0}
    }
    return Phase1RuntimeFixture(
        runtime=runtime,
        network=network,
        process_runtime_state=process_runtime_state,
    )


def save_phase1_runtime_snapshot(
    fixture: Phase1RuntimeFixture,
) -> dict[str, object]:
    return save_runtime_snapshot_contract(
        runtime=fixture.runtime,
        network=fixture.network,
        process_runtime_state=fixture.process_runtime_state,
    )


def capture_phase1_replay_hashes(
    fixture: Phase1RuntimeFixture,
    *,
    ticks: tuple[int, ...],
) -> dict[int, str]:
    return {
        tick: runtime_replay_state_hash(
            tick=tick,
            runtime=fixture.runtime,
            network=fixture.network,
            process_runtime_state=fixture.process_runtime_state,
        )
        for tick in ticks
    }


def mutate_phase1_runtime_fixture_for_scenario(
    fixture: Phase1RuntimeFixture,
    scenario: ScenarioManifestRow,
) -> None:
    runtime = fixture.runtime
    process_state = fixture.process_runtime_state.setdefault("reactor", {})
    if not isinstance(process_state, dict):
        raise AssertionError("phase1 runtime fixture reactor state must remain a mapping")

    runtime.set_runtime_state(
        simulation_time_s=float(len(scenario.replay_ticks)),
        macro_step_index=max(scenario.replay_ticks, default=0),
        macro_step_active=False,
        committed_idempotency_keys=(f"{scenario.scenario_id}-commit",),
    )
    runtime.clear_latest_port_conditions()
    runtime.restore_transport_runtime_state({})
    fixture.network.replace_queued_reconfigurations(())

    if scenario.scenario_class is ScenarioClass.INVENTORY_SENSITIVE:
        process_state.update(
            {
                "temperature": 301.5,
                "conversion": 0.11,
                "holdup_total_mol": -0.05,
                "scenario_class": scenario.scenario_class.value,
            }
        )
        runtime.record_latest_inlet_condition(
            node_id="reactor",
            port_name="feed",
            condition=_port_condition(pressure=120500.0, temperature=301.5, flow_rate=0.2),
        )
    elif scenario.scenario_class is ScenarioClass.DELAY_HEAVY:
        process_state.update(
            {
                "temperature": 333.0,
                "conversion": 0.34,
                "delay_profile": "transport_fallback",
                "scenario_class": scenario.scenario_class.value,
            }
        )
        runtime.record_latest_outlet_condition(
            node_id="reactor",
            port_name="product",
            condition=_port_condition(pressure=119800.0, temperature=333.0, flow_rate=0.0),
        )
        runtime.restore_transport_runtime_state(
            {
                "edge_states": [
                    {
                        "edge_id": "edge_0001",
                        "composition": [0.6, 0.4],
                        "temperature": 333.0,
                    }
                ],
                "previous_edge_flow_rates": [{"edge_id": "edge_0001", "flow_rate": 0.0}],
                "junction_states": [
                    {
                        "junction_id": "delay_mix",
                        "state": {
                            "pressure": 119800.0,
                            "temperature": 333.0,
                            "mole_fractions": [0.6, 0.4],
                            "species_ids": ["A", "B"],
                        },
                    }
                ],
            }
        )
    elif scenario.scenario_class is ScenarioClass.STRONGLY_COUPLED:
        process_state.update(
            {
                "temperature": 352.0,
                "conversion": 0.61,
                "recycle_ratio": 0.88,
                "scenario_class": scenario.scenario_class.value,
            }
        )
        runtime.record_latest_inlet_condition(
            node_id="reactor",
            port_name="feed",
            condition=_port_condition(pressure=121500.0, temperature=352.0, flow_rate=1.4),
        )
        runtime.record_latest_outlet_condition(
            node_id="reactor",
            port_name="product",
            condition=_port_condition(pressure=120900.0, temperature=349.0, flow_rate=1.35),
        )
        runtime.restore_transport_runtime_state(
            {
                "edge_states": [
                    {
                        "edge_id": "edge_0001",
                        "composition": [0.45, 0.55],
                        "temperature": 349.0,
                    }
                ],
                "previous_edge_flow_rates": [{"edge_id": "edge_0001", "flow_rate": 1.35}],
            }
        )
    else:
        process_state.update(
            {
                "temperature": 317.0,
                "conversion": 0.20,
                "restart_mode": "queued_reconfigure",
                "scenario_class": scenario.scenario_class.value,
            }
        )
        fixture.network.queue_reconfiguration(
            {
                "operation": "add_boundary_sink",
                "boundary_id": f"{scenario.scenario_id}_sink",
            }
        )


def build_phase1_scenario_evidence(
    scenario: ScenarioManifestRow,
    fixture: Phase1RuntimeFixture,
) -> Phase1ScenarioEvidence:
    mutate_phase1_runtime_fixture_for_scenario(fixture, scenario)
    replay_hashes = capture_phase1_replay_hashes(fixture, ticks=scenario.replay_ticks)

    bookkeeping_kwargs: dict[str, object] = {
        "macro_step_time_s": 1.0 + 0.1 * len(scenario.replay_ticks),
        "macro_step_index": max(scenario.replay_ticks, default=0),
        "updated_port_keys": tuple(),
        "transport_fallback_keys": tuple(),
        "junction_fallback_keys": tuple(),
        "used_fallback": False,
        "picard_gate_enabled": False,
        "picard_iterations_used": 0,
        "picard_converged": True,
        "picard_last_residual": None,
    }

    if scenario.scenario_class is ScenarioClass.INVENTORY_SENSITIVE:
        bookkeeping_kwargs["updated_port_keys"] = ("reactor.feed",)
    elif scenario.scenario_class is ScenarioClass.DELAY_HEAVY:
        bookkeeping_kwargs["updated_port_keys"] = ("reactor.product",)
        bookkeeping_kwargs["transport_fallback_keys"] = ("edge_0001",)
        bookkeeping_kwargs["used_fallback"] = True
    elif scenario.scenario_class is ScenarioClass.STRONGLY_COUPLED:
        bookkeeping_kwargs["updated_port_keys"] = ("recycle.inlet",)
        bookkeeping_kwargs["transport_fallback_keys"] = ("edge_0001",)
        bookkeeping_kwargs["junction_fallback_keys"] = ("junction_recycle",)
        bookkeeping_kwargs["used_fallback"] = True
        bookkeeping_kwargs["picard_gate_enabled"] = True
        bookkeeping_kwargs["picard_iterations_used"] = 2
        bookkeeping_kwargs["picard_converged"] = False
        bookkeeping_kwargs["picard_last_residual"] = 0.11
    else:
        bookkeeping_kwargs["updated_port_keys"] = ("reactor.feed",)

    bookkeeping = MacroStepBookkeeping(
        macro_step_time_s=float(bookkeeping_kwargs["macro_step_time_s"]),
        macro_step_index=bookkeeping_kwargs["macro_step_index"],
        executed_sequence=MACRO_COUPLING_SEQUENCE,
        updated_port_keys=bookkeeping_kwargs["updated_port_keys"],
        transport_fallback_keys=bookkeeping_kwargs["transport_fallback_keys"],
        junction_fallback_keys=bookkeeping_kwargs["junction_fallback_keys"],
        used_fallback=bool(bookkeeping_kwargs["used_fallback"]),
        picard_gate_enabled=bool(bookkeeping_kwargs["picard_gate_enabled"]),
        picard_iterations_used=int(bookkeeping_kwargs["picard_iterations_used"]),
        picard_converged=bool(bookkeeping_kwargs["picard_converged"]),
        picard_last_residual=bookkeeping_kwargs["picard_last_residual"],
    )
    bookkeeping_expectation = build_macro_step_bookkeeping_expectation(
        macro_step_time_s=bookkeeping.macro_step_time_s,
        macro_step_index=bookkeeping.macro_step_index,
        updated_port_keys=bookkeeping.updated_port_keys,
        transport_fallback_keys=bookkeeping.transport_fallback_keys,
        junction_fallback_keys=bookkeeping.junction_fallback_keys,
        used_fallback=bookkeeping.used_fallback,
        picard_gate_enabled=bookkeeping.picard_gate_enabled,
        picard_iterations_used=bookkeeping.picard_iterations_used,
        picard_converged=bookkeeping.picard_converged,
        picard_last_residual=bookkeeping.picard_last_residual,
    )

    evidence = ClassifiedRuntimeEvidence(
        scenario=scenario,
        failure_family=scenario.primary_failure_family,
        replay_hashes=replay_hashes,
        bookkeeping=bookkeeping,
        checkpoint_schema_marker="connection.runtime.snapshot",
        diagnostic_payload={
            "scenario_class": scenario.scenario_class.value,
            "failure_family": scenario.primary_failure_family.value,
        },
        notes=("replay-backed", "phase1"),
    )
    return Phase1ScenarioEvidence(
        scenario=scenario,
        evidence=evidence,
        bookkeeping_expectation=bookkeeping_expectation,
        selected_ticks=scenario.replay_ticks,
    )


def build_macro_step_bookkeeping_expectation(
    *,
    macro_step_time_s: float,
    macro_step_index: int | None = None,
    updated_port_keys: tuple[str, ...] = (),
    transport_fallback_keys: tuple[str, ...] = (),
    junction_fallback_keys: tuple[str, ...] = (),
    used_fallback: bool = False,
    picard_gate_enabled: bool = False,
    picard_iterations_used: int = 0,
    picard_converged: bool = True,
    picard_last_residual: float | None = None,
) -> MacroStepBookkeepingExpectation:
    return MacroStepBookkeepingExpectation(
        macro_step_time_s=macro_step_time_s,
        macro_step_index=macro_step_index,
        updated_port_keys=updated_port_keys,
        transport_fallback_keys=transport_fallback_keys,
        junction_fallback_keys=junction_fallback_keys,
        used_fallback=used_fallback,
        picard_gate_enabled=picard_gate_enabled,
        picard_iterations_used=picard_iterations_used,
        picard_converged=picard_converged,
        picard_last_residual=picard_last_residual,
    )


@pytest.fixture(name="phase1_scenario_manifest")
def fixture_phase1_scenario_manifest() -> tuple[ScenarioManifestRow, ...]:
    return build_default_phase1_scenario_manifest()


@pytest.fixture(name="phase1_runtime_fixture")
def fixture_phase1_runtime_fixture() -> Phase1RuntimeFixture:
    return build_phase1_runtime_fixture()


@pytest.fixture(name="phase1_snapshot_export")
def fixture_phase1_snapshot_export(
    phase1_runtime_fixture: Phase1RuntimeFixture,
) -> Callable[[], dict[str, object]]:
    return lambda: save_phase1_runtime_snapshot(phase1_runtime_fixture)


@pytest.fixture(name="phase1_replay_hash_capture")
def fixture_phase1_replay_hash_capture(
    phase1_runtime_fixture: Phase1RuntimeFixture,
) -> Callable[[tuple[int, ...]], Mapping[int, str]]:
    return lambda ticks: capture_phase1_replay_hashes(
        phase1_runtime_fixture,
        ticks=ticks,
    )


@pytest.fixture(name="phase1_bookkeeping_expectation_builder")
def fixture_phase1_bookkeeping_expectation_builder() -> Callable[
    ..., MacroStepBookkeepingExpectation
]:
    return build_macro_step_bookkeeping_expectation


@pytest.fixture(name="phase1_scenario_evidence_rows")
def fixture_phase1_scenario_evidence_rows(
    phase1_scenario_manifest: tuple[ScenarioManifestRow, ...],
) -> tuple[Phase1ScenarioEvidence, ...]:
    rows: list[Phase1ScenarioEvidence] = []
    for scenario in phase1_scenario_manifest:
        rows.append(build_phase1_scenario_evidence(scenario, build_phase1_runtime_fixture()))
    return tuple(rows)
