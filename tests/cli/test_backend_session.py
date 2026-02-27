"""Tests for :mod:`modular_simulation.cli.backend_session`."""

from __future__ import annotations

import dataclasses
from types import SimpleNamespace
from typing import Any, Mapping

import pytest

from modular_simulation.cli.backend_session import (
    CommitResult,
    PlantBackendSession,
    PreviewResult,
    TxHandle,
)


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


@dataclasses.dataclass
class _FakeBarrierReport:
    applied_request_ids: tuple[str, ...] = ()
    skipped_request_ids: tuple[str, ...] = ()
    graph_revision: str | None = "rev_001"


@dataclasses.dataclass
class _FakeStepResult:
    barrier_reconfiguration: _FakeBarrierReport = dataclasses.field(
        default_factory=_FakeBarrierReport,
    )


class _FakeTopology:
    """Minimal topology stand-in with node_ids and edges."""

    def __init__(
        self,
        node_ids: tuple[str, ...] = (),
        edges: tuple[Any, ...] = (),
    ) -> None:
        self.node_ids = node_ids
        self.edges = edges


@dataclasses.dataclass
class _FakeCompiled:
    graph_revision: str = "rev_000"
    topology: _FakeTopology = dataclasses.field(default_factory=_FakeTopology)


class _FakeNetwork:
    """Duck-typed stand-in for ``ConnectionNetwork``.

    Records all calls to ``queue_reconfiguration`` and returns deterministic
    request IDs.
    """

    def __init__(
        self,
        *,
        compiled: _FakeCompiled | None = None,
        step_result: _FakeStepResult | None = None,
        step_raises: BaseException | None = None,
    ) -> None:
        self.queued: list[object] = []
        self._compiled = compiled
        self._step_result = step_result or _FakeStepResult()
        self._step_raises = step_raises
        self._call_count = 0
        self._snapshot: Mapping[str, object] | None = None
        self._reconfiguration_state: object = None
        self._port_registry: dict[str, tuple[str, ...]] = {}

    # -- ConnectionNetwork protocol ------------------------------------------

    @property
    def compiled(self) -> _FakeCompiled | None:
        return self._compiled

    def queue_reconfiguration(self, request: object) -> str:
        self.queued.append(request)
        self._call_count += 1
        return f"rq_{self._call_count:04d}"

    def step(self, *, macro_step_time_s: float) -> _FakeStepResult:
        if self._step_raises is not None:
            raise self._step_raises
        # The first queued request id goes into applied_request_ids
        report = self._step_result.barrier_reconfiguration
        if not report.applied_request_ids and self.queued:
            # Auto-populate applied_request_ids with the last request
            last_id = f"rq_{self._call_count:04d}"
            object.__setattr__(report, "applied_request_ids", (last_id,))
        return self._step_result

    def compile(self) -> _FakeCompiled:
        if self._compiled is None:
            self._compiled = _FakeCompiled()
        return self._compiled

    def process_ports(self, *, process_id: str) -> tuple[str, ...] | None:
        return self._port_registry.get(process_id)

    def capture_reconfiguration_state(self) -> object:
        self._reconfiguration_state = {"captured": True}
        return self._reconfiguration_state

    def restore_reconfiguration_state(self, state: object) -> None:
        self._reconfiguration_state = state

    def save_runtime_snapshot(self) -> Mapping[str, object]:
        return {
            "snapshot": "saved",
            "graph_revision": getattr(self._compiled, "graph_revision", None),
        }

    def resume_from_snapshot(self, *, snapshot: object) -> None:
        self._snapshot = snapshot  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def fake_network() -> _FakeNetwork:
    return _FakeNetwork(compiled=_FakeCompiled())


@pytest.fixture()
def session(fake_network: _FakeNetwork) -> PlantBackendSession:
    return PlantBackendSession(network=fake_network)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# PlantBackendSession — construction & properties
# ---------------------------------------------------------------------------


