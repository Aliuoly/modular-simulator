# Phase 1: Failure Semantics & Acceptance Gates - Research

**Researched:** 2026-03-29
**Domain:** Connected-plant runtime failure semantics, acceptance gating, and transactional state publication
**Confidence:** MEDIUM

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** Phase 1 must classify four first-class failure families: stale hydraulic lag, inventory or physical-feasibility breaks, structural inconsistency, and solver masking or fake stability.
- **D-02:** Phase 1 evidence must cover four scenario classes: inventory-sensitive cases, delay-heavy cases, strongly coupled cases, and runtime-edit or restart cases.
- **D-03:** The accepted or rejected state boundary is the whole connected-plant macro-step, not only the `MacroCoupler` sequence, because subsystem process phases mutate unit state before connection runtime coupling runs.
- **D-04:** A candidate step is acceptable only when it yields one coupled plant snapshot for that macro-step; partially updated unit state and connection state must not be exposed as if the step succeeded.
- **D-05:** Under-specified, over-specified, and structurally inconsistent flowsheet states should be rejected through the existing compile and reconfiguration-barrier path before runtime stepping starts.
- **D-06:** Phase 1 needs an explicit plant-level physical acceptance layer because current guards are partial and some non-physical states can still be hidden behind observability clipping or local fallback behavior.
- **D-07:** Failure reproduction and classification should use the backend/runtime checkpoint seam plus macro-step bookkeeping rather than gameplay-side state, so evidence is deterministic and comparable across kernel directions.
- **D-08:** Rejection reasons should extend the repo's structured diagnostic-payload pattern into runtime-step failures; plain `RuntimeError` strings are not sufficient for acceptance-gate or benchmark disqualification decisions.

### the agent's Discretion
- Choose the exact data shape for Phase 1 failure taxonomy tables, as long as the four locked failure families and four locked scenario classes remain explicit.
- Choose whether Phase 1 evidence uses full snapshot rollback, staged candidate state, or another acceptance/publication pattern after the required external research on low-latency transactional state publication.

### Deferred Ideas (OUT OF SCOPE)
None — discussion stayed within phase scope.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| KERN-01 | Team can classify and reproduce the current split-kernel failure modes that create stale-coupling, non-physical inventory, or stale-pressure-driven flow on representative complex flowsheets. | Use checkpoint/replay seams, deterministic replay hashes, macro-step bookkeeping, and a scenario matrix that maps each fixture to one failure family and one scenario class. |
| KERN-02 | Team can validate whether a candidate kernel step produced one accepted coupled plant state rather than publishing partially updated unit and connection states. | Add an explicit macro-step acceptance transaction around `ConnectedPlantOrchestrator.step()` plus accepted-state publication buffering and rollback-on-reject semantics. |
| KERN-03 | Team can reject under-specified, over-specified, or structurally inconsistent flowsheet states before runtime stepping begins. | Reuse compile/barrier/invariant/hydraulic solvability paths and classify their failures as structural pre-step rejection, not runtime instability. |
| KERN-05 | Team can enforce physical feasibility guards that prevent accepted states with negative inventory, invalid composition normalization, or other non-physical plant states. | Add plant-level physical acceptance checks after candidate macro-step execution and before publication; use existing transport invariants plus new inventory/holdup guards. |
</phase_requirements>

## Project Constraints (from AGENTS.md)

- Use `bd` for task tracking.
- Prefer repo-local OpenCode agents (`hybrid-planner`, `hybrid-plan-reviewer`, `hybrid-orchestrator`, `hybrid-explore`, `hybrid-general-low`, `hybrid-general-high`, `hybrid-code-reviewer`).
- Intake is Beads-first; OpenSpec becomes the durable contract after scope stabilizes.
- Beads is the cross-change workflow tracker; OpenSpec `tasks.md` tracks implementation progress within the active change.
- Run all `bd --json` commands from project root `/home/alden/projects/ModularSimulator`.
- Do not use date-prefixed OpenSpec change names.
- Do not create `docs/superpowers/plans/*.md` as a second planning system.
- OpenSpec `tasks.md` must be execution-ready: concrete waves, exact files when known, explicit verification commands, clear TDD expectations.
- Changes affecting simulation behavior or physical realism must set `simulation-realism-required: true` in the task packet.
- Use real equation/correlation names where practical.
- If OpenSpec artifacts change during implementation, verify/sync/archive appropriately.
- Use `grepai` as primary code exploration/search tool; use `Grep`/`Glob` only for exact text/path matching.

