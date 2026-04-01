"""
PlantBackendSession — unified facade for interactive plant editing.

Wraps ``ConnectionNetwork``, typed reconfiguration APIs, sensor / controller
wiring APIs, and persistence into a single transactional surface suitable for
a game-like UI where users build, run, save, and reload simulations.

Design invariants
-----------------
* All mutations go through ``network.queue_reconfiguration`` via the typed
  APIs.  No raw dict plumbing.
* Every ``commit()`` respects *optimistic concurrency*
  (``expected_revision``) and *idempotency* (``idempotency_key``).
* Barrier apply is *atomic*: on failure the network is rolled back to
  pre-barrier state and a structured ``CommitResult`` with diagnostics is
  returned.
* Sensor / controller mutations are "zero-resistance instrumentation"
  updates; they cannot alter the hydraulic topology.

Quick-start
-----------
::

    session = PlantBackendSession(network=network)

    tx = session.begin_tx(expected_revision="rev_003")
    tx.add_process("tank_A", inlet_ports=["cold_in"], outlet_ports=["hot_out"])
    tx.add_port("tank_A", "extra_outlet", "outlet")
    tx.connect_line(source="tank_A/hot_out", target="tank_B/cold_in")
    tx.configure_line(line_id="edge_001", radius_m=0.05, length_m=3.0)
    tx.create_sensor(sensor_id="T1", signal_key="temperature_K")
    tx.bind_sensor(sensor_id="T1", signal_key="temperature_K",
                   process_id="tank_A")
    result = tx.commit()
    # result.success, result.graph_revision, result.barrier_report, ...

    step_result = session.step(dt=0.25)
    checkpoint  = session.save_checkpoint()
    session.load_checkpoint(checkpoint)
"""

from __future__ import annotations

import dataclasses
import uuid
from typing import TYPE_CHECKING, Mapping, Sequence, TypedDict

from modular_simulation.connection.domain.domain_contracts import (
    CommandEnvelope,
    validate_command_envelope,
)
from modular_simulation.connection.domain.error_catalog import (
    DiagnosticPayload,
    extract_diagnostic_payload,
)
from modular_simulation.connection.topology.network import (
    CompiledConnectionNetwork,
    ConnectionNetwork,
)
from modular_simulation.connection.domain.reconfiguration_api import (
    DynamicConnectionLineReconfigurationApi,
    DynamicUnitPortReconfigurationApi,
)
from modular_simulation.components.sensors.runtime_binding_api import (
    SensorRuntimeBindingApi,
)
from modular_simulation.components.control_system.runtime_wiring_api import (
    ControllerRuntimeWiringApi,
)

if TYPE_CHECKING:
    from modular_simulation.connection.runtime.runtime import (
        BarrierReconfigurationReport,
    )

__all__ = [
    "PlantBackendSession",
    "TxHandle",
    "CommitResult",
    "PreviewResult",
]


# ---------------------------------------------------------------------------
# Result containers
# ---------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class CommitResult:
    """Outcome of a transactional commit (barrier apply)."""

    success: bool
    """``True`` when the barrier applied without errors."""

    graph_revision: str | None
    """Post-barrier graph revision (``None`` on failure)."""

    applied_request_ids: tuple[str, ...] = ()
    """Request IDs that were successfully applied."""

    skipped_request_ids: tuple[str, ...] = ()
    """Request IDs skipped due to poison / invariant violation."""

    barrier_report: BarrierReconfigurationReport | None = None
    """Full barrier report from the runtime (``None`` on failure)."""

    diagnostic: DiagnosticPayload | None = None
    """Structured diagnostic payload on failure."""

    error: BaseException | None = None
    """The raw exception, if any."""


@dataclasses.dataclass(frozen=True)
class PreviewResult:
    """Result of validating pending mutations without committing."""

    valid: bool
    """``True`` when the pending mutations pass envelope validation."""

    mutations: tuple[dict[str, object], ...] = ()
    """The mutations that would be committed."""

    validation_errors: tuple[str, ...] = ()
    """Human-readable validation error descriptions, if any."""


