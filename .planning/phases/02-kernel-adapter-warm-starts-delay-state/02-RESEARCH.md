# Phase 2: Kernel Adapter, Warm Starts & Delay State - Research

**Researched:** 2026-03-29
**Domain:** Solver-kernel adapter seams, canonical warm-start restore, and explicit delay-state treatment
**Confidence:** MEDIUM

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** Define one full shared candidate-kernel contract up front: state, residual, Jacobian, bounds, initialization, warm start, and telemetry all belong to the same seam.
- **D-02:** Wrap the current split runtime fully as one adapter implementation so the baseline and future candidates are compared through the same contract.
- **D-03:** Comparable telemetry is mandatory in the adapter contract from the start.
- **D-04:** Be substrate-first by default; keep work behind substrate/runtime boundaries unless widening higher-layer contracts is clearly justified.
- **D-05:** Higher-layer session or API changes are allowed when they materially improve adapter integration.
- **D-06:** Checkpoint-style accepted snapshots are the one canonical restore mechanism underneath resume, save/load, and post-edit recovery paths.
- **D-07:** Warm starts must use the accepted coupled plant snapshot as the authoritative source, not helper caches or gameplay-owned state.
- **D-08:** Unsafe restore paths must fail explicitly with a clear reason; no silent cold-start fallback or lossy repair.
- **D-09:** Candidate kernels may choose their own delay/deadtime treatment in Phase 2.
- **D-10:** Any candidate that replaces current transport history must document the mapping from current delay state to its own representation and define safe restore behavior.
- **D-11:** Delay semantics remain open for exploration in Phase 2; consistency with today's runtime is preferred only when justified by later evidence.

### the agent's Discretion
- Choose whether the seam is expressed as protocols, dataclasses, typed dicts, or another typed Python contract, as long as D-01 stays explicit.
- Keep higher-layer widening minimal and generic when it is needed.
- Choose the concrete artifact shape used to document candidate-specific delay mapping and restore semantics.

### Deferred Ideas (OUT OF SCOPE)
None — discussion stayed within phase scope.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| KERN-04 | Team can initialize and warm-start candidate kernels from the last accepted plant state, checkpoint restore, or post-edit recovery path. | Treat the accepted checkpoint envelope as the canonical warm-start artifact and add adapter-owned restore helpers that always fail explicitly on incompatibility. |
| SOLV-02 | Team can expose a solver-kernel adapter seam with state, residual, Jacobian, bounds, initialization, warm-start, and telemetry interfaces. | Create one typed adapter contract plus a wrapped split-runtime baseline implementation before any candidate-specific comparison work. |
| DELY-01 | Team can preserve or explicitly replace existing transport-lag behavior when evaluating kernel directions. | Make delay treatment first-class adapter metadata; the split baseline should declare that it preserves external transport-history lag behavior. |
| DELY-02 | Team can define how deadtime is represented in each candidate kernel direction. | Require every adapter to publish delay semantics metadata (for example `external_transport_history`, `augmented_state`, or `hybrid`). |
| DELY-03 | Team can restore and safely update deadtime or transport-history state across checkpoint reloads, warm starts, and runtime edits. | Reuse existing transport snapshot round-trip seams, but expose them through adapter-neutral delay-state capture/restore helpers and regression tests. |
</phase_requirements>

## Summary

Phase 2 should be planned as a substrate refactor that adds a candidate-kernel seam without replacing the current runtime/session facades first. The repo already has most of the hard restore machinery: `ConnectionNetwork.save_runtime_snapshot()` and `resume_from_snapshot()`, rollback-safe checkpoint restore in `runtime_persistence.py`, process-runtime export/restore in `ConnectedPlantOrchestrator`, transport-history export/restore in `ConnectionRuntimeOrchestrator`, and stable `PlantBackendSession.save_checkpoint()` / `load_checkpoint()` entry points.

The planning-critical move is to unify these existing seams behind one adapter contract instead of inventing a new solver stack immediately. The current split runtime can be wrapped as the baseline adapter now, exposing explicit telemetry from `ConnectionRuntimeStepResult` and `MacroStepBookkeeping`, while warm starts stay anchored on accepted checkpoint snapshots. Delay semantics should be explicit adapter-owned metadata plus adapter-owned delay-state capture/restore methods, not an implicit assumption that every candidate uses the current external transport-history model.

**Primary recommendation:** Plan Phase 2 around (1) a typed adapter contract, (2) a fully wrapped split-runtime baseline adapter, (3) canonical checkpoint-based warm-start helpers, and (4) explicit delay semantics metadata + delay-state round-trip tests.

## Recommended Implementation Decomposition

### Wave 0: Contracts and baseline seam
1. Add one shared adapter contract covering state, residual, Jacobian, bounds, initialization, warm start, telemetry, and delay semantics.
2. Wrap the current split runtime as the first adapter implementation.
3. Add contract tests proving the baseline adapter can be instantiated and emits the required telemetry and delay metadata.