class TestSessionProperties:
    def test_network_property_returns_underlying_network(
        self,
        session: PlantBackendSession,
        fake_network: _FakeNetwork,
    ) -> None:
        assert session.network is fake_network

    def test_compiled_delegates_to_network(
        self,
        session: PlantBackendSession,
    ) -> None:
        assert session.compiled is not None
        assert session.compiled.graph_revision == "rev_000"

    def test_graph_revision_returns_none_when_not_compiled(self) -> None:
        net = _FakeNetwork(compiled=None)
        s = PlantBackendSession(network=net)  # type: ignore[arg-type]
        assert s.graph_revision is None

    def test_graph_revision_returns_current_revision(
        self,
        session: PlantBackendSession,
    ) -> None:
        assert session.graph_revision == "rev_000"

    def test_repr_includes_revision(self, session: PlantBackendSession) -> None:
        r = repr(session)
        assert "PlantBackendSession" in r
        assert "rev_000" in r


# ---------------------------------------------------------------------------
# begin_tx
# ---------------------------------------------------------------------------


class TestBeginTx:
    def test_begin_tx_returns_open_handle(self, session: PlantBackendSession) -> None:
        tx = session.begin_tx()
        assert isinstance(tx, TxHandle)
        assert tx.is_open
        assert tx.pending_count == 0

    def test_begin_tx_with_expected_revision(self, session: PlantBackendSession) -> None:
        tx = session.begin_tx(expected_revision="rev_000")
        assert tx.is_open

    def test_begin_tx_with_custom_idempotency_key(
        self,
        session: PlantBackendSession,
    ) -> None:
        tx = session.begin_tx(idempotency_key="my-key-123")
        assert tx.is_open


# ---------------------------------------------------------------------------
# TxHandle — mutation accumulation
# ---------------------------------------------------------------------------