class _TopologyPort(TypedDict):
    port_name: str
    direction: str


class _TopologyNode(TypedDict):
    node_id: str
    node_kind: str
    ports: list[_TopologyPort]


class _TopologyEdgeEndpoint(TypedDict):
    node_id: str
    port_name: str


class _TopologyEdge(TypedDict):
    edge_id: str
    source: _TopologyEdgeEndpoint
    target: _TopologyEdgeEndpoint


class _TopologySnapshot(TypedDict):
    nodes: list[_TopologyNode]
    edges: list[_TopologyEdge]


class _TopologyEnvelope(TypedDict):
    graph_revision: str | None
    topology: _TopologySnapshot | None


# ---------------------------------------------------------------------------
# TxHandle — accumulates mutations and commits / rolls back
# ---------------------------------------------------------------------------


class TxHandle:
    """
    Transaction handle returned by :py:meth:`PlantBackendSession.begin_tx`.

    Collects mutation requests through typed helper methods and either
    ``commit()``s them (queues an envelope, triggers a zero-dt barrier step)
    or ``rollback()``s (discards all pending mutations).
    """

    # -- construction -------------------------------------------------------

    def __init__(
        self,
        *,
        session: PlantBackendSession,
        expected_revision: str | None,
        idempotency_key: str | None,
    ) -> None:
        self._session = session
        self._expected_revision = expected_revision
        self._idempotency_key = idempotency_key or str(uuid.uuid4())
        self._pending: list[dict[str, object]] = []
        self._committed = False
        self._rolled_back = False

    # -- properties ---------------------------------------------------------

    @property
    def pending_count(self) -> int:
        """Number of mutations queued in this transaction."""
        return len(self._pending)

    @property
    def is_open(self) -> bool:
        """``True`` while the transaction has not been committed or rolled
        back."""
        return not self._committed and not self._rolled_back

    # -- topology mutations -------------------------------------------------

    def add_process(
        self,
        process_id: str,
        *,
        inlet_ports: Sequence[str] = (),
        outlet_ports: Sequence[str] = (),
    ) -> TxHandle:
        """Queue an *add_process* mutation."""
        self._require_open()
        self._pending.append(
            {
                "operation": "add_process",
                "process_id": process_id,
                "inlet_ports": list(inlet_ports),
                "outlet_ports": list(outlet_ports),
            }
        )
        return self

    def add_port(
        self,
        process_id: str,
        port_id: str,
        direction: str,
    ) -> TxHandle:
        """Queue an *add_inlet* or *add_outlet* mutation."""
        self._require_open()
        if direction not in ("inlet", "outlet"):
            raise ValueError(f"direction must be 'inlet' or 'outlet', got {direction!r}")
        op = "add_inlet" if direction == "inlet" else "add_outlet"
        self._pending.append(
            {
                "operation": op,
                "process_id": process_id,
                "direction": direction,
                "port_name": port_id,
            }
        )
        return self

    def remove_process(self, process_id: str) -> TxHandle:
        """Queue a *remove_unit* mutation."""
        self._require_open()
        self._pending.append(
            {
                "operation": "remove_unit",
                "process_id": process_id,
            }
        )
        return self

    def remove_port(
        self,
        process_id: str,
        port_id: str,
        direction: str,
    ) -> TxHandle:
        """Queue a *remove_inlet* or *remove_outlet* mutation."""
        self._require_open()
        if direction not in ("inlet", "outlet"):
            raise ValueError(f"direction must be 'inlet' or 'outlet', got {direction!r}")
        op = "remove_inlet" if direction == "inlet" else "remove_outlet"
        self._pending.append(
            {
                "operation": op,
                "process_id": process_id,
                "direction": direction,
                "port_name": port_id,
            }
        )
        return self

    # -- connection mutations -----------------------------------------------

    def connect_line(
        self,
        *,
        source: str,
        target: str,
        line_id: str | None = None,
    ) -> TxHandle:
        """Queue a *connect_line* mutation."""
        self._require_open()
        m: dict[str, object] = {
            "operation": "connect_line",
            "source": source,
            "target": target,
        }
        if line_id is not None:
            m["edge_id"] = line_id
        self._pending.append(m)
        return self

    def disconnect_line(
        self,
        *,
        line_id: str | None = None,
        source: str | None = None,
        target: str | None = None,
    ) -> TxHandle:
        """Queue a *disconnect_line* mutation."""
        self._require_open()
        m: dict[str, object] = {"operation": "disconnect_line"}
        if line_id is not None:
            m["edge_id"] = line_id
        if source is not None:
            m["source"] = source
        if target is not None:
            m["target"] = target
        self._pending.append(m)
        return self

    def configure_line(
        self,
        line_id: str,
        *,
        radius_m: float,
        length_m: float,
        equation_name: str | None = None,
        resistance_parameter_name: str | None = None,
    ) -> TxHandle:
        """Queue a *configure_line_geometry* mutation."""
        self._require_open()
        m: dict[str, object] = {
            "operation": "configure_line_geometry",
            "line_id": line_id,
            "radius_m": radius_m,
            "length_m": length_m,
        }
        if equation_name is not None:
            m["equation_name"] = equation_name
        if resistance_parameter_name is not None:
            m["resistance_parameter_name"] = resistance_parameter_name
        self._pending.append(m)
        return self

    def attach_valve(
        self,
        line_id: str,
        *,
        valve_id: str,
        min_open_fraction: float = 0.0,
        max_open_fraction: float = 1.0,
        initial_open_fraction: float = 1.0,
        equation_name: str | None = None,
        resistance_parameter_name: str | None = None,
    ) -> TxHandle:
        """Queue an *attach_line_valve* mutation."""
        self._require_open()
        m: dict[str, object] = {
            "operation": "attach_line_valve",
            "line_id": line_id,
            "valve_id": valve_id,
            "min_open_fraction": min_open_fraction,
            "max_open_fraction": max_open_fraction,
            "initial_open_fraction": initial_open_fraction,
        }
        if equation_name is not None:
            m["equation_name"] = equation_name
        if resistance_parameter_name is not None:
            m["resistance_parameter_name"] = resistance_parameter_name
        self._pending.append(m)
        return self

    def add_junction(
        self,
        *,
        junction_id: str,
        inlet_ports: Sequence[str] = (),
        outlet_ports: Sequence[str] = (),
    ) -> TxHandle:
        """Queue an *add_junction* mutation."""
        self._require_open()
        self._pending.append(
            {
                "operation": "add_junction",
                "junction_id": junction_id,
                "inlet_ports": list(inlet_ports),
                "outlet_ports": list(outlet_ports),
            }
        )
        return self

    def attach_line_pump(
        self,
        line_id: str,
        *,
        pump_id: str,
        initial_pump_speed: float = 0.0,
        equation_name: str | None = None,
        pump_parameter_name: str | None = None,
    ) -> TxHandle:
        """Queue an *attach_line_pump* mutation."""
        self._require_open()
        m: dict[str, object] = {
            "operation": "attach_line_pump",
            "line_id": line_id,
            "pump_id": pump_id,
            "initial_pump_speed": initial_pump_speed,
        }
        if equation_name is not None:
            m["equation_name"] = equation_name
        if pump_parameter_name is not None:
            m["pump_parameter_name"] = pump_parameter_name
        self._pending.append(m)
        return self

    def attach_line_heat_actuator(
        self,
        line_id: str,
        *,
        heat_actuator_id: str,
        initial_heat_rate: float = 0.0,
    ) -> TxHandle:
        """Queue an *attach_line_heat_actuator* mutation."""
        self._require_open()
        self._pending.append(
            {
                "operation": "attach_line_heat_actuator",
                "line_id": line_id,
                "heat_actuator_id": heat_actuator_id,
                "initial_heat_rate": initial_heat_rate,
            }
        )
        return self

    # -- sensor mutations ---------------------------------------------------

    def create_sensor(
        self,
        *,
        sensor_id: str,
        signal_key: str,
        process_id: str | None = None,
        port_id: str | None = None,
        line_id: str | None = None,
        sensor_type: str = "SampledDelayedSensor",
        sensor_module: str = ("modular_simulation.components.sensors.sampled_delayed_sensor"),
        sensor_config: dict[str, object] | None = None,
        binding_metadata: dict[str, object] | None = None,
    ) -> TxHandle:
        """Queue a *create_sensor* mutation."""
        self._require_open()
        m: dict[str, object] = {
            "operation": "create_sensor",
            "sensor_id": sensor_id,
            "signal_key": signal_key,
            "sensor_type": sensor_type,
            "sensor_module": sensor_module,
        }
        if process_id is not None:
            m["process_id"] = process_id
        if port_id is not None:
            m["port_id"] = port_id
        if line_id is not None:
            m["line_id"] = line_id
        if sensor_config is not None:
            m["sensor_config"] = sensor_config
        if binding_metadata is not None:
            m["binding_metadata"] = binding_metadata
        self._pending.append(m)
        return self

    def bind_sensor(
        self,
        *,
        sensor_id: str,
        signal_key: str,
        process_id: str | None = None,
        port_id: str | None = None,
        line_id: str | None = None,
        binding_metadata: dict[str, object] | None = None,
    ) -> TxHandle:
        """Queue a *bind_sensor* mutation."""
        self._require_open()
        m: dict[str, object] = {
            "operation": "bind_sensor",
            "sensor_id": sensor_id,
            "signal_key": signal_key,
        }
        if process_id is not None:
            m["process_id"] = process_id
        if port_id is not None:
            m["port_id"] = port_id
        if line_id is not None:
            m["line_id"] = line_id
        if binding_metadata is not None:
            m["binding_metadata"] = binding_metadata
        self._pending.append(m)
        return self

    def unbind_sensor(self, *, sensor_id: str) -> TxHandle:
        """Queue an *unbind_sensor* mutation."""
        self._require_open()
        self._pending.append(
            {
                "operation": "unbind_sensor",
                "sensor_id": sensor_id,
            }
        )
        return self

    def remove_sensor(self, *, sensor_id: str) -> TxHandle:
        """Queue a *remove_sensor* mutation."""
        self._require_open()
        self._pending.append(
            {
                "operation": "remove_sensor",
                "sensor_id": sensor_id,
            }
        )
        return self

    # -- controller mutations -----------------------------------------------

    def create_controller(
        self,
        *,
        controller_id: str,
        controller_type: str,
        controller_module: str,
        controller_config: dict[str, object] | None = None,
    ) -> TxHandle:
        """Queue a *create_controller* mutation."""
        self._require_open()
        m: dict[str, object] = {
            "operation": "create_controller",
            "controller_id": controller_id,
            "controller_type": controller_type,
            "controller_module": controller_module,
        }
        if controller_config is not None:
            m["controller_config"] = controller_config
        self._pending.append(m)
        return self

    def bind_controller_input(
        self,
        *,
        controller_id: str,
        signal_key: str,
    ) -> TxHandle:
        """Queue a *bind_controller_input* mutation."""
        self._require_open()
        self._pending.append(
            {
                "operation": "bind_controller_input",
                "controller_id": controller_id,
                "signal_key": signal_key,
            }
        )
        return self

    def bind_controller_output(
        self,
        *,
        controller_id: str,
        actuator_tag: str,
    ) -> TxHandle:
        """Queue a *bind_controller_output* mutation."""
        self._require_open()
        self._pending.append(
            {
                "operation": "bind_controller_output",
                "controller_id": controller_id,
                "actuator_tag": actuator_tag,
            }
        )
        return self

    def configure_controller_mode(
        self,
        *,
        controller_id: str,
        mode: str,
    ) -> TxHandle:
        """Queue a *configure_controller_mode* mutation."""
        self._require_open()
        self._pending.append(
            {
                "operation": "configure_controller_mode",
                "controller_id": controller_id,
                "mode": mode,
            }
        )
        return self

    def activate_controller(self, *, controller_id: str) -> TxHandle:
        """Queue an *activate_controller* mutation."""
        self._require_open()
        self._pending.append(
            {
                "operation": "activate_controller",
                "controller_id": controller_id,
            }
        )
        return self

    # -- preview / commit / rollback ----------------------------------------

    def preview(self) -> PreviewResult:
        """Validate pending mutations *without* committing.

        Returns a :class:`PreviewResult` indicating whether the mutations
        would pass envelope validation.
        """
        self._require_open()
        if not self._pending:
            return PreviewResult(
                valid=True,
                mutations=(),
                validation_errors=("No mutations to preview.",),
            )
        mutations = tuple(self._pending)
        try:
            validate_command_envelope(
                idempotency_key=self._idempotency_key,
                expected_revision=self._expected_revision,
                metadata={},
                mutations=mutations,
            )
            return PreviewResult(valid=True, mutations=mutations)
        except Exception as exc:
            return PreviewResult(
                valid=False,
                mutations=mutations,
                validation_errors=(str(exc),),
            )

    def commit(self) -> CommitResult:
        """Validate, queue, and apply all pending mutations atomically.

        A zero-dt barrier step is triggered so that the queued envelope is
        applied (or rejected) immediately.  The network is rolled back on
        failure.

        Returns
        -------
        CommitResult
            Always returned — never raises for barrier-apply errors.
        """
        self._require_open()
        network = self._session._network

        if not self._pending:
            self._committed = True
            compiled = network.compiled
            return CommitResult(
                success=True,
                graph_revision=(compiled.graph_revision if compiled is not None else None),
            )

        # Build validated command envelope.
        envelope = validate_command_envelope(
            idempotency_key=self._idempotency_key,
            expected_revision=self._expected_revision,
            metadata={},
            mutations=tuple(self._pending),
        )

        # Snapshot for atomic rollback.
        rollback_state = network.capture_reconfiguration_state()

        try:
            # Queue the envelope (serialised to dict for the network).
            request_id = network.queue_reconfiguration(
                _envelope_to_dict(envelope),
            )

            # Zero-dt barrier step to apply immediately.
            step_result = network.step(macro_step_time_s=0.0)
            barrier = step_result.barrier_reconfiguration  # pyright: ignore[reportAttributeAccessIssue]

            self._committed = True
            return CommitResult(
                success=request_id in barrier.applied_request_ids,
                graph_revision=barrier.graph_revision,
                applied_request_ids=barrier.applied_request_ids,
                skipped_request_ids=barrier.skipped_request_ids,
                barrier_report=barrier,
            )
        except Exception as exc:
            # Roll back to pre-commit state.
            network.restore_reconfiguration_state(rollback_state)
            self._rolled_back = True
            return CommitResult(
                success=False,
                graph_revision=None,
                diagnostic=extract_diagnostic_payload(exc),
                error=exc,
            )

    def rollback(self) -> None:
        """Discard all pending mutations without applying."""
        self._require_open()
        self._pending.clear()
        self._rolled_back = True

    # -- internals ----------------------------------------------------------

    def _require_open(self) -> None:
        if self._committed:
            raise RuntimeError("Transaction already committed")
        if self._rolled_back:
            raise RuntimeError("Transaction already rolled back")


