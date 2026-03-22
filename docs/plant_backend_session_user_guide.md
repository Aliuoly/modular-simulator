# PlantBackendSession User Guide

`PlantBackendSession` is the **low-level runtime-editing and topology-management substrate** for user-facing applications built on this educational chemical-process backend. It is *not* the owner of gameplay progression rules, economics, or classroom orchestration logic — those concerns belong to higher-level layers that compose `PlantBackendSession` rather than live inside it.

User-facing educational gameplay or classroom orchestration tools should treat `PlantBackendSession` as the physical/runtime substrate: it manages topology, sensors, controllers, and simulation stepping. Progression, economics, and scenario state are responsibilities of the gameplay layer above.

In this repository, that higher-level split now exists in `src/modular_simulation/gameplay/` as a separate sandbox simulation session and economics ledger layer. For a minimal end-to-end example of that split, see `examples/dynamic_api_cli/sandbox_backend_minimal.py`.

This guide explains how to use `PlantBackendSession` as a user-facing backend for interactive plant editing (for example, a game-like UI where users add processes, ports, lines, sensors, and controllers at runtime).

The focus is practical usage:
- how to define a multi-process system,
- how to install sensors and controllers,
- how to run,
- how to save/load/restart,
- and how to expose this cleanly to frontends.

## What PlantBackendSession Gives You

`PlantBackendSession` is a facade over `ConnectionNetwork` plus typed reconfiguration APIs.

Key benefits:
- single entry point for editing and runtime operations,
- transaction batching (`begin_tx` + `TxHandle`),
- preview-before-commit validation,
- atomic barrier apply with rollback-on-failure,
- optimistic concurrency (`expected_revision`) and idempotency support,
- serializable topology snapshot for UI rendering,
- checkpoint save/load for restart workflows.

API location:
- `src/modular_simulation/cli/backend_session.py`

## Recommended Starting Examples

If you want runnable companions while reading this guide, use this order:

1. `examples/dynamic_api_cli/minimal_command_quickstart.py`
   - smallest command-first path for topology edits, barrier apply, and graph revision changes.
2. `examples/dynamic_api_cli/minimal_control_loop_save_load.py`
   - adds runtime sensor/controller wiring plus save/load/continue on a still-minimal setup.
3. `examples/dynamic_api_cli/minimal_spec_quickstart.py`
   - keep as reference only when you specifically need `spec_diff` / `spec_apply`; it is no longer the primary onboarding path.

For the broader curated example list, see [Examples Catalog](examples_catalog.md).

## Core Concepts

### Graph Revision

Every successful reconfiguration updates a `graph_revision`.

Use it for frontend concurrency:
- UI reads topology with revision `rN`.
- UI sends edits with `expected_revision=rN`.
- Backend rejects stale edits if another writer already moved the graph to `rN+1`.

### Idempotency Key

`idempotency_key` protects against duplicate submissions (for example, network retries).

- Same key + same payload: safe dedupe.
- Same key + different payload: conflict (diagnostic error).

### Barrier Apply

Mutations are queued, then applied at barrier (typically `step(0.0)` during commit).

- On success: commit result contains applied request ids and new revision.
- On failure: queued commit is rolled back atomically.

## Typical End-to-End Workflow

1. Create and compile a `ConnectionNetwork`.
2. Create `PlantBackendSession(network=...)`.
3. Start a transaction with `begin_tx(...)`.
4. Add/edit processes, ports, lines, sensors, and controllers.
5. `preview()` to validate.
6. `commit()` to apply atomically.
7. Run simulation with `step(dt)`.
8. Save with `save_checkpoint()`.
9. Reload with `load_checkpoint(...)` and continue.

## Step 1: Build the Base Network and Session