### Wave 1: Canonical warm-start restore
1. Add adapter-owned restore request/result helpers that accept checkpoint-style accepted snapshots.
2. Route save/load, resume, and post-edit recovery through the same canonical restore mechanism under the substrate.
3. Fail explicitly on incompatible snapshots or unsupported restore paths.

### Wave 2: Delay-state mapping and regression coverage
1. Expose adapter-neutral delay-state capture/restore helpers.
2. Map the split baseline to existing `transport_runtime_state` rather than renaming public runtime payloads prematurely.
3. Add regression coverage for live snapshot resume, checkpoint restore, and runtime-edit recovery after delay-state restore.

## Standard Stack

### Core
| Library | Purpose | Why Standard |
|---------|---------|--------------|
| Python 3.13 | Typed adapter/dataclass/protocol surface | Required by `pyproject.toml` and current repo conventions. |
| pytest | Contract and restore regression coverage | Already the project test runner. |
| pydantic | Snapshot/restore schema validation | Already used by `runtime_snapshot_schema.py`; good fit for explicit restore payload checks. |
| SciPy | Baseline solver substrate | Existing solver baseline; the adapter must accommodate residual/Jacobian/bounds hooks used by SciPy-style solve flows. |

### External References Reviewed
- SciPy `optimize.newton_krylov` and `optimize.minimize` docs confirm a practical callback surface for residual, Jacobian/Hessian-adjacent information, bounds, and solver telemetry collection.
- PyBaMM's SciPy solver wrapper reinforces the pattern of passing Jacobian callbacks and solver options through a narrow adapter rather than scattering solver-specific logic through the domain model.

## Architecture Patterns

### Pattern 1: Typed candidate-kernel adapter seam
**What:** One protocol/dataclass surface for candidate kernels, including initialization, step inputs, warm-start restore, telemetry, and delay semantics metadata.

**Repo fit:** High. The codebase already uses typed seams and protocols in `runtime.py`, `connection_layer.py`, and subsystem descriptors.

### Pattern 2: Canonical checkpoint-based warm start
**What:** Restore candidates from an accepted snapshot envelope instead of gameplay mirrors or ad hoc caches.

**Repo fit:** High. `PlantBackendSession.save_checkpoint()`, `ConnectionNetwork.save_runtime_snapshot()`, `runtime_persistence.save_runtime_snapshot_contract()`, and `ConnectedPlantOrchestrator.restore_process_runtime_state()` already establish this direction.

### Pattern 3: Delay semantics as metadata + state bundle
**What:** Every adapter declares how it represents delay/deadtime and provides delay-state capture/restore helpers.

**Repo fit:** High. The split runtime already owns `transport_runtime_state`; future candidates can expose augmented-state or hybrid delay bundles without breaking higher-layer save/load APIs.

## Recommended Project Structure

```text
src/modular_simulation/connection/
├── kernel_adapter.py                     # shared adapter contracts
├── runtime/
│   ├── split_kernel_adapter.py           # wrapped current split runtime baseline
│   └── kernel_adapter_restore.py         # canonical warm-start helpers
└── topology/network.py                   # existing snapshot/resume facade consumers

tests/connection/
├── test_kernel_adapter_contract.py
├── test_kernel_adapter_restore.py
├── test_split_kernel_delay_mapping.py
└── test_runtime_persistence_contract.py  # extend existing round-trip coverage

docs/
└── kernel_adapter_delay_semantics.md
```

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Warm-start source of truth | Gameplay/session mirrors | Existing accepted snapshot + checkpoint seams | D-06 and D-07 explicitly reject mirror-driven reconstruction. |
| Delay-state persistence | New parallel transport persistence system | Existing `transport_runtime_state` export/restore as the split baseline mapping | The repo already has tested round-trip behavior. |
| Solver telemetry | Candidate-specific ad hoc dicts | Shared adapter telemetry record keyed off `ConnectionRuntimeStepResult` and `MacroStepBookkeeping` | D-03 requires comparable telemetry from the start. |
| Public-facing restore API rewrite | New user-visible save/load concepts | Keep `save_checkpoint()` / `load_checkpoint()` stable and route internally through adapter helpers | Preserves current facades per D-04. |

## Common Pitfalls

### Pitfall 1: Making the adapter too small
If state/residual/Jacobian/bounds/warm-start/telemetry are split across unrelated helper objects, future candidate comparison becomes unfair and D-01 is violated.

### Pitfall 2: Smuggling gameplay state into warm starts
Restore paths built from gameplay/session caches will drift from the accepted coupled plant snapshot and violate D-06/D-07.

### Pitfall 3: Silent cold-start fallback
A restore helper that quietly reinitializes when state is incompatible makes benchmark and kernel-comparison results untrustworthy. Fail explicitly per D-08.

### Pitfall 4: Treating transport history as an implementation detail
Delay semantics are a milestone concern, not an internal detail. If the split baseline preserves transport history, that should be declared explicitly and tested.

### Pitfall 5: Renaming public snapshot payloads too early
The repo already uses `transport_runtime_state` in snapshot contracts. Phase 2 should wrap and document that as the split baseline delay bundle first; large schema migrations can wait for evidence that a new name is necessary.

