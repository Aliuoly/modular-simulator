## Context

- `ConnectionNetwork` already owns public runtime operations such as stepping, queued reconfiguration handling, and persistence snapshots via `save_runtime_snapshot()` / `resume_from_snapshot()`.
- `ConnectedPlantOrchestrator` already knows how to snapshot published subsystem measurements and plant-calculation outputs, but that data is not yet exposed through a stable, consumer-facing substrate contract.
- `PlantBackendSession` is already the user-facing facade for topology and checkpoint access, and repo positioning specs require it to stay a thin substrate surface rather than absorbing gameplay or economics policy.
- `sandbox_session.py` and future economics consumers need observability reads for physical-state rollups, but those should come from a substrate-owned read model rather than duplicated gameplay-side derivations.

## Goals / Non-Goals

**Goals:**
- Add a stable observability snapshot API owned by the substrate.
- Expose a first slice that is additive, serializable, and policy-free.
- Keep public ownership boundaries explicit: `ConnectionNetwork` owns the snapshot, `PlantBackendSession` forwards it, and higher layers consume it.
- Cover the new contract with red-test-first substrate tests.

**Non-Goals:**
- Move pricing, inventory policy, tutorial progress, or ledger behavior into substrate code.
- Replace checkpoint persistence contracts with the new observability read model.
- Add history-heavy, mutable, or debugging-only payloads in the first slice.
- Solve the separate installed-asset/provenance inventory gap tracked under `ModularSimulator-9u6`.

## Decisions

1. **`ConnectionNetwork` owns the public observability snapshot.**
   - Add a new public method on `ConnectionNetwork` that returns a consumer-facing snapshot distinct from persistence payloads.
   - Rationale: the network already owns runtime stepping, graph revision, queue state, and runtime snapshot orchestration.
   - Alternative considered: exposing the snapshot directly from `System` or `ConnectedPlantOrchestrator`. Rejected because that would bypass the existing public owner surface and expose lower-level runtime internals as new public entry points.

2. **`PlantBackendSession` only forwards the substrate snapshot.**
   - Add one thin facade method that returns the network snapshot without adding gameplay vocabulary or economics rules.
   - Rationale: this matches the existing topology/checkpoint pattern and preserves substrate positioning.
   - Alternative considered: putting higher-level rollup logic in `PlantBackendSession`. Rejected because that would make the facade a policy owner.

3. **The first snapshot slice is small and stable.**
   - Freeze these top-level sections:
     - `schema`: versioned snapshot contract marker.
     - `graph_revision`: current topology revision or `null`.
     - `runtime`: `simulation_time_s`, `macro_step_index`, `macro_step_active`.
     - `queue`: `queued_request_ids`, `queued_request_count`, `committed_idempotency_keys`.
     - `observables`: policy-free readouts for `published_measurements` and `plant_calculation_outputs`.
   - Rationale: these fields already exist in owner-owned substrate state and are enough for higher layers to stop scraping internal objects.
   - Alternative considered: including point history, controller bindings, full transport state, or gameplay-level feed/product/utility heuristics in v1. Rejected because those are either too unstable, too heavy, or belong to later higher-layer composition.

4. **Published-measurement and plant-calculation data stay normalized numeric maps.**
   - Reuse existing subsystem publication normalization and collision checks already enforced by `ConnectedPlantOrchestrator`.
   - Expose copies of maps rather than live references.
   - Rationale: callers need stable numeric readouts, not mutable runtime containers.

5. **Persistence and observability remain separate contracts.**
   - `save_runtime_snapshot()` remains the checkpoint/replay surface.
   - The new observability snapshot is a separate read model with fewer fields and no checksum/replay semantics.
   - Rationale: consumer reads and replay persistence have different stability and validation needs.

## Risks / Trade-offs

- **Snapshot scope drifts into gameplay policy** → Mitigation: keep the contract limited to substrate-owned runtime state and numeric observables; reject economics/tutorial fields in this pack.
- **Live runtime structures leak through the API** → Mitigation: snapshot methods must return fresh mappings/tuples, never direct mutable registry objects.
- **Higher layers still need richer rollups later** → Mitigation: version the schema and keep the first slice additive so follow-on work can extend it without breaking consumers.
- **Confusion between checkpoint and observability snapshots** → Mitigation: use distinct method names, explicit schema markers, and tests that assert the consumer-facing shape is different from persistence payloads.

## Migration Plan

1. Add failing substrate tests that freeze the new network/session snapshot contract.
2. Implement the network-owned snapshot surface and session forwarding facade.
3. Verify the targeted substrate and integration matrix.
4. Update OpenSpec task state, create/close the corresponding Beads child issues, and then sync the settled capability into `openspec/specs/`.

## Open Questions

- None for this first slice; feed/product/utility rollups that require gameplay-owned semantics stay out of scope until a later change defines those contracts explicitly.

## Verification Strategy

- Red tests first for the new public snapshot contract.
- Required verification for this change:
  - `uv run pytest tests/cli/test_backend_session.py -k "topology or checkpoint or observability"`
  - `uv run pytest tests/connection/test_network_api.py -k "observability or snapshot"`
  - `uv run pytest tests/integration/test_dynamic_process_network_workflow.py`
- Expected evidence:
  - `ConnectionNetwork` exposes a stable consumer-facing observability snapshot distinct from checkpoint persistence.
  - `PlantBackendSession` forwards that snapshot without owning policy.
  - published subsystem measurements and plant-calculation outputs are available through a stable, serializable substrate read model.