## Summary

Phase 1 can be planned as a brownfield correctness layer on top of strong existing seams rather than as a kernel rewrite. The repo already has most of the substrate needed for deterministic failure evidence: barrier rollback for reconfiguration, checkpoint/save/restore contracts, deterministic replay hashes, process-runtime export/restore, transport-runtime persistence, and macro-step bookkeeping. The main gaps are semantic, not foundational: runtime-step failures are still reported too often as broad `RuntimeError`s, plant-level physical acceptance is incomplete, and the current macro-step mutates unit state in place before the connection runtime decides whether the step should count as accepted.

The planning-critical design choice is transactional publication. In this codebase, a full double-buffered clone of every process/runtime object is possible in theory but is too invasive for Phase 1 because unit models mutate in place, some carry cached derived views (`HoldingTank._rebuild_cached_state_views()`), and the runtime owns multiple mutable stores (port snapshots, transport history, junction states, idempotency metadata). The best Phase 1 fit is a hybrid: capture a pre-step rollback capsule using the existing checkpoint/process-state seams, execute the candidate macro-step in place, run structural + physical acceptance gates, publish one accepted snapshot on success, and restore on rejection. Use full snapshot capture as the correctness baseline and evidence mechanism first; optimize the rollback capsule only after instrumentation proves it is the latency bottleneck.

**Primary recommendation:** Plan Phase 1 around an explicit macro-step acceptance transaction with rollback-on-reject and accepted-state publication buffering; do **not** plan a repo-wide copy-on-write rewrite in this phase.

## Recommended Implementation Decomposition

### Wave 0: Test and fixture substrate
1. Add phase-specific test module(s) for failure taxonomy, structural rejection, physical acceptance, and accepted-state publication.
2. Build canonical replayable fixtures from checkpoint/runtime seams, not gameplay state.
3. Define the failure taxonomy table format and scenario matrix used across tests and docs.

### Wave 1: Structural rejection taxonomy
1. Normalize compile/barrier/invariant/hydraulic solvability failures into explicit structural rejection categories.
2. Ensure missing anchors, DOF mismatch, singular Jacobian, invalid mutation envelopes, and destructive-edit invariant failures are surfaced before runtime stepping.
3. Add tests proving these failures never proceed into process stepping / transport / boundary propagation.

### Wave 2: Runtime-step diagnostics and bookkeeping classification
1. Replace broad runtime-step `RuntimeError` strings around macro coupling with structured diagnostic payloads.
2. Extend bookkeeping/failure result objects so failures can be classified as stale hydraulic lag, physical-feasibility break, structural inconsistency, or solver masking/fake stability.
3. Persist enough evidence per rejected step to compare split-kernel and candidate-kernel behavior later.

### Wave 3: Macro-step acceptance transaction
1. Add a candidate macro-step wrapper at the whole connected-plant boundary (`ConnectedPlantOrchestrator.step`).
2. Capture a pre-step rollback capsule, execute in place, evaluate acceptance, restore on reject, and publish one accepted state on success.
3. Keep observability/publication distinct from checkpoint payloads.

### Wave 4: Plant-level physical acceptance
1. Add plant-wide post-step physical guards before accepted publication.
2. Start with inventory, composition normalization, finite values, and non-physical fallback/masking detection.
3. Add failure fixtures for inventory-sensitive, delay-heavy, strongly coupled, and runtime-edit/restart cases.

## Evidence / Artifact Strategy

Use one artifact bundle per canonical scenario:

| Artifact | Purpose | Existing seam |
|---------|---------|---------------|
| Pre-step checkpoint envelope | Deterministic reproduction baseline | `runtime_persistence.save_runtime_snapshot_contract()` |
| Replay hashes at selected ticks | Detect drift or non-deterministic classification | `runtime_persistence.runtime_replay_state_hash()` |
| Macro-step bookkeeping | Detect fallback use, Picard activity, residuals, sequence | `connection_layer.MacroStepBookkeeping` |
| Structured rejection payload | Machine-readable failure family + reason | `connection.domain.error_catalog` pattern |
| Accepted observability snapshot | Prove only accepted state becomes public | `ConnectionNetwork.get_observability_snapshot()` |
| Scenario manifest row | Maps fixture to failure family + scenario class + expected gate | New Phase 1 fixture metadata |