class TestTxMutations:
    def test_add_process_queues_mutation(self, session: PlantBackendSession) -> None:
        tx = session.begin_tx()
        result = tx.add_process("tank_A", inlet_ports=["in1"], outlet_ports=["out1"])
        assert result is tx  # fluent API
        assert tx.pending_count == 1

    def test_add_port_queues_inlet(self, session: PlantBackendSession) -> None:
        tx = session.begin_tx()
        tx.add_port("tank_A", "cold_in", "inlet")
        assert tx.pending_count == 1

    def test_add_port_queues_outlet(self, session: PlantBackendSession) -> None:
        tx = session.begin_tx()
        tx.add_port("tank_A", "hot_out", "outlet")
        assert tx.pending_count == 1

    def test_add_port_rejects_invalid_direction(
        self,
        session: PlantBackendSession,
    ) -> None:
        tx = session.begin_tx()
        with pytest.raises(ValueError, match="direction must be"):
            tx.add_port("tank_A", "port", "sideways")

    def test_remove_process(self, session: PlantBackendSession) -> None:
        tx = session.begin_tx()
        tx.remove_process("tank_A")
        assert tx.pending_count == 1

    def test_remove_port_rejects_invalid_direction(
        self,
        session: PlantBackendSession,
    ) -> None:
        tx = session.begin_tx()
        with pytest.raises(ValueError, match="direction must be"):
            tx.remove_port("tank_A", "port", "up")

    def test_connect_line(self, session: PlantBackendSession) -> None:
        tx = session.begin_tx()
        tx.connect_line(source="A/out", target="B/in")
        assert tx.pending_count == 1

    def test_connect_line_with_explicit_id(
        self,
        session: PlantBackendSession,
    ) -> None:
        tx = session.begin_tx()
        tx.connect_line(source="A/out", target="B/in", line_id="pipe_1")
        assert tx.pending_count == 1

    def test_disconnect_line(self, session: PlantBackendSession) -> None:
        tx = session.begin_tx()
        tx.disconnect_line(line_id="pipe_1")
        assert tx.pending_count == 1

    def test_configure_line(self, session: PlantBackendSession) -> None:
        tx = session.begin_tx()
        tx.configure_line("pipe_1", radius_m=0.05, length_m=3.0)
        assert tx.pending_count == 1

    def test_attach_valve(self, session: PlantBackendSession) -> None:
        tx = session.begin_tx()
        tx.attach_valve("pipe_1", valve_id="V1")
        assert tx.pending_count == 1

    def test_create_sensor(self, session: PlantBackendSession) -> None:
        tx = session.begin_tx()
        tx.create_sensor(sensor_id="T1", signal_key="temperature_K")
        assert tx.pending_count == 1

    def test_bind_sensor(self, session: PlantBackendSession) -> None:
        tx = session.begin_tx()
        tx.bind_sensor(sensor_id="T1", signal_key="temperature_K", process_id="tank_A")
        assert tx.pending_count == 1

    def test_unbind_sensor(self, session: PlantBackendSession) -> None:
        tx = session.begin_tx()
        tx.unbind_sensor(sensor_id="T1")
        assert tx.pending_count == 1

    def test_remove_sensor(self, session: PlantBackendSession) -> None:
        tx = session.begin_tx()
        tx.remove_sensor(sensor_id="T1")
        assert tx.pending_count == 1

    def test_create_controller(self, session: PlantBackendSession) -> None:
        tx = session.begin_tx()
        tx.create_controller(
            controller_id="PID_1",
            controller_type="PIDController",
            controller_module="modular_simulation.components.control_system.pid",
        )
        assert tx.pending_count == 1

    def test_bind_controller_input(self, session: PlantBackendSession) -> None:
        tx = session.begin_tx()
        tx.bind_controller_input(controller_id="PID_1", signal_key="temperature_K")
        assert tx.pending_count == 1

    def test_bind_controller_output(self, session: PlantBackendSession) -> None:
        tx = session.begin_tx()
        tx.bind_controller_output(controller_id="PID_1", actuator_tag="heater")
        assert tx.pending_count == 1

    def test_configure_controller_mode(self, session: PlantBackendSession) -> None:
        tx = session.begin_tx()
        tx.configure_controller_mode(controller_id="PID_1", mode="auto")
        assert tx.pending_count == 1

    def test_activate_controller(self, session: PlantBackendSession) -> None:
        tx = session.begin_tx()
        tx.activate_controller(controller_id="PID_1")
        assert tx.pending_count == 1

    def test_fluent_chaining_accumulates(self, session: PlantBackendSession) -> None:
        tx = session.begin_tx()
        tx.add_process("A", inlet_ports=["i"]).connect_line(
            source="A/i",
            target="B/o",
        ).configure_line("edge_001", radius_m=0.05, length_m=3.0)
        assert tx.pending_count == 3


# ---------------------------------------------------------------------------
# TxHandle — commit
# ---------------------------------------------------------------------------


class TestTxCommit:
    def test_commit_empty_tx_returns_success(
        self,
        session: PlantBackendSession,
    ) -> None:
        tx = session.begin_tx()
        result = tx.commit()
        assert result.success
        assert result.graph_revision == "rev_000"
        assert not tx.is_open

    def test_commit_queues_envelope_and_triggers_barrier(
        self,
        session: PlantBackendSession,
        fake_network: _FakeNetwork,
    ) -> None:
        tx = session.begin_tx()
        tx.add_process("tank_A", inlet_ports=["in1"])
        result = tx.commit()

        assert result.success
        assert result.graph_revision == "rev_001"
        assert len(fake_network.queued) == 1
        assert not tx.is_open

    def test_commit_includes_applied_request_ids(
        self,
        session: PlantBackendSession,
    ) -> None:
        tx = session.begin_tx()
        tx.add_process("tank_A")
        result = tx.commit()
        assert len(result.applied_request_ids) > 0

    def test_commit_on_barrier_failure_rolls_back(self) -> None:
        error = RuntimeError("barrier exploded")
        net = _FakeNetwork(
            compiled=_FakeCompiled(),
            step_raises=error,
        )
        s = PlantBackendSession(network=net)  # type: ignore[arg-type]

        tx = s.begin_tx()
        tx.add_process("tank_A")
        result = tx.commit()

        assert not result.success
        assert result.graph_revision is None
        assert result.error is error
        assert not tx.is_open

    def test_commit_prevents_double_commit(
        self,
        session: PlantBackendSession,
    ) -> None:
        tx = session.begin_tx()
        tx.commit()
        with pytest.raises(RuntimeError, match="already committed"):
            tx.commit()

    def test_commit_after_rollback_raises(
        self,
        session: PlantBackendSession,
    ) -> None:
        tx = session.begin_tx()
        tx.rollback()
        with pytest.raises(RuntimeError, match="already rolled back"):
            tx.commit()


