from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from modular_simulation.cli.backend_session import PlantBackendSession
from modular_simulation.connection.benchmarking.contracts import (
    BenchmarkScenarioTag,
    BenchmarkWorkloadDefinition,
)
from modular_simulation.connection.hydraulics.hydraulic_solver import (
    HydraulicSolveResult,
    HydraulicSystemDefinition,
)
from modular_simulation.connection.runtime.runtime import ConnectionRuntimeOrchestrator
from modular_simulation.connection.topology.network import ConnectionNetwork
import numpy as np

PHASE3_TOLERANCE_PROFILE = "phase3-default-tolerances"
PHASE3_PHYSICAL_ACCEPTANCE_PROFILE = "phase3-physical-acceptance-v1"
PHASE3_TELEMETRY_CONTRACT_VERSION = "benchmark_attempt_v1"
PHASE3_DELAY_SEMANTICS_LABEL = "external_transport_history"


@dataclass(frozen=True)
class BenchmarkCheckpointSeed:
    workload_id: str
    checkpoint_id: str
    session: PlantBackendSession
    checkpoint: Mapping[str, object]
    macro_step_time_s: float


def build_phase3_workloads() -> tuple[BenchmarkWorkloadDefinition, ...]:
    return (
        BenchmarkWorkloadDefinition(
            workload_id="ammonia_recycle_warm",
            checkpoint_id="phase3-ammonia-recycle-warm-checkpoint",
            tolerance_profile=PHASE3_TOLERANCE_PROFILE,
            physical_acceptance_profile=PHASE3_PHYSICAL_ACCEPTANCE_PROFILE,
            telemetry_contract_version=PHASE3_TELEMETRY_CONTRACT_VERSION,
            delay_semantics_label=PHASE3_DELAY_SEMANTICS_LABEL,
            checkpoint_builder=build_ammonia_recycle_warm_checkpoint,
            scenario_tags=(
                BenchmarkScenarioTag.WARM_RUN,
                BenchmarkScenarioTag.RECYCLE_HEAVY,
            ),
            description=(
                "Warm-run recycle-sensitive checkpoint derived from the canonical ammonia "
                "flowsheet reference."
            ),
        ),
        BenchmarkWorkloadDefinition(
            workload_id="staged_delay_control_disturbance",
            checkpoint_id="phase3-staged-delay-control-checkpoint",
            tolerance_profile=PHASE3_TOLERANCE_PROFILE,
            physical_acceptance_profile=PHASE3_PHYSICAL_ACCEPTANCE_PROFILE,
            telemetry_contract_version=PHASE3_TELEMETRY_CONTRACT_VERSION,
            delay_semantics_label=PHASE3_DELAY_SEMANTICS_LABEL,
            checkpoint_builder=build_staged_delay_control_disturbance_checkpoint,
            scenario_tags=(
                BenchmarkScenarioTag.DISTURBANCE,
                BenchmarkScenarioTag.CONTROLLER_NETWORK_COUPLING,
                BenchmarkScenarioTag.DELAY_HEAVY,
            ),
            description=(
                "Controller and transport-lag-sensitive disturbance checkpoint built from the "
                "three-tank staged control reference."
            ),
        ),
        BenchmarkWorkloadDefinition(
            workload_id="checkpoint_restart_reconfigure",
            checkpoint_id="phase3-restart-reconfigure-checkpoint",
            tolerance_profile=PHASE3_TOLERANCE_PROFILE,
            physical_acceptance_profile=PHASE3_PHYSICAL_ACCEPTANCE_PROFILE,
            telemetry_contract_version=PHASE3_TELEMETRY_CONTRACT_VERSION,
            delay_semantics_label=PHASE3_DELAY_SEMANTICS_LABEL,
            checkpoint_builder=build_checkpoint_restart_reconfigure_checkpoint,
            scenario_tags=(
                BenchmarkScenarioTag.RESTART_RECONFIGURATION,
                BenchmarkScenarioTag.DELAY_HEAVY,
            ),
            description=(
                "Phase-3-owned restart and reconfiguration checkpoint proving accepted-state "
                "replay and post-save restore under the same fairness contract."
            ),
        ),
    )


def benchmark_workload_coverage_matrix() -> tuple[dict[str, object], ...]:
    return tuple(
        {
            "workload_id": workload.workload_id,
            "checkpoint_id": workload.checkpoint_id,
            "scenario_tags": tuple(tag.value for tag in workload.scenario_tags),
        }
        for workload in build_phase3_workloads()
    )


def build_ammonia_recycle_warm_checkpoint() -> BenchmarkCheckpointSeed:
    session = _build_session(
        checkpoint_id="phase3-ammonia-recycle-warm-checkpoint",
        edges=(
            ("fresh_syngas", "synthesis_mixer.fresh_in"),
            ("recycle_source", "synthesis_mixer.recycle_in"),
            ("synthesis_mixer.to_reactor", "ammonia_reactor.feed_in"),
            ("ammonia_reactor.product_out", "separator.feed_in"),
            ("separator.recycle_out", "recycle_sink.inlet"),
            ("separator.product_out", "product_sink.inlet"),
        ),
        macro_step_time_s=0.25,
    )
    return _seed_checkpoint(
        workload_id="ammonia_recycle_warm",
        checkpoint_id="phase3-ammonia-recycle-warm-checkpoint",
        session=session,
        macro_step_time_s=0.25,
    )


