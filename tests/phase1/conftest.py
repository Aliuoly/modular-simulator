from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass

import pytest

from modular_simulation.connection.domain.phase1_failure_semantics import (
    ScenarioManifestRow,
    build_default_phase1_scenario_manifest,
)
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