# ---------------------------------------------------------------------------
# TxHandle — rollback
# ---------------------------------------------------------------------------


class TestTxRollback:
    def test_rollback_discards_pending(self, session: PlantBackendSession) -> None:
        tx = session.begin_tx()
        tx.add_process("tank_A")
        tx.add_process("tank_B")
        tx.rollback()
        assert not tx.is_open

    def test_rollback_prevents_further_mutations(
        self,
        session: PlantBackendSession,
    ) -> None:
        tx = session.begin_tx()
        tx.rollback()
        with pytest.raises(RuntimeError, match="already rolled back"):
            tx.add_process("tank_A")


# ---------------------------------------------------------------------------
# TxHandle — preview
# ---------------------------------------------------------------------------


class TestTxPreview:
    def test_preview_empty_returns_valid_with_note(
        self,
        session: PlantBackendSession,
    ) -> None:
        tx = session.begin_tx()
        preview = tx.preview()
        assert preview.valid
        assert preview.mutations == ()
        assert len(preview.validation_errors) > 0  # "No mutations to preview."

    def test_preview_with_mutations_returns_valid(
        self,
        session: PlantBackendSession,
    ) -> None:
        tx = session.begin_tx()
        tx.add_process("tank_A", inlet_ports=["in1"])
        preview = tx.preview()
        assert preview.valid
        assert len(preview.mutations) == 1

    def test_preview_does_not_consume_mutations(
        self,
        session: PlantBackendSession,
    ) -> None:
        tx = session.begin_tx()
        tx.add_process("tank_A")
        tx.preview()
        assert tx.pending_count == 1  # Still there

    def test_preview_after_commit_raises(
        self,
        session: PlantBackendSession,
    ) -> None:
        tx = session.begin_tx()
        tx.commit()
        with pytest.raises(RuntimeError, match="already committed"):
            tx.preview()


# ---------------------------------------------------------------------------
# PlantBackendSession — queue_and_apply
# ---------------------------------------------------------------------------


class TestQueueAndApply:
    def test_queue_and_apply_commits_mutations(
        self,
        session: PlantBackendSession,
        fake_network: _FakeNetwork,
    ) -> None:
        result = session.queue_and_apply(
            [
                {
                    "operation": "add_process",
                    "process_id": "X",
                    "inlet_ports": [],
                    "outlet_ports": [],
                }
            ],
        )
        assert result.success
        assert len(fake_network.queued) == 1


# ---------------------------------------------------------------------------
# PlantBackendSession — step
# ---------------------------------------------------------------------------


class TestStep:
    def test_step_delegates_to_network(
        self,
        session: PlantBackendSession,
    ) -> None:
        result = session.step(dt=0.25)
        assert result is not None


# ---------------------------------------------------------------------------
# PlantBackendSession — topology query
# ---------------------------------------------------------------------------


