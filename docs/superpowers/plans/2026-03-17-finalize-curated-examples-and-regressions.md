# Finalize Curated Examples And Regressions Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** After `ModularSimulator-szt.2` and `ModularSimulator-szt.3` land, finalize the canonical examples, public guidance, wrapper-unit migration behavior, and end-to-end regressions for the hydraulic canonicalization epic.

**Architecture:** This document is a blocked post-landing scaffold, not a runnable implementation plan yet. It defines the execution gates, candidate files, and the first unblock actions required to convert the scaffold into a fully executable plan once the landed `szt.2` public API surface is available on the branch.

**Tech Stack:** Python, pytest, ModularSimulator flowsheet API, documentation markdown, public API exports, persistence/import compatibility surfaces

---

## Block Conditions

This scaffold MUST NOT be executed as implementation work until all conditions below are true:

1. `ModularSimulator-szt.2` has landed on the execution branch.
2. `ModularSimulator-szt.3` compile-time recycle validation behavior is present on the execution branch.
3. The execution agent has re-verified the actual landed file surface against this scaffold.

## Candidate File Structure To Revalidate Post-Landing

- `examples/unit_process_flowsheet/complex_6_ammonia_recycle_loop.py` — canonical recycle example likely requiring junction/sink and line-installed pump migration
- `examples/unit_process_flowsheet/easy_2_heater_flash.py` — verify canonical example wording and sink conventions
- `examples/unit_process_flowsheet/easy_3_dual_feed_heat_exchanger.py` — verify canonical multi-branch example wording and endpoint conventions
- `tests/integration/test_examples_smoke.py` — final smoke alignment for canonical examples
- `tests/test_rework_examples_review_alignment.py` — example/doc alignment regression coverage
- `tests/unit_process/test_flowsheet_builder.py` — builder/runtime expectations for junction, sink, and line installs
- `tests/unit_process/test_flowsheet_integration.py` — flowsheet-level public API and migration behavior coverage
- `tests/connection/test_junction_runtime.py` — junction runtime regression surface
- `tests/connection/test_junction_mixing.py` — junction mixing regression surface
- `src/modular_simulation/unit_processes/__init__.py` — public export cleanup for removed wrapper units
- `docs/examples_catalog.md` — canonical example inventory and migration map
- `docs/README.md` — public-facing example guidance
- `docs/discoverability_ownership_policy.md` — canonical/public surface ownership wording if needed
- `openspec/changes/canonicalize-hydraulic-junction-api/specs/curated-flowsheet-examples/spec.md` — canonical example requirements
- `openspec/changes/reject-invalid-recycle-loops/specs/curated-flowsheet-examples/spec.md` — recycle example viability requirements

## Required Unblock Task

### Task 1: Reconcile the scaffold against landed `szt.2` and `szt.3`

**Files:**
- Review: landed diff for `ModularSimulator-szt.2`
- Review: landed diff for `ModularSimulator-szt.3`
- Update: this plan file before any implementation plan steps are added

- [ ] **Step 1: Verify both prerequisites are actually landed on the execution branch**

Run: `bd show ModularSimulator-szt.2 --json && bd show ModularSimulator-szt.3 --json && bd show ModularSimulator-szt.4 --json`
Expected: `szt.2` and `szt.3` are no longer in progress/blocking on the execution branch context, and `szt.4` remains the active target for this plan rewrite

- [ ] **Step 2: Diff the landed public API surface against the candidate file list above**

First record the exact landed SHA(s) for `szt.2` and `szt.3` directly in this plan file under a short “Unblock Record” note so the next agent does not have to rediscover them.

Then run a real diff such as:

Run: `git diff --name-only <recorded-pre-szt.2-base>...HEAD`
Expected: a concrete file list showing where junction/sink APIs, line installs, wrapper removals, and related docs/tests actually landed

If the landing happened as merge commits, record the merge SHA and use its first parent as the pre-landing base when constructing the diff range.

- [ ] **Step 3: Update this scaffold into a full executable plan only after reconciling actual paths**

Add exact create/modify/test sections and executable TDD steps based on the landed surface. Do not start code edits before this rewrite is complete.

- [ ] **Step 4: Commit the rewritten executable plan before implementation begins**

```bash
git add docs/superpowers/plans/2026-03-17-finalize-curated-examples-and-regressions.md
git commit -m "docs: unblock curated examples regression plan"
```

## Owned Scope Once Unblocked

When this scaffold is converted into an executable plan, it owns:

- canonical example rewrites after the sibling API lands
- public docs and examples-catalog refresh
- wrapper-unit migration behavior on canonical/public surfaces
- final smoke, integration, and regression alignment across the epic

It does **not** own:

- initial compile-time recycle validation logic from `ModularSimulator-szt.3`
- unresolved API design choices that belong to the still-in-progress `ModularSimulator-szt.2` session

## Migration Compatibility Decisions To Make Explicit In The Final Plan

Before implementation starts, the rewritten executable plan must lock down:

- whether stale `Pump`, `Valve`, `Mixer`, and `Splitter` imports hard-fail or provide actionable migration messages
- whether saved payload/import compatibility is preserved, shimmed, or intentionally rejected
- which canonical examples remain in the primary path after migration
- which regression suites are required for final signoff
- which behaviors were already settled by the landed `szt.2` work and therefore must be preserved/documented rather than re-decided in `szt.4`

## Minimum Verification Expectations For The Final Unblocked Plan

The eventual executable version of this plan should end with a broader regression pass covering at least:

- `uv run python -m pytest -q tests/integration/test_examples_smoke.py`
- `uv run python -m pytest -q tests/test_rework_examples_review_alignment.py`
- a targeted flowsheet/junction regression subset based on the landed `szt.2` surface

The rewritten plan should include exact expected outcomes once the actual landed file paths are known.
