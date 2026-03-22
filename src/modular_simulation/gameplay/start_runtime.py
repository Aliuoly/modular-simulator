"""Runtime composition helpers for supported realtime slice starts."""

from __future__ import annotations

from dataclasses import dataclass

from modular_simulation.cli.backend_session import PlantBackendSession
from modular_simulation.connection.topology.network import ConnectionNetwork
from modular_simulation.gameplay.economics import CashLedgerRuntime
from modular_simulation.gameplay.sandbox_session import SandboxSessionRuntime
from modular_simulation.gameplay.starts.builders import LEARNER_START_SCAFFOLDS

SUPPORTED_MODE_IDS: tuple[str, ...] = (
    "phase1_process_sandbox_v1",
    "heater_flash_guided_build_v1",
)

MODE_TO_START_ID: dict[str, str] = {
    "phase1_process_sandbox_v1": "phase1_process_sandbox_v1",
    "heater_flash_guided_build_v1": "heater_flash_tutorial_start_v1",
}


@dataclass(frozen=True)
class StartRuntimeBundle:
    mode_id: str
    sandbox_runtime: SandboxSessionRuntime
    cash_ledger_runtime: CashLedgerRuntime
    backend_session: PlantBackendSession


def create_start_runtime_bundle(*, mode_id: str) -> StartRuntimeBundle:
    if mode_id not in SUPPORTED_MODE_IDS:
        raise KeyError(f"Unsupported mode_id: {mode_id!r}")

    ledger = CashLedgerRuntime()
    session_runtime = SandboxSessionRuntime(economics_api=ledger)
    if mode_id == "phase1_process_sandbox_v1":
        session_runtime.start_sandbox()
    else:
        session_runtime.start_tutorial("heater_flash_guided_build_v1")
    ledger.open_cash_ledger()

    start_id = MODE_TO_START_ID[mode_id]
    scaffold = LEARNER_START_SCAFFOLDS[start_id]

    network = ConnectionNetwork()
    for feed_id in scaffold.named_feed_ids:
        network.add_boundary_source(feed_id)
    for sink_id in scaffold.named_sink_ids:
        network.add_boundary_sink(sink_id)

    backend_session = PlantBackendSession(network=network)
    try:
        backend_session.compile()
    except Exception:
        # Topology reads remain available even without a compiled graph.
        pass

    return StartRuntimeBundle(
        mode_id=mode_id,
        sandbox_runtime=session_runtime,
        cash_ledger_runtime=ledger,
        backend_session=backend_session,
    )