Recommended scenario matrix minimum:

| Scenario Class | Must exercise | Primary failure family target |
|---------------|---------------|-------------------------------|
| Inventory-sensitive | holding tank / depletion / conservation edge cases | inventory or physical-feasibility breaks |
| Delay-heavy | lag transport and near-zero fallback behavior | stale hydraulic lag; solver masking/fake stability |
| Strongly coupled | recycle / feedback / pressure-flow sensitivity | stale hydraulic lag; solver masking/fake stability |
| Runtime-edit / restart | queued reconfiguration + checkpoint resume | structural inconsistency; physical-feasibility breaks |

## Transactional State Publication Options

| Option | Fit to this repo | Latency outlook | Planning verdict |
|-------|-------------------|-----------------|------------------|
| Full snapshot rollback every macro-step | HIGH fit: existing save/restore, process-state export/restore, transport and port snapshot seams already exist | Worst steady-state cost because capture/normalize/restore touches broad state each step | Use as Phase 1 correctness baseline and rejection mechanism; do not assume it is the final optimized runtime path |
| Full staged candidate state / double-buffered clone of runtime and unit models | LOW-MEDIUM fit: unit models mutate in place and some require cache rebuilds after restore/dimension changes | Potentially good after heavy refactor, but expensive to build now | Do not plan this in Phase 1 |
| Hybrid optimistic execute + rollback-on-reject + accepted-state publication buffer | HIGH fit: small semantic change over current runtime, preserves current ownership boundaries | Good if rejected steps are rare; only failed steps pay restore cost | **Recommended Phase 1 approach** |
| Deepcopy arbitrary runtime/process objects | LOW fit: brittle with cached views, bindings, runtime-owned stores, and hidden mutable references | Unpredictable, often slow | Avoid |
| Compensating write / manual undo log | LOW-MEDIUM fit: would require enumerating every unit/runtime mutation path | Fast if perfect, but fragile and easy to under-cover | Avoid in Phase 1 |

### Recommended publication pattern

Use a **macro-step acceptance transaction** with two layers:

1. **Rollback capsule (correctness):** capture pre-step runtime/process/transport/queue state before a candidate macro-step.
2. **Accepted publication buffer (visibility):** expose public observability only from the last accepted state until the candidate passes acceptance gates.

This gives Phase 1 the semantics it needs without demanding a whole-repo state clone architecture. It also cleanly supports later benchmark comparisons because the same acceptance gate can be applied to split and candidate kernels.

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python | 3.13.x (docs queried at 3.13.9) | Required runtime for the repo | `pyproject.toml` requires `>=3.13,<3.14`; stdlib `copy` docs are current for clone/rollback tradeoff analysis |
| pytest | 9.0.2 | Phase 1 test and fixture execution | Standard Python test runner already configured in `pyproject.toml`; supports precise node-id test selection |
| pydantic | 2.12.5 | Structured runtime/checkpoint/diagnostic schemas | Already used in runtime snapshot schema; v2 validators fit acceptance payload validation cleanly |
| scipy | 1.17.1 | Current baseline solver substrate in the repo | Existing brownfield dependency; Phase 1 classifies current behavior rather than replacing it |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| thermo | 0.6.0 | Existing thermodynamic helper dependency | Reuse only if a physical guard needs current thermodynamic metadata |
| chemicals | 1.5.1 | Existing thermodynamic/property helper dependency | Same as above; do not add new property-stack work unless required by a guard |
| Python `copy` stdlib | 3.13.9 docs | Evaluate deep-copy tradeoffs for candidate-state mechanisms | For analysis and narrowly-scoped copies only; not as the primary transaction mechanism |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Existing snapshot/restore seams | `copy.deepcopy()` across runtime/unit objects | Simpler-looking but brittle with cached views, hidden mutable references, and runtime-owned stores |
| Hybrid rollback-on-reject | Full double-buffer / copy-on-write state graph | Better long-term isolation, but too invasive for Phase 1 brownfield scope |
| Structured diagnostic payloads | Ad hoc `RuntimeError` strings | Faster to type, but unusable for classification, benchmarking, and automated acceptance decisions |

