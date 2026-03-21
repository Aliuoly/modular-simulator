# Downstream Hydraulic Epic Superpowers Planning Design

## Goal

Replace the remaining downstream OpenSpec execution packs for the active hydraulic canonicalization epic with Superpowers-native implementation plans, without disturbing the already in-progress `ModularSimulator-szt.2` session.

## Scope

In scope:
- `ModularSimulator-szt.3` — `Implement reject-invalid-recycle-loops`
- `ModularSimulator-szt.4` — `Finalize curated examples and end-to-end regressions`

Out of scope:
- `ModularSimulator-szt.2` implementation work already in progress elsewhere
- `ModularSimulator-m3a` follow-up contract design task
- direct code changes in this planning session

## Recommended Approach

Create two separate Superpowers plans:

1. a focused implementation plan for `ModularSimulator-szt.3`
2. a follow-on integration/finalization plan for `ModularSimulator-szt.4`

This keeps the blocked work (`szt.3`) separate from the later regression/doc sweep (`szt.4`), preserves the epic dependency chain, and gives future low-context execution agents a clear start/stop boundary for each task.

## Why Separate Plans

- `szt.3` is a compile-time validation feature with its own code, diagnostics, and targeted regression surface.
- `szt.4` is primarily a post-landing consolidation task spanning curated examples, public guidance, and end-to-end verification.
- Combining them would blur completion gates and make it easier for an execution agent to start finalization before the public API from `szt.2` and recycle validation from `szt.3` are both available.

## Plan Structure

Both plan documents will follow the Superpowers implementation-plan format and include:

- explicit goal, architecture, and tech-stack header
- exact file paths grouped by create/modify/test responsibility
- small checkbox execution steps suitable for subagent-driven implementation
- TDD-first sequencing where practical
- concrete verification commands with expected outcomes
- commit checkpoints described in-plan, but actual git commits remain operator-controlled

For `ModularSimulator-szt.4`, this format applies to scaffold metadata, explicit block conditions, and post-landing authoring or unblock steps only; it should not contain executable implementation tasks until `szt.2` is landed and file paths are revalidated.

## Plan 1: `ModularSimulator-szt.3` Design

### Objective

Turn recycle-loop validation into a deterministic compile-time failure whenever a directed recycle loop lacks a supported line-installed pump boost with a positive initial boost value.

### Expected Work Areas

- `src/modular_simulation/flowsheet/flowsheet.py`
  - extend compile validation orchestration
  - replace cycle warning behavior with deterministic recycle validation
  - replace single-cycle `_find_directed_cycle` behavior with all-cycle enumeration and inspect directed loops against line-installed pump metadata
- `src/modular_simulation/connection/domain/error_catalog.py`
  - align validation diagnostics with existing deterministic error payload conventions if needed
- `src/modular_simulation/validation/exceptions.py`
  - only if a dedicated domain exception materially improves clarity
- OpenSpec alignment artifacts under `openspec/changes/reject-invalid-recycle-loops/`
  - align proposal/design language with canonical line-owned pump semantics
  - preserve the explicit dependency on `canonicalize-hydraulic-junction-api`
  - update curated example specs to describe recycle pressure boost as line-installed pump behavior while deferring code rewrites until the sibling API is available
- `tests/unit_process/test_flowsheet_validation.py`
  - convert current cycle-warning expectations into failure expectations
  - add valid/invalid/mixed-loop coverage

### Deterministic Validation Contract

- The failure shape should be a diagnostic-bearing `ValueError`, reusing `src/modular_simulation/connection/domain/error_catalog.py` helpers so tests can assert stable payload fields.
- The validation error must include:
  - an error code or equivalent stable identifier if diagnostic payloads are used
  - the offending ordered loop path text
  - a statement that no supported positive line-installed pressure boost was found on that loop
  - an actionable hint telling the user to add a pump or pressure-boosting stage on the recycle path
- Mixed or multiple invalid loops must be reported deterministically using a stable sort order over loop-path text.
- The implementation may cap the number of reported invalid loops only if the cap is deterministic and still preserves the information needed for user action.
- The plan should explicitly direct the execution agent to write assertions against stable message or payload fields rather than brittle incidental formatting.

### Execution Gate