```python
from modular_simulation.cli.backend_session import PlantBackendSession
from modular_simulation.connection.topology.network import ConnectionNetwork

# Build network as usual (compile lifecycle, hydraulic builder, runtime orchestrator, etc.)
network = ConnectionNetwork(
    compile_lifecycle=...,  # your HydraulicCompileLifecycle
    hydraulic_system_builder=...,  # your HydraulicSystemBuilder callback
    runtime_orchestrator=...,  # your ConnectionRuntimeOrchestrator
)

# Optional static scaffolding before dynamic edits
network.add_boundary_source("feed")
network.add_boundary_sink("product")
network.compile()

session = PlantBackendSession(network=network)
```

## Step 2: Define a Multi-Process System (Transaction)

Use one transaction to apply a coherent topology update.

```python
tx = session.begin_tx(expected_revision=session.graph_revision)

(tx
    .add_process("tank_a", inlet_ports=("in",), outlet_ports=("out",))
    .add_process("tank_b", inlet_ports=("in",), outlet_ports=("out",))
    .connect_line(source="feed.outlet", target="tank_a.in", line_id="line_feed")
    .connect_line(source="tank_a.out", target="tank_b.in", line_id="line_ab")
    .connect_line(source="tank_b.out", target="product.inlet", line_id="line_product")
    .configure_line("line_ab", radius_m=0.05, length_m=3.0)
    .attach_valve("line_ab", valve_id="valve_ab", initial_open_fraction=0.65)
)

preview = tx.preview()
if not preview.valid:
    raise RuntimeError(preview.validation_errors)

result = tx.commit()
if not result.success:
    raise RuntimeError(result.diagnostic or result.error)
```

## Step 3: Install Sensors and Controllers

Add instrumentation in the same transaction or separate transactions.

```python
tx = session.begin_tx(expected_revision=session.graph_revision)

(tx
    .create_sensor(
        sensor_id="s_tank_b_level",
        signal_key="tank_b_level_signal",
        process_id="tank_b",
        port_id="out",
    )
    .create_controller(
        controller_id="c_level",
        controller_type="PIDController",
        controller_module="modular_simulation.components.control_system.controllers.pid_controller",
        controller_config={
            "kp": 1.0,
            "ki": 0.2,
            "kd": 0.0,
            "sample_time": 0.1,
        },
    )
    .bind_controller_input(controller_id="c_level", signal_key="tank_b_level_signal")
    .bind_controller_output(controller_id="c_level", actuator_tag="valve_ab")
    .configure_controller_mode(controller_id="c_level", mode="auto")
    .activate_controller(controller_id="c_level")
)

result = tx.commit()
if not result.success:
    raise RuntimeError(result.diagnostic or result.error)
```

Notes:
- `create_sensor(...)` supports process/port or line binding targets.
- controller output `actuator_tag` should match your actuator wiring convention.

## Step 4: Run and Observe

```python
# Advance one macro step
step_result = session.step(0.25)

# Read topology for UI graph rendering
topology_payload = session.get_topology()
print(topology_payload["graph_revision"])
```

`get_topology()` returns a JSON-friendly payload:
- `graph_revision`
- `topology.nodes` with `node_id`, `kind`, `port_names`
- `topology.edges` with `edge_id`, `source`, `target`

## Step 5: Save, Load, Restart

```python
# Save runtime checkpoint (in-memory mapping)
checkpoint = session.save_checkpoint()

# Persist if desired
import json
with open("checkpoint.json", "w", encoding="utf-8") as handle:
    json.dump(checkpoint, handle, indent=2)

# ... later (same graph topology expected)
with open("checkpoint.json", "r", encoding="utf-8") as handle:
    restored = json.load(handle)

session.load_checkpoint(restored)

# Continue stepping after restart
session.step(0.25)
```

Important:
- checkpoint restore expects compatible graph revision/topology contract.
- save/load must happen outside an active macro-step barrier.

## Full Transaction Surface (TxHandle)