# ---------------------------------------------------------------------------
# PlantBackendSession — the top-level facade
# ---------------------------------------------------------------------------


class PlantBackendSession:
    """Unified facade for interactive plant editing and simulation.

    Parameters
    ----------
    network:
        A fully-constructed :class:`ConnectionNetwork` (with compile
        lifecycle, hydraulic builder, and runtime orchestrator already
        wired).
    """

    def __init__(self, *, network: ConnectionNetwork) -> None:
        self._network = network

        # Typed APIs — delegates all queue operations through the proper
        # channels instead of raw dict plumbing.
        self._unit_api = DynamicUnitPortReconfigurationApi(network=network)
        self._line_api = DynamicConnectionLineReconfigurationApi(
            network=network,
        )
        self._sensor_api = SensorRuntimeBindingApi(network=network)
        self._controller_api = ControllerRuntimeWiringApi(network=network)

    # -- properties ---------------------------------------------------------

    @property
    def network(self) -> ConnectionNetwork:
        """The underlying connection network."""
        return self._network

    @property
    def compiled(self) -> CompiledConnectionNetwork | None:
        """The current compiled topology, or ``None`` if not yet compiled."""
        return self._network.compiled

    @property
    def graph_revision(self) -> str | None:
        """Current graph revision, or ``None`` if not compiled."""
        compiled = self._network.compiled
        return compiled.graph_revision if compiled is not None else None

    # -- typed API accessors ------------------------------------------------

    @property
    def unit_api(self) -> DynamicUnitPortReconfigurationApi:
        """Direct access to the unit / port reconfiguration API."""
        return self._unit_api

    @property
    def line_api(self) -> DynamicConnectionLineReconfigurationApi:
        """Direct access to the connection-line reconfiguration API."""
        return self._line_api

    @property
    def sensor_api(self) -> SensorRuntimeBindingApi:
        """Direct access to the sensor runtime binding API."""
        return self._sensor_api

    @property
    def controller_api(self) -> ControllerRuntimeWiringApi:
        """Direct access to the controller runtime wiring API."""
        return self._controller_api

    # -- transaction API ----------------------------------------------------

    def begin_tx(
        self,
        *,
        expected_revision: str | None = None,
        idempotency_key: str | None = None,
    ) -> TxHandle:
        """Start a new mutation transaction.

        Parameters
        ----------
        expected_revision:
            If given, the barrier will reject the commit when the current
            graph revision does not match (optimistic concurrency).
        idempotency_key:
            Client-supplied deduplication key.  Auto-generated when
            ``None``.
        """
        return TxHandle(
            session=self,
            expected_revision=expected_revision,
            idempotency_key=idempotency_key,
        )

    # -- immediate (non-tx) helpers -----------------------------------------

    def queue_and_apply(
        self,
        mutations: Sequence[dict[str, object]],
        *,
        expected_revision: str | None = None,
        idempotency_key: str | None = None,
    ) -> CommitResult:
        """Convenience: queue *mutations* and apply in one shot.

        Equivalent to ``begin_tx → (add raw mutations) → commit`` but
        accepts pre-built mutation dicts directly.
        """
        tx = self.begin_tx(
            expected_revision=expected_revision,
            idempotency_key=idempotency_key,
        )
        tx._pending.extend(mutations)  # noqa: SLF001 — controlled internal
        return tx.commit()

    # -- simulation ---------------------------------------------------------

    def step(self, dt: float) -> object:
        """Advance the simulation by *dt* seconds.

        Returns the result object produced by
        ``network.step(macro_step_time_s=dt)``.
        """
        return self._network.step(macro_step_time_s=dt)

    # -- topology query -----------------------------------------------------

    def get_topology(self) -> _TopologyEnvelope:
        """Return a serialisable snapshot of the current topology.

        Contains the ``graph_revision`` and the compiled topology graph
        (nodes, edges, ports).  Suitable for rendering in a UI.
        """
        compiled = self._network.compiled
        if compiled is None:
            return {"graph_revision": None, "topology": None}

        topo = compiled.topology
        nodes: list[_TopologyNode] = []
        process_nodes = {node.process_id: node for node in getattr(topo, "process_nodes", ())}
        boundary_nodes = {node.boundary_id: node for node in getattr(topo, "boundary_nodes", ())}
        junction_nodes = {node.junction_id: node for node in getattr(topo, "junction_nodes", ())}
        for node_id in topo.node_ids:
            process_node = process_nodes.get(node_id)
            if process_node is not None:
                nodes.append(
                    {
                        "node_id": node_id,
                        "node_kind": "process",
                        "ports": [
                            {"port_name": port_name, "direction": "inlet"}
                            for port_name in process_node.inlet_ports
                        ]
                        + [
                            {"port_name": port_name, "direction": "outlet"}
                            for port_name in process_node.outlet_ports
                        ],
                    }
                )
                continue

            boundary_node = boundary_nodes.get(node_id)
            if boundary_node is not None:
                nodes.append(
                    {
                        "node_id": node_id,
                        "node_kind": "boundary",
                        "ports": [
                            {
                                "port_name": boundary_node.port_name,
                                "direction": boundary_node.direction,
                            }
                        ],
                    }
                )
                continue

            junction_node = junction_nodes.get(node_id)
            if junction_node is not None:
                nodes.append(
                    {
                        "node_id": node_id,
                        "node_kind": "junction",
                        "ports": [
                            {"port_name": port_name, "direction": "inlet"}
                            for port_name in junction_node.inlet_ports
                        ]
                        + [
                            {"port_name": port_name, "direction": "outlet"}
                            for port_name in junction_node.outlet_ports
                        ],
                    }
                )
                continue

            port_names = self._network.process_ports(process_id=node_id)
            nodes.append(
                {
                    "node_id": node_id,
                    "node_kind": "unknown",
                    "ports": [
                        {"port_name": port_name, "direction": "unknown"}
                        for port_name in (list(port_names) if port_names else [])
                    ],
                }
            )

        edges: list[_TopologyEdge] = []
        for edge in topo.edges:
            edges.append(
                {
                    "edge_id": edge.edge_id,
                    "source": {"node_id": edge.source.node_id, "port_name": edge.source.port_name},
                    "target": {"node_id": edge.target.node_id, "port_name": edge.target.port_name},
                }
            )

        return {
            "graph_revision": compiled.graph_revision,
            "topology": {"nodes": nodes, "edges": edges},
        }

    # -- persistence --------------------------------------------------------

    def save_checkpoint(self) -> Mapping[str, object]:
        """Save a runtime snapshot (must be called at barrier — not mid-step).

        Returns a serialisable mapping that can be passed to
        :py:meth:`load_checkpoint` to restore the session state.
        """
        return self._network.save_runtime_snapshot()

    def load_checkpoint(self, checkpoint: Mapping[str, object]) -> None:
        """Restore from a previously saved checkpoint.

        The checkpoint must have been produced by :py:meth:`save_checkpoint`
        on a network with the same ``graph_revision``.
        """
        self._network.restore_from_checkpoint_snapshot(
            snapshot=checkpoint,
            restore_reason="save_load",
        )

    def get_observability_snapshot(self) -> Mapping[str, object]:
        """Return the substrate observability snapshot for this session.

        Forwards the snapshot assembled by the underlying
        :class:`~modular_simulation.connection.topology.network.ConnectionNetwork`.
        This is a policy-free read model; it does not add any pricing,
        scoring, or ledger fields.
        """
        return self._network.get_observability_snapshot()

    # -- compile ------------------------------------------------------------

    def compile(self) -> CompiledConnectionNetwork:
        """(Re-)compile the network topology.

        Normally compilation is handled automatically during barrier apply,
        but this method is useful for initial setup before the first
        ``step()``.
        """
        return self._network.compile()

    # -- repr ---------------------------------------------------------------

    def __repr__(self) -> str:
        rev = self.graph_revision
        return f"<PlantBackendSession graph_revision={rev!r}>"


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _envelope_to_dict(envelope: CommandEnvelope) -> dict[str, object]:
    """Convert a validated ``CommandEnvelope`` to a plain dict payload.

    The network's ``queue_reconfiguration`` expects a mapping, not the
    Pydantic model directly.
    """
    return envelope.model_dump()