**Installation:**
```bash
pip3 install -e . pytest
```

**Version verification:** Verified on 2026-03-29 against package registries/docs.
- `pytest` 9.0.2 — published 2025-12-06
- `pydantic` 2.12.5 — published 2025-11-26
- `scipy` 1.17.1 — published 2026-02-23
- `thermo` 0.6.0 — published 2025-10-26
- `chemicals` 1.5.1 — published 2026-02-09

## Architecture Patterns

### Recommended Project Structure
```text
src/modular_simulation/connection/
├── domain/                  # diagnostic payloads, invariants, structural rejection
├── runtime/                 # macro-step transaction, rollback capsule, acceptance gates
├── topology/                # network facade and observability publication surface
└── hydraulics/              # compile-time solvability and structure validation

tests/
├── connection/              # extend current orchestrator/runtime persistence tests
├── persistence/             # deterministic replay and checkpoint tests
└── phase1/                  # new failure taxonomy and acceptance-gate fixtures
```

### Pattern 1: Whole-plant macro-step acceptance transaction
**What:** Treat `ConnectedPlantOrchestrator.step()` as the candidate-step boundary, capture a rollback capsule before unit process stepping, and decide accept/reject only after runtime coupling and plant-level physical validation finish.

**When to use:** Every candidate macro-step for current split-kernel and future kernel-comparison paths.

**Example:**
```python
# Source: repo - src/modular_simulation/connection/runtime/connected_plant_orchestrator.py
pre_step = capture_runtime_checkpoint(...)
try:
    candidate = orchestrator.step(macro_step_time_s=dt)
    acceptance = validate_candidate_step(candidate, bookkeeping, physical_guards)
    if not acceptance.accepted:
        restore_runtime_checkpoint(pre_step)
        return rejection_payload
    publish_accepted_snapshot(candidate)
    return accepted_payload
except Exception as exc:
    restore_runtime_checkpoint(pre_step)
    raise translate_runtime_failure(exc)
```

### Pattern 2: Deterministic failure reproduction via checkpoint + replay hash
**What:** Use runtime checkpoint envelopes and replay hashes as the canonical evidence path.

**When to use:** Fixture creation, regression tests, and future split-vs-candidate kernel comparison.

**Example:**
```python
# Source: repo - src/modular_simulation/connection/runtime/runtime_persistence.py
checkpoint = save_runtime_snapshot_contract(
    runtime=runtime,
    network=network,
    process_runtime_state=process_runtime_state,
)
hash_before = runtime_replay_state_hash(
    tick=tick,
    runtime=runtime,
    network=network,
    process_runtime_state=process_runtime_state,
)
```

### Pattern 3: Structured runtime diagnostics
**What:** Wrap runtime-step failures in the same structured payload pattern already used for barrier/validation failures.

**When to use:** Any acceptance-gate rejection, runtime coupling failure, or benchmark disqualification reason.

**Example:**
```python
# Source: repo - src/modular_simulation/connection/domain/error_catalog.py
from modular_simulation.connection.domain.error_catalog import diagnostic_runtime_error

raise diagnostic_runtime_error(
    code="PHYSICAL_ACCEPTANCE_FAILURE",
    message="candidate macro-step produced negative holdup_total_mol",
    path="process_state_values.tank_a/holdup_total_mol",
    hint="restore the last accepted state and inspect pre-step inventory",
)
```