The executable `szt.3` plan must include explicit execution preconditions showing that `ModularSimulator-szt.2` is no longer in progress and its landed branch surface is available before code tasks begin. The plan must keep ownership limited to compile-time validation logic, validation-focused tests, temporary branch-green placeholder smoke coverage if the canonical ammonia example is not yet rewritten, and OpenSpec language alignment for this change. Any curated example code rewrite, public documentation rewrite, or final smoke-test alignment that depends on `canonicalize-hydraulic-junction-api` belongs to `ModularSimulator-szt.4`, not this plan.

## Plan 2: `ModularSimulator-szt.4` Design

### Objective

After `szt.2` and `szt.3` land, finalize the canonical example set, align public guidance with the new junction/line-owned hydraulic API, and run the end-to-end regression sweep that proves the hydraulic canonicalization sequence is coherent as a user-facing whole.

This artifact should be authored now as a clearly blocked post-landing Superpowers scaffold rather than a fully executable implementation plan, because the exact landed `szt.2` public surface may still shift.

### Expected Work Areas

- curated examples under `examples/unit_process_flowsheet/`
  - especially `complex_6_ammonia_recycle_loop.py`
  - plus any example still showing removed wrapper units or stale terminal patterns
- example and discoverability docs
  - `docs/examples_catalog.md`
  - `docs/README.md`
  - `docs/discoverability_ownership_policy.md` if canonical public-surface wording needs refresh
- public API/export and migration surfaces
  - `src/modular_simulation/unit_processes/__init__.py`
  - any persistence/import compatibility points still referencing removed wrapper-unit names
- regression and integration suites
  - `tests/integration/test_examples_smoke.py`
  - `tests/test_rework_examples_review_alignment.py`
  - connection and flowsheet tests covering junction runtime, wrapper removal, and line-installed controls

### Execution Gate

This plan should be explicitly marked as blocked until:

1. `ModularSimulator-szt.2` has landed on the execution branch
2. `ModularSimulator-szt.3` validation behavior is present

The plan should assume it is the final public-surface cleanup and regression pass for the epic, not a parallel implementation stream.
Before writing step-level execution tasks, the plan author should re-verify the expected file list against the actual landed `szt.2` diff and adjust touched paths if the public API landed in different modules.

### Migration Compatibility Expectations

- This plan owns canonical example rewrites, public documentation refresh, and final smoke/integration alignment after `szt.2` and `szt.3` land.
- This plan also owns final wrapper-unit migration behavior decisions for canonical/public surfaces, including whether stale deleted-wrapper class imports hard-fail, provide actionable migration messages, or preserve limited compatibility shims.
- The blocked scaffold should require the eventual execution agent to make these behaviors explicit in tests before implementation edits proceed.

## Shared Constraints

- Another session is already implementing `ModularSimulator-szt.2`; these plans must not assume unresolved API details.
- `szt.3` should treat line-installed pump semantics as canonical and must not reintroduce pump-unit ownership semantics.
- `szt.4` should remove or reject stale wrapper-unit usage in canonical paths, while keeping migration guidance actionable.
- Future execution agents should be able to follow each plan independently with minimal repo context.

## Plan Boundary Matrix

### `ModularSimulator-szt.3` owns

- compile-time recycle validation logic
- deterministic validation diagnostics contract
- validation-focused unit and regression tests
- temporary placeholder or stub smoke coverage needed to keep the branch green until `szt.4` rewrites the canonical recycle example
- OpenSpec proposal/design/spec language alignment for recycle validation

### `ModularSimulator-szt.3` does not own

- curated example code rewrites
- public docs/catalog refresh
- final smoke-test alignment for canonical examples
- wrapper-unit migration cleanup on the public API surface

### `ModularSimulator-szt.4` owns

- curated example rewrites after the sibling API lands
- public docs and examples-catalog refresh
- canonical public-surface cleanup and wrapper-unit migration behavior
- final smoke, integration, and regression alignment across the epic

## Testing And Verification Philosophy

- Prefer targeted pytest commands for each task before broader sweeps.
- Require deterministic diagnostics for recycle validation failures.
- End the `szt.4` plan with a broader regression pass that spans flowsheet validation, connection/junction behavior, curated example smoke tests, and any example-review alignment checks tied to the new canonical API.

## Deliverables

Produce exactly two plan files:

- `docs/superpowers/plans/2026-03-17-reject-invalid-recycle-loops.md`
- `docs/superpowers/plans/2026-03-17-finalize-curated-examples-and-regressions.md`

Each plan should be handoff-ready for a low-context Superpowers execution agent.