Topology and line edits:
- `add_process(process_id, inlet_ports=(), outlet_ports=())`
- `add_port(process_id, port_id, direction)`
- `remove_process(process_id)`
- `remove_port(process_id, port_id, direction)`
- `connect_line(source, target, line_id=None)`
- `disconnect_line(line_id=None, source=None, target=None)`
- `configure_line(line_id, radius_m, length_m, equation_name=None, resistance_parameter_name=None)`
- `attach_valve(line_id, valve_id, min_open_fraction=0.0, max_open_fraction=1.0, initial_open_fraction=1.0, equation_name=None, resistance_parameter_name=None)`

Sensors:
- `create_sensor(sensor_id, signal_key, process_id=None, port_id=None, line_id=None, sensor_type=..., sensor_module=..., sensor_config=None, binding_metadata=None)`
- `bind_sensor(sensor_id, signal_key, process_id=None, port_id=None, line_id=None, binding_metadata=None)`
- `unbind_sensor(sensor_id)`
- `remove_sensor(sensor_id)`

Controllers:
- `create_controller(controller_id, controller_type, controller_module, controller_config=None)`
- `bind_controller_input(controller_id, signal_key)`
- `bind_controller_output(controller_id, actuator_tag)`
- `configure_controller_mode(controller_id, mode)`
- `activate_controller(controller_id)`

Lifecycle and diagnostics:
- `preview()`
- `commit()`
- `rollback()`
- `pending_count`
- `is_open`

## CommitResult and PreviewResult

`PreviewResult`:
- `valid: bool`
- `mutations: tuple[dict[str, object], ...]`
- `validation_errors: tuple[dict[str, object], ...]`

`CommitResult`:
- `success: bool`
- `graph_revision: str | None`
- `applied_request_ids: tuple[str, ...]`
- `skipped_request_ids: tuple[str, ...]`
- `barrier_report`
- `diagnostic`
- `error`

Use `diagnostic` to return structured API errors to frontend clients.

## Backend Endpoint Mapping (Suggested)

For user-facing applications, a clean pattern is:

- `GET /plant/topology`
  - backend: `session.get_topology()`

- `POST /plant/tx/preview`
  - request: list of mutations + optional `expected_revision`
  - backend: build a transaction from request mutations, then call `preview()` without committing

- `POST /plant/tx/commit`
  - request: list of mutations + optional `expected_revision` + optional `idempotency_key`
  - backend: `begin_tx(...)->commit()`
  - response: `CommitResult`

- `POST /plant/step`
  - request: `dt`
  - backend: `session.step(dt)`

- `POST /plant/checkpoint/save`
  - backend: `session.save_checkpoint()`

- `POST /plant/checkpoint/load`
  - request: checkpoint payload
  - backend: `session.load_checkpoint(payload)`

## Practical Concurrency Pattern for UIs

1. Client fetches topology and gets `graph_revision`.
2. Client submits edit command batch with `expected_revision`.
3. If commit fails with revision mismatch:
   - fetch fresh topology,
   - rebase/rebuild batch,
   - retry with new revision.
4. Reuse `idempotency_key` on retries of the same batch.

## Related Examples

Run these primary examples for concrete behavior:

```bash
uv run python examples/dynamic_api_cli/minimal_command_quickstart.py
uv run python examples/dynamic_api_cli/minimal_control_loop_save_load.py
```

Reference-only example:

```bash
uv run python examples/dynamic_api_cli/minimal_spec_quickstart.py
```

Use the spec quickstart when you need declarative spec diff/apply behavior; otherwise prefer the command-first path above.

## Troubleshooting

- Preview fails:
  - inspect `PreviewResult.validation_errors` for code/path/hint details.

- Commit fails:
  - inspect `CommitResult.diagnostic` first,
  - then `CommitResult.error` for unexpected exceptions.

- Load checkpoint fails:
  - verify topology/graph revision compatibility,
  - ensure no active macro-step is in progress.

- No changes applied:
  - ensure transaction is open and contains pending mutations (`pending_count > 0`).