## Likely File Touch Points

- `src/modular_simulation/connection/runtime/runtime.py` — existing protocol seams, telemetry source, and transport-history export/restore.
- `src/modular_simulation/connection/runtime/connection_layer.py` — `MacroStepBookkeeping` fields to surface through shared adapter telemetry.
- `src/modular_simulation/connection/runtime/connected_plant_orchestrator.py` — process-runtime export/restore used by canonical warm starts.
- `src/modular_simulation/connection/topology/network.py` — live snapshot save/resume facade likely to call adapter-aware helpers.
- `src/modular_simulation/cli/backend_session.py` — stable save/load substrate surface that should remain the public story.
- `tests/connection/test_runtime_persistence_contract.py` — existing restore/transport-history round-trip tests to extend.
- `tests/connection/test_connected_plant_orchestrator.py` — orchestrator integration patterns for adapter-driven work.

## Open Questions

1. **Should the contract expose full dense Jacobians only, or allow sparse / operator-style Jacobian hints?**
   - Recommendation: plan for an abstract Jacobian provider surface, not a dense `ndarray` requirement.

2. **Do any higher-layer resume/edit paths bypass checkpoint helpers today?**
   - Recommendation: audit during implementation and route those paths to the canonical adapter restore helper if they do.

3. **Should candidate delay semantics live only in docs, or also in machine-readable metadata?**
   - Recommendation: require both. Docs for humans, typed metadata for tests and later benchmark harnesses.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest via `uv run python -m pytest` |
| Config file | `pyproject.toml` |
| Quick run command | `uv run python -m pytest tests/connection/test_kernel_adapter_contract.py -q` |
| Full suite command | `uv run python -m pytest tests/connection/test_kernel_adapter_contract.py tests/connection/test_kernel_adapter_restore.py tests/connection/test_split_kernel_delay_mapping.py tests/connection/test_runtime_persistence_contract.py -q` |
| Estimated runtime | ~35 seconds |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| SOLV-02 | Shared adapter seam covers state/residual/Jacobian/bounds/init/warm-start/telemetry | contract | `uv run python -m pytest tests/connection/test_kernel_adapter_contract.py -q` | ❌ Wave 0 |
| KERN-04 | Warm starts restore from accepted snapshots and fail explicitly when unsafe | integration | `uv run python -m pytest tests/connection/test_kernel_adapter_restore.py -q` | ❌ Wave 0 |
| DELY-01 | Split baseline preserves current transport-lag treatment and exposes it explicitly | regression | `uv run python -m pytest tests/connection/test_split_kernel_delay_mapping.py -q` | ❌ Wave 0 |
| DELY-02 | Candidate delay representation is machine-readable | contract | `uv run python -m pytest tests/connection/test_kernel_adapter_contract.py -q` | ❌ Wave 0 |
| DELY-03 | Delay state round-trips across snapshot resume, checkpoint restore, and edit recovery | integration/regression | `uv run python -m pytest tests/connection/test_split_kernel_delay_mapping.py tests/connection/test_runtime_persistence_contract.py -q` | ✅ partial / ❌ new coverage |

### Sampling Rate
- **Per task commit:** `uv run python -m pytest tests/connection/test_kernel_adapter_contract.py -q`
- **Per wave merge:** `uv run python -m pytest tests/connection/test_kernel_adapter_contract.py tests/connection/test_kernel_adapter_restore.py tests/connection/test_split_kernel_delay_mapping.py tests/connection/test_runtime_persistence_contract.py -q`
- **Phase gate:** full targeted suite green before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `tests/connection/test_kernel_adapter_contract.py`
- [ ] `tests/connection/test_kernel_adapter_restore.py`
- [ ] `tests/connection/test_split_kernel_delay_mapping.py`
- [ ] Shared adapter contract file `src/modular_simulation/connection/kernel_adapter.py`

## Sources

### Primary
- Repo source: `src/modular_simulation/connection/runtime/runtime.py`
- Repo source: `src/modular_simulation/connection/runtime/connection_layer.py`
- Repo source: `src/modular_simulation/connection/runtime/connected_plant_orchestrator.py`
- Repo source: `src/modular_simulation/connection/runtime/runtime_persistence.py`
- Repo source: `src/modular_simulation/connection/runtime/runtime_snapshot_schema.py`
- Repo source: `src/modular_simulation/connection/topology/network.py`
- Repo tests: `tests/connection/test_runtime_persistence_contract.py`
- Repo tests: `tests/connection/test_connected_plant_orchestrator.py`

### Secondary
- SciPy `newton_krylov` documentation
- SciPy `minimize` documentation
- PyBaMM SciPy solver wrapper source docs

## Metadata

**Confidence breakdown:**
- Contract recommendation: HIGH
- Warm-start unification: HIGH
- Delay-state future-proofing shape: MEDIUM
- Exact file decomposition: MEDIUM

**Research date:** 2026-03-29
**Valid until:** 2026-04-28