### Likely Phase 1 file touch points
- `src/modular_simulation/connection/runtime/connected_plant_orchestrator.py` — whole-plant macro-step boundary; process-state export/restore; observability clipping seam.
- `src/modular_simulation/connection/runtime/runtime.py` — barrier apply, runtime step, transport/junction state, observability state, snapshot save/resume.
- `src/modular_simulation/connection/runtime/runtime_persistence.py` — checkpoint envelope, rollback-safe restore, replay hashes.
- `src/modular_simulation/connection/runtime/connection_layer.py` — macro-step bookkeeping and current broad runtime errors.
- `src/modular_simulation/connection/domain/error_catalog.py` — structured failure payload pattern to extend.
- `src/modular_simulation/connection/domain/invariant_validator.py` — destructive edit and structural pre-step rejection.
- `src/modular_simulation/connection/hydraulics/hydraulic_solver.py` — structural solvability failures (missing pressure reference, DOF mismatch, singular Jacobian).
- `src/modular_simulation/connection/topology/network.py` — public observability snapshot and runtime snapshot facade.
- `tests/connection/test_connected_plant_orchestrator.py` — macro-step ordering and queue semantics.
- `tests/connection/test_runtime_persistence_contract.py` and `tests/persistence/test_checkpoint_journal_replay_determinism.py` — restore atomicity, replay determinism, checkpoint contract behavior.

### Anti-Patterns to Avoid
- **Publishing from live mutable state during candidate execution:** `get_observability_snapshot()` should not become proof of acceptance while the candidate macro-step is still mutable.
- **Treating structural solve errors as runtime instability:** missing anchors, DOF mismatch, and singular Jacobian should reject before runtime stepping.
- **Using clipped observability as physical truth:** holding-tank observability clips negative/near-empty values for continuity; that is not an acceptance proof.
- **Deep-copying arbitrary process graphs:** cache-heavy process models make this brittle.
- **Benchmarking against smoke demos:** current benchmark examples are deterministic smoke placeholders, not Phase 1 evidence fixtures.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Rollback capsule | Ad hoc object graph cloning | Existing runtime snapshot + process-state export/restore seams | Already covers queue/order/runtime/transport/process state and has rollback-safe tests |
| Runtime-step error taxonomy | Free-form string parsing | `error_catalog` diagnostic payload pattern | Classification and benchmark disqualification need machine-readable payloads |
| Structural pre-step validation | New parallel validator stack | Existing barrier/invariant/hydraulic compile validation | The repo already rejects many structural failures correctly; Phase 1 should classify and route them |
| Replay evidence | Gameplay-side mirrors or UI logs | `runtime_replay_state_hash()` + checkpoint contract | Deterministic and kernel-direction agnostic |
| Physical guard schemas | Untyped dict checks spread everywhere | Pydantic-style validated envelopes/payloads | Keeps rejection reasons consistent and testable |

**Key insight:** the repo already has the hard parts for reproducibility and rollback; Phase 1 should compose them into an explicit acceptance gate instead of inventing a new state-management subsystem.

## Common Pitfalls

### Pitfall 1: Mistaking observability continuity for physical validity
**What goes wrong:** A tank near-empty or clipped observability value looks stable even though the underlying plant state should be rejected.
**Why it happens:** `ConnectedPlantOrchestrator._snapshot_holding_tank_process_state_values()` clips holdup/components for continuity, and the observability spec explicitly allows clipped near-zero values.
**How to avoid:** Run physical acceptance against runtime/process state before observability projection, not against `observables.process_state_values` alone.
**Warning signs:** Accepted steps with zero-ish public holdup while internal state needed clipping or fallback.

### Pitfall 2: Classifying structural solver failures as runtime instability
**What goes wrong:** Missing pressure references, DOF mismatch, or singular Jacobian get mixed into generic runtime failure buckets.
**Why it happens:** The runtime path currently wraps coupling failures broadly, while hydraulic solvability already provides explicit structural messages.
**How to avoid:** Route compile/barrier/hydraulic-solvability failures into a structural rejection family before `ConnectedPlantOrchestrator.step()` begins process stepping.
**Warning signs:** Transport/boundary steps never ran, but the failure is reported as a generic macro-step runtime error.

### Pitfall 3: Hidden partial success on rejected macro-steps
**What goes wrong:** Unit process state mutates during subsystem process stepping even when the connection/runtime portion later fails.
**Why it happens:** The whole-plant macro-step is wider than `MacroCoupler`; current code mutates in place before acceptance is known.
**How to avoid:** Capture pre-step rollback state and restore on any rejection; expose public accepted state from a separate publication buffer.
**Warning signs:** Re-running the same fixture after a rejection gives different results unless the runtime is reloaded.