class TestGetTopology:
    def test_get_topology_when_not_compiled(self) -> None:
        net = _FakeNetwork(compiled=None)
        s = PlantBackendSession(network=net)  # type: ignore[arg-type]
        topo = s.get_topology()
        assert topo["graph_revision"] is None
        assert topo["topology"] is None

    def test_get_topology_with_compiled_network(self) -> None:
        fake_edge = SimpleNamespace(
            edge_id="edge_001",
            source=SimpleNamespace(node_id="A", port_name="out"),
            target=SimpleNamespace(node_id="B", port_name="in"),
        )
        topology = _FakeTopology(node_ids=("A", "B"), edges=(fake_edge,))
        compiled = _FakeCompiled(graph_revision="rev_002", topology=topology)
        net = _FakeNetwork(compiled=compiled)
        net._port_registry = {"A": ("out",), "B": ("in",)}

        s = PlantBackendSession(network=net)  # type: ignore[arg-type]
        topo = s.get_topology()

        assert topo["graph_revision"] == "rev_002"
        assert topo["topology"] is not None
        nodes = topo["topology"]["nodes"]  # type: ignore[index]
        edges = topo["topology"]["edges"]  # type: ignore[index]
        assert len(nodes) == 2
        assert len(edges) == 1
        assert edges[0]["edge_id"] == "edge_001"
        assert edges[0]["source"]["node_id"] == "A"
        assert edges[0]["target"]["node_id"] == "B"


# ---------------------------------------------------------------------------
# PlantBackendSession — persistence
# ---------------------------------------------------------------------------


class TestPersistence:
    def test_save_checkpoint_returns_mapping(
        self,
        session: PlantBackendSession,
    ) -> None:
        checkpoint = session.save_checkpoint()
        assert isinstance(checkpoint, Mapping)
        assert "snapshot" in checkpoint

    def test_load_checkpoint_delegates_to_network(
        self,
        session: PlantBackendSession,
        fake_network: _FakeNetwork,
    ) -> None:
        checkpoint = {"snapshot": "saved", "graph_revision": "rev_000"}
        session.load_checkpoint(checkpoint)
        assert fake_network._snapshot == checkpoint


# ---------------------------------------------------------------------------
# PlantBackendSession — compile
# ---------------------------------------------------------------------------


class TestCompile:
    def test_compile_returns_compiled_network(
        self,
        session: PlantBackendSession,
    ) -> None:
        compiled = session.compile()
        assert compiled is not None
        assert compiled.graph_revision == "rev_000"

    def test_compile_creates_compiled_when_none(self) -> None:
        net = _FakeNetwork(compiled=None)
        s = PlantBackendSession(network=net)  # type: ignore[arg-type]
        compiled = s.compile()
        assert compiled is not None


# ---------------------------------------------------------------------------
# CommitResult / PreviewResult dataclass contracts
# ---------------------------------------------------------------------------


class TestResultDataclasses:
    def test_commit_result_is_frozen(self) -> None:
        r = CommitResult(success=True, graph_revision="rev_001")
        with pytest.raises(dataclasses.FrozenInstanceError):
            r.success = False  # type: ignore[misc]

    def test_preview_result_is_frozen(self) -> None:
        r = PreviewResult(valid=True)
        with pytest.raises(dataclasses.FrozenInstanceError):
            r.valid = False  # type: ignore[misc]

    def test_commit_result_defaults(self) -> None:
        r = CommitResult(success=False, graph_revision=None)
        assert r.applied_request_ids == ()
        assert r.skipped_request_ids == ()
        assert r.barrier_report is None
        assert r.diagnostic is None
        assert r.error is None


# ---------------------------------------------------------------------------
# Multiple transactions on same session
# ---------------------------------------------------------------------------


class TestMultipleTransactions:
    def test_sequential_transactions(
        self,
        session: PlantBackendSession,
        fake_network: _FakeNetwork,
    ) -> None:
        tx1 = session.begin_tx()
        tx1.add_process("tank_A")
        tx1.commit()

        tx2 = session.begin_tx()
        tx2.add_process("tank_B")
        tx2.commit()

        # Both should have queued payloads
        assert len(fake_network.queued) == 2


# ---------------------------------------------------------------------------
# Typed API accessors
# ---------------------------------------------------------------------------


class TestTypedApiAccessors:
    def test_unit_api_exposed(self, session: PlantBackendSession) -> None:
        assert session.unit_api is not None

    def test_line_api_exposed(self, session: PlantBackendSession) -> None:
        assert session.line_api is not None

    def test_sensor_api_exposed(self, session: PlantBackendSession) -> None:
        assert session.sensor_api is not None

    def test_controller_api_exposed(self, session: PlantBackendSession) -> None:
        assert session.controller_api is not None