def build_staged_delay_control_disturbance_checkpoint() -> BenchmarkCheckpointSeed:
    session = _build_session(
        checkpoint_id="phase3-staged-delay-control-checkpoint",
        edges=(
            ("fresh_feed_1", "tank_1.fresh_in"),
            ("tank_1.out", "tank_2.cascade_in"),
            ("fresh_feed_2", "tank_2.makeup_in"),
            ("tank_2.out", "tank_3.cascade_in"),
            ("fresh_feed_3", "tank_3.makeup_in"),
            ("tank_3.out", "product_sink.inlet"),
        ),
        macro_step_time_s=10.0,
    )
    return _seed_checkpoint(
        workload_id="staged_delay_control_disturbance",
        checkpoint_id="phase3-staged-delay-control-checkpoint",
        session=session,
        macro_step_time_s=10.0,
    )


def build_checkpoint_restart_reconfigure_checkpoint() -> BenchmarkCheckpointSeed:
    session = _build_session(
        checkpoint_id="phase3-restart-reconfigure-checkpoint",
        edges=(
            ("feed_boundary", "upstream.inlet"),
            ("upstream.outlet", "buffer.inlet"),
            ("buffer.outlet", "product_boundary.inlet"),
        ),
        macro_step_time_s=0.5,
    )
    checkpoint = session.save_checkpoint()
    session.load_checkpoint(checkpoint)
    tx = session.begin_tx()
    tx.add_process("bypass", inlet_ports=("inlet",), outlet_ports=("outlet",))
    tx.commit()
    return BenchmarkCheckpointSeed(
        workload_id="checkpoint_restart_reconfigure",
        checkpoint_id="phase3-restart-reconfigure-checkpoint",
        session=session,
        checkpoint=checkpoint,
        macro_step_time_s=0.5,
    )


def _seed_checkpoint(
    *,
    workload_id: str,
    checkpoint_id: str,
    session: PlantBackendSession,
    macro_step_time_s: float,
) -> BenchmarkCheckpointSeed:
    checkpoint = session.save_checkpoint()
    return BenchmarkCheckpointSeed(
        workload_id=workload_id,
        checkpoint_id=checkpoint_id,
        session=session,
        checkpoint=checkpoint,
        macro_step_time_s=macro_step_time_s,
    )


def _build_session(
    *, checkpoint_id: str, edges: tuple[tuple[str, str], ...], macro_step_time_s: float
) -> PlantBackendSession:
    del checkpoint_id
    network = ConnectionNetwork(
        runtime_orchestrator=ConnectionRuntimeOrchestrator(
            hydraulic_solve_step=_steady_hydraulic_solve_step,
        )
    )
    source_boundaries: set[str] = set()
    sink_boundaries: set[str] = set()
    process_inlets: dict[str, set[str]] = {}
    process_outlets: dict[str, set[str]] = {}

    for source, target in edges:
        if "." in source:
            process_id, port_name = source.split(".", maxsplit=1)
            process_outlets.setdefault(process_id, set()).add(port_name)
        else:
            source_boundaries.add(source)

        if "." in target:
            process_id, port_name = target.split(".", maxsplit=1)
            process_inlets.setdefault(process_id, set()).add(port_name)
        else:
            sink_boundaries.add(target)

    for boundary_id in sorted(source_boundaries):
        network.add_boundary_source(boundary_id)
    for boundary_id in sorted(sink_boundaries):
        network.add_boundary_sink(boundary_id)

    for process_id in sorted(set(process_inlets) | set(process_outlets)):
        network.add_process(
            process_id,
            inlet_ports=tuple(sorted(process_inlets.get(process_id, {"inlet"}))),
            outlet_ports=tuple(sorted(process_outlets.get(process_id, {"outlet"}))),
        )

    for index, (source, target) in enumerate(edges, start=1):
        network.connect(source, target, edge_id=f"checkpoint_edge_{index:02d}")

    session = PlantBackendSession(network=network)
    session.compile()
    session.step(macro_step_time_s)
    return session


def _steady_hydraulic_solve_step(
    *, network: ConnectionNetwork, macro_step_time_s: float
) -> HydraulicSolveResult:
    del network, macro_step_time_s
    _ = HydraulicSystemDefinition(equations=(), linear_residual_equations=())
    return HydraulicSolveResult(
        converged=True,
        iterations=1,
        residual_norm=0.0,
        solution_vector=np.zeros(0, dtype=np.float64),
        unknowns={},
        unknown_index_map={},
        residual_index_map={},
    )


__all__ = [
    "BenchmarkCheckpointSeed",
    "benchmark_workload_coverage_matrix",
    "build_ammonia_recycle_warm_checkpoint",
    "build_checkpoint_restart_reconfigure_checkpoint",
    "build_phase3_workloads",
    "build_staged_delay_control_disturbance_checkpoint",
]