### Pitfall 4: Deep copy breaks hidden caches
**What goes wrong:** Restored or copied unit state has correct arrays but stale cached views.
**Why it happens:** Some process models, notably `HoldingTank`, rebuild cached state views when array dimensions change.
**How to avoid:** Prefer explicit export/restore seams already aware of these cases; if any scoped copy is used, prove cache rebuild behavior in tests.
**Warning signs:** Shape mismatch or stale derived-view failures after restore/resume.

### Pitfall 5: Replay evidence is invalidated by queue-order drift
**What goes wrong:** A scenario appears “different” because queued reconfiguration order changed, not because kernel behavior changed.
**Why it happens:** Replay hash includes queued requests and ordering by design.
**How to avoid:** Freeze queue order as part of fixture setup and compare hashes at selected ticks.
**Warning signs:** Hash mismatch at restart/edit cases with identical physics inputs but different request ordering.

## Code Examples

Verified patterns from official sources:

### Specific pytest node-id execution
```bash
# Source: Context7 /pytest-dev/pytest (usage.md)
python3 -m pytest tests/connection/test_runtime_persistence_contract.py::test_restore_requires_barrier_inactive_and_is_atomic_when_process_validation_fails -q
```

### Pydantic v2 model-level invariant validation
```python
# Source: Context7 /pydantic/pydantic
from typing_extensions import Self
from pydantic import BaseModel, model_validator

class CandidateAcceptance(BaseModel):
    accepted: bool
    rejection_code: str | None = None

    @model_validator(mode="after")
    def validate_consistency(self) -> Self:
        if self.accepted and self.rejection_code is not None:
            raise ValueError("accepted candidate cannot carry a rejection_code")
        if not self.accepted and self.rejection_code is None:
            raise ValueError("rejected candidate must carry a rejection_code")
        return self
```

### Repo pattern for stable checkpoint save/restore
```python
# Source: repo - src/modular_simulation/connection/runtime/runtime_persistence.py
snapshot = save_runtime_snapshot_contract(
    runtime=runtime,
    network=network,
    process_runtime_state=process_runtime_state,
)

restore_runtime_snapshot_contract(
    runtime=runtime,
    network=network,
    process_runtime_state_sink=process_runtime_state,
    snapshot=snapshot,
)
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Broad runtime failure strings | Structured diagnostic payloads in barrier/validation paths | Already present in current repo | Phase 1 should extend the same pattern into runtime-step failures |
| Directly reading mutable state during updates | Double-buffer / accepted-publication pattern | Established pattern; external source reviewed 2026-03-29 | Best mental model for “one accepted snapshot” semantics |
| Manual resume intuition | Validated checkpoint envelopes + replay hashes | Already present in current repo | Gives Phase 1 deterministic evidence instead of narrative debugging |

**Deprecated/outdated:**
- Plain `RuntimeError` classification for macro-step failures — too weak for acceptance gates.
- Using `observability.process_state_values` alone as physical-feasibility evidence — can be masked by clipping/continuity rules.
- Treating `examples/connection_layer/benchmarks/macro_coupling_benchmark.py` as benchmark evidence — it is deterministic smoke scaffolding only.

## Open Questions

1. **How small can the rollback capsule become before correctness risk rises?**
   - What we know: the full contract already preserves runtime, queue, transport, port-condition, and process state atomically.
   - What's unclear: whether a lighter in-memory capsule can omit any of these for accepted-step rollback without missing a failure mode.
   - Recommendation: start Phase 1 with the full capsule as the oracle; only trim after profiling and after failure fixtures are green.

2. **Should accepted-state publication buffer only observability, or also other runtime readers?**
   - What we know: public observability is already a distinct read model, and snapshots are forbidden mid-step.
   - What's unclear: whether any non-observability consumers read mutable runtime state directly during stepping.
   - Recommendation: audit call sites before scoping implementation; at minimum, isolate observability publication in Phase 1.

3. **Which four concrete fixtures should become canonical Phase 1 scenarios?**
   - What we know: the required classes are inventory-sensitive, delay-heavy, strongly coupled, and runtime-edit/restart.
   - What's unclear: which existing examples/tests are realistic enough versus needing new fixtures.
   - Recommendation: choose one minimal deterministic fixture per scenario class first, then add stress variants only if a family is still under-covered.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.13 | Project runtime and Phase 1 test execution | ✗ | 3.12.3 installed | None |
| pytest | Validation architecture / test execution | ✗ | — | None |
| pip3 | Installing project and test dependencies | ✓ | 24.0 | — |

**Missing dependencies with no fallback:**
- Python 3.13 runtime matching `pyproject.toml` (`>=3.13,<3.14`)
- `pytest` in the active interpreter environment

**Missing dependencies with fallback:**
- None

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.0.2 target (configured in `pyproject.toml`, not installed in current environment) |
| Config file | `pyproject.toml` (`[tool.pytest.ini_options]`) |
| Quick run command | `python3 -m pytest tests/connection/test_runtime_persistence_contract.py -q` |
| Full suite command | `python3 -m pytest tests/connection tests/persistence tests/integration -q` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| KERN-01 | Failure families are reproducible and classified across canonical fixtures | integration/contract | `python3 -m pytest tests/phase1/test_failure_taxonomy.py -q` | ❌ Wave 0 |
| KERN-02 | Rejected macro-step never publishes partial success; accepted step publishes one snapshot | integration | `python3 -m pytest tests/phase1/test_macro_step_acceptance.py -q` | ❌ Wave 0 |
| KERN-03 | Structural inconsistency rejects before runtime stepping starts | unit/integration | `python3 -m pytest tests/phase1/test_structural_rejection.py -q` | ❌ Wave 0 |
| KERN-05 | Physical-feasibility guards reject negative inventory / invalid composition / masked fake stability | integration | `python3 -m pytest tests/phase1/test_physical_acceptance.py -q` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `python3 -m pytest tests/phase1/test_macro_step_acceptance.py -q`
- **Per wave merge:** `python3 -m pytest tests/connection tests/persistence tests/phase1 -q`
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `tests/phase1/test_failure_taxonomy.py` — canonical scenario matrix and family classification
- [ ] `tests/phase1/test_macro_step_acceptance.py` — one accepted snapshot / rollback-on-reject semantics
- [ ] `tests/phase1/test_structural_rejection.py` — compile/barrier/hydraulic structural failure routing
- [ ] `tests/phase1/test_physical_acceptance.py` — plant-level physical rejection guards
- [ ] Python 3.13 environment — current machine is on Python 3.12.3
- [ ] Framework install: `pip3 install -e . pytest`

## Sources

### Primary (HIGH confidence)
- `/pytest-dev/pytest` - specific test selection / node-id execution
- `/pydantic/pydantic` - `field_validator` and `model_validator` patterns for validated acceptance payloads
- `/python/cpython/v3.13.9` - stdlib copy/deepcopy caveats around mutable nested state
- Repo source: `src/modular_simulation/connection/runtime/runtime_persistence.py` - checkpoint contract, rollback safety, replay hashes
- Repo source: `src/modular_simulation/connection/runtime/runtime.py` - runtime step boundary, observability state, transport/junction state, mutation barrier
- Repo source: `src/modular_simulation/connection/runtime/connected_plant_orchestrator.py` - whole-plant macro-step boundary and process-state export/restore
- Repo source: `src/modular_simulation/connection/hydraulics/hydraulic_solver.py` - structural solvability failures

### Secondary (MEDIUM confidence)
- `https://gameprogrammingpatterns.com/double-buffer.html` - authoritative pattern reference for atomic publication / double buffering mental model
- Repo tests: `tests/connection/test_runtime_persistence_contract.py` - atomic restore and transport/process-state restore behavior
- Repo tests: `tests/persistence/test_checkpoint_journal_replay_determinism.py` - deterministic replay evidence

### Tertiary (LOW confidence)
- Exa search results on simulation-state publication patterns were useful for terminology, but not strong enough to drive the recommendation directly without repo-fit validation.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - versions verified from package registries and aligned with repo usage
- Architecture: MEDIUM - strong repo evidence for seams, but final latency tradeoff depends on profiling in Python 3.13 environment
- Pitfalls: HIGH - directly grounded in current code paths, specs, and tests

**Research date:** 2026-03-29
**Valid until:** 2026-04-28
