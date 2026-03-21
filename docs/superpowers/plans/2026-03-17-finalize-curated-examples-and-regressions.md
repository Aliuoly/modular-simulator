# Finalize Curated Examples And End-To-End Regressions Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Finalize the curated flowsheet examples, public catalog/docs wording, wrapper-unit migration hard-fail behavior, and the last targeted regression sweep against the already-landed hydraulic API.

**Architecture:** Treat `ModularSimulator-szt.2` and `ModularSimulator-szt.3` as landed prerequisites and keep this work limited to reconciliation and polish on the current public surface. Prefer tightening the existing curated examples, docs, and regression assertions over adding new surfaces. Preserve the current migration direction: removed wrapper units must hard-fail with actionable import or load-time errors rather than compatibility shims.

**Tech Stack:** Python, pytest, Markdown docs, ModularSimulator `Flowsheet` API, public API exports

---

## Unblock Record

- `ModularSimulator-szt.2` landed in commit `2a150aa8ac66bb44c4b415e87a41dbdd8a94bd3f` (`canonicalize-hydraulic-junction-api spec implementation`).
- `ModularSimulator-szt.3` landed in commit `a18fffc6abe86863728758a138460c9ee1bf2aec` (`reject invalid recycle loops at compile time`).
- Current main-branch merge commit observed while rewriting this plan: `d90e1df3834c558f896099375434d4ef2465ec18`.
- Current repo state already contains the canonical API on the primary implementation surface: curated examples, `docs/README.md`, `docs/examples_catalog.md`, regression coverage, and `src/modular_simulation/unit_processes/__init__.py`.
- Existing artifacts under `openspec/` are reference-only background; this plan should follow the landed repo state, not reopen requirement decisions from OpenSpec.

## Scope Boundaries

This plan owns:

- curated flowsheet examples in `examples/unit_process_flowsheet/`
- public example guidance in `docs/README.md` and `docs/examples_catalog.md`
- hard-fail migration guidance for removed wrapper-unit imports and saved payloads
- final smoke/alignment/junction/recycle regression confirmation for the landed API

This plan does **not** own:

- new hydraulic API design work
- compatibility shims for removed deleted-wrapper unit classes (topology wrappers and flow-control wrappers)
- unrelated example cleanup outside the curated flowsheet and regression surface listed below

## File Structure

- **Modify:** `examples/unit_process_flowsheet/easy_2_heater_flash.py` — smallest canonical flowsheet example wording and runtime behavior
- **Modify:** `examples/unit_process_flowsheet/easy_3_dual_feed_heat_exchanger.py` — canonical multi-feed example wording and runtime behavior
- **Modify:** `examples/unit_process_flowsheet/complex_6_ammonia_recycle_loop.py` — canonical recycle example topology, reporting, and line-installed pump usage
- **Modify:** `docs/README.md` — user-facing canonical example guidance and migration wording
- **Modify:** `docs/examples_catalog.md` — curated inventory, classification, and migration map
- **Maybe modify:** `docs/discoverability_ownership_policy.md` — only if public-surface wording references the pre-migration wrapper path
- **Modify:** `src/modular_simulation/unit_processes/__init__.py` — actionable hard-fail import guidance for removed wrapper units
- **Modify:** `src/modular_simulation/unit_processes/flow/__init__.py` — actionable hard-fail import guidance for removed flow-wrapper units
- **Modify:** `src/modular_simulation/unit_processes/mixing/__init__.py` — actionable hard-fail import guidance for removed mixing-wrapper units
- **Modify:** `src/modular_simulation/unit_processes/separation/__init__.py` — actionable hard-fail import guidance for removed separation-wrapper units
- **Modify:** `tests/integration/test_examples_smoke.py` — smoke coverage for the curated example set
- **Modify:** `tests/test_rework_examples_review_alignment.py` — doc/example alignment and reference-only inventory coverage
- **Modify:** `tests/unit_process/test_canonical_wrapper_removal.py` — removed-wrapper export and import guidance assertions
- **Modify:** `tests/test_save_load_minimal.py` — saved wrapper payload rejection coverage
- **Modify:** `tests/unit_process/test_flowsheet_builder.py` — junction/sink/line-install builder expectations
- **Modify:** `tests/unit_process/test_flowsheet_integration.py` — flowsheet-level runtime expectations for the landed public API
- **Reference:** `tests/unit_process/test_flowsheet_validation.py` — compile-time recycle rejection contract already landed in `szt.3`
- **Reference:** `tests/connection/test_junction_runtime.py` — junction runtime regression surface
- **Reference:** `tests/connection/test_junction_mixing.py` — junction mixing regression surface
- **Reference:** `tests/connection/test_migration_hygiene_gate.py` — no-fallback/no-legacy-surface hygiene gate

## Implementation Rules

- Do not add compatibility shims for removed wrapper units.
- If any deleted flow-control or topology wrapper class names are still mentioned on canonical public surfaces, replace them with actionable migration guidance that points to `Flowsheet.connect(..., pump=PumpInstall(...), valve=ValveInstall(...), heat=HeatInstall(...))`, `Flowsheet.add_junction(...)`, and `Flowsheet.add_sink(...)`.
- Keep the canonical example set limited to the already-curated files; do not promote new examples in this change.
- If a listed file already matches the landed API and tests, leave it unchanged and record that verification in the implementation notes rather than expanding scope.

### Task 1: Reconcile the implementation surface against landed branch state

**Files:**
- Review: `docs/superpowers/plans/2026-03-17-finalize-curated-examples-and-regressions.md`
- Review: `examples/unit_process_flowsheet/easy_2_heater_flash.py`
- Review: `examples/unit_process_flowsheet/easy_3_dual_feed_heat_exchanger.py`
- Review: `examples/unit_process_flowsheet/complex_6_ammonia_recycle_loop.py`
- Review: `docs/README.md`
- Review: `docs/examples_catalog.md`
- Review: `src/modular_simulation/unit_processes/__init__.py`
- Review: `tests/integration/test_examples_smoke.py`
- Review: `tests/test_rework_examples_review_alignment.py`

- [ ] **Step 1: Confirm the bead state still matches this landed plan**

Run: `bd show ModularSimulator-szt.4 --json`
Expected: `ModularSimulator-szt.4` is still the active task and its blockers `ModularSimulator-szt.2` and `ModularSimulator-szt.3` remain closed.

- [ ] **Step 2: Confirm the landed prerequisite commits are still on the execution branch**

Run: `git merge-base --is-ancestor "2a150aa8ac66bb44c4b415e87a41dbdd8a94bd3f" HEAD && git merge-base --is-ancestor "a18fffc6abe86863728758a138460c9ee1bf2aec" HEAD`
Expected: exit code `0` with no output.

- [ ] **Step 3: Re-read the exact implementation surface and reduce the change list to real drift only**

Compare the current examples, docs, and regression files listed above. Keep edits only where the landed repo still has wording drift, missing assertions, or inconsistent migration guidance.

- [ ] **Step 4: Do not start broader cleanup**

If review uncovers unrelated issues outside the files listed in this plan, leave them for separate bead work instead of expanding this task.

### Task 2: Finalize curated examples and public docs around the landed API

**Files:**
- Modify: `examples/unit_process_flowsheet/easy_2_heater_flash.py`
- Modify: `examples/unit_process_flowsheet/easy_3_dual_feed_heat_exchanger.py`
- Modify: `examples/unit_process_flowsheet/complex_6_ammonia_recycle_loop.py`
- Modify: `docs/README.md`
- Modify: `docs/examples_catalog.md`
- Maybe modify: `docs/discoverability_ownership_policy.md`
- Modify: `tests/integration/test_examples_smoke.py`
- Modify: `tests/test_rework_examples_review_alignment.py`

- [ ] **Step 1: Verify each curated example still demonstrates the canonical API directly**

Keep `easy_2_heater_flash.py`, `easy_3_dual_feed_heat_exchanger.py`, and `complex_6_ammonia_recycle_loop.py` centered on explicit feeds, explicit sinks, explicit junctions where needed, and line-installed controls rather than wrapper units.

- [ ] **Step 2: Tighten any example docstrings, report text, or helper naming that still reflects transition-period migration wording**

Prefer small wording fixes over structural rewrites. The examples should read like the final canonical path, not like temporary migration placeholders.

- [ ] **Step 3: Reconcile `docs/README.md` and `docs/examples_catalog.md` with the final curated set**

Ensure both docs agree on:

- which examples are canonical
- why `complex_6_ammonia_recycle_loop.py` remains the advanced canonical flowsheet
- which examples are reference-only or removed from the primary path
- the migration map away from pre-curation entrypoints

- [ ] **Step 4: Keep discoverability wording aligned only if the policy doc still points readers to removed wrapper-unit workflows**

Do not edit `docs/discoverability_ownership_policy.md` unless the current text directly conflicts with the landed user-facing migration story.

- [ ] **Step 5: Update smoke and alignment tests to lock the final curated/example-doc contract**

Use `tests/integration/test_examples_smoke.py` and `tests/test_rework_examples_review_alignment.py` to assert the final curated examples run, docs use `boundary sinks` wording, and reference-only examples remain out of the canonical path.

- [ ] **Step 6: Run the curated example/doc verification subset**

Run: `uv run python -m pytest -q tests/integration/test_examples_smoke.py::test_curated_heater_flash_example_smoke tests/integration/test_examples_smoke.py::test_curated_dual_feed_exchanger_example_smoke tests/integration/test_examples_smoke.py::test_curated_ammonia_recycle_example_smoke tests/test_rework_examples_review_alignment.py::test_curated_docs_describe_terminal_unit_outlets tests/test_rework_examples_review_alignment.py::test_complex_8_pressure_flash_recovery_example_runs_and_returns_report tests/test_rework_examples_review_alignment.py::test_reference_examples_use_junctions_sinks_and_line_installs_instead_of_wrapper_units`
Expected: PASS; all selected curated example and doc-alignment regressions succeed.

### Task 3: Preserve hard-fail wrapper migration behavior with actionable guidance

**Files:**
- Modify: `src/modular_simulation/unit_processes/__init__.py`
- Modify: `src/modular_simulation/unit_processes/flow/__init__.py`
- Modify: `src/modular_simulation/unit_processes/mixing/__init__.py`
- Modify: `src/modular_simulation/unit_processes/separation/__init__.py`
- Modify: `tests/unit_process/test_canonical_wrapper_removal.py`
- Modify: `tests/test_save_load_minimal.py`
- Modify: `tests/unit_process/test_flowsheet_builder.py`
- Modify: `tests/unit_process/test_flowsheet_integration.py`

- [ ] **Step 1: Re-verify the removed-wrapper import contract in `src/modular_simulation/unit_processes/__init__.py`**

Removed wrapper symbols must not be importable or accessible. Do not add aliases, compatibility exports, or delayed runtime shims.

- [ ] **Step 2: Reconcile migration tests with the desired failure behavior**

`tests/unit_process/test_canonical_wrapper_removal.py` and `tests/test_save_load_minimal.py` should cover both public import failures and saved-payload rejection for the deleted wrapper model classes (the four removed topology-wrapper and flow-control-wrapper unit types).

Saved-payload rejection must be a hard failure. Live rejection paths may fail generically for removed or unsupported legacy process-model payloads; live source must not carry wrapper-name dispatch tables or wrapper-specific migration strings.

- [ ] **Step 3: Reconcile builder/runtime contract tests with the same migration direction**

Use `tests/unit_process/test_flowsheet_builder.py` and `tests/unit_process/test_flowsheet_integration.py` to preserve the public replacement path: explicit `add_junction(...)`, `add_sink(...)`, and line-owned `PumpInstall` / `ValveInstall` controls.

- [ ] **Step 4: Run the migration-behavior verification subset**

Run: `uv run python -m pytest -q tests/unit_process/test_canonical_wrapper_removal.py tests/test_save_load_minimal.py::test_process_model_load_rejects_removed_wrapper_unit_payloads tests/unit_process/test_flowsheet_builder.py::test_junction_sink_and_line_reference_compile_to_explicit_topology tests/unit_process/test_flowsheet_builder.py::test_endpoint_validation_and_overlay_rules_are_actionable tests/unit_process/test_flowsheet_integration.py::test_cascade_reference_to_line_owned_pump_actuator_updates_namespaced_command_point`
Expected: PASS; removed wrapper imports and saved payloads fail cleanly, while the replacement flowsheet surface continues to pass.

### Task 4: Run the final targeted regression sweep and sign off

**Files:**
- Reference: `tests/integration/test_examples_smoke.py`
- Reference: `tests/test_rework_examples_review_alignment.py`
- Reference: `tests/unit_process/test_canonical_wrapper_removal.py`
- Reference: `tests/test_save_load_minimal.py`
- Reference: `tests/unit_process/test_flowsheet_builder.py`
- Reference: `tests/unit_process/test_flowsheet_integration.py`
- Reference: `tests/unit_process/test_flowsheet_validation.py`
- Reference: `tests/connection/test_junction_runtime.py`
- Reference: `tests/connection/test_junction_mixing.py`
- Reference: `tests/connection/test_migration_hygiene_gate.py`

- [ ] **Step 1: Run the recycle and junction regression subset first**

Run: `uv run python -m pytest -q tests/unit_process/test_flowsheet_validation.py::TestRecycleLoopRejection tests/connection/test_junction_runtime.py tests/connection/test_junction_mixing.py`
Expected: PASS; compile-time recycle rejection and junction runtime/mixing behavior remain stable.

- [ ] **Step 2: Run the end-to-end targeted signoff suite**

Run: `uv run python -m pytest -q tests/integration/test_examples_smoke.py::test_curated_heater_flash_example_smoke tests/integration/test_examples_smoke.py::test_curated_dual_feed_exchanger_example_smoke tests/integration/test_examples_smoke.py::test_curated_ammonia_recycle_example_smoke tests/test_rework_examples_review_alignment.py::test_curated_docs_describe_terminal_unit_outlets tests/test_rework_examples_review_alignment.py::test_complex_5_wording_matches_reference_only_catalog_status tests/test_rework_examples_review_alignment.py::test_complex_8_pressure_flash_recovery_example_runs_and_returns_report tests/test_rework_examples_review_alignment.py::test_reference_examples_use_junctions_sinks_and_line_installs_instead_of_wrapper_units tests/unit_process/test_canonical_wrapper_removal.py tests/test_save_load_minimal.py::test_process_model_load_rejects_removed_wrapper_unit_payloads tests/unit_process/test_flowsheet_builder.py::test_junction_sink_and_line_reference_compile_to_explicit_topology tests/unit_process/test_flowsheet_builder.py::test_endpoint_validation_and_overlay_rules_are_actionable tests/unit_process/test_flowsheet_integration.py::test_cascade_reference_to_line_owned_pump_actuator_updates_namespaced_command_point tests/unit_process/test_flowsheet_validation.py::TestRecycleLoopRejection tests/connection/test_junction_runtime.py tests/connection/test_junction_mixing.py tests/connection/test_migration_hygiene_gate.py`
Expected: PASS; curated examples, targeted doc alignment, wrapper migration behavior, focused flowsheet builder/runtime behavior, recycle validation, junction runtime, and migration hygiene all pass together without depending on unrelated tests in larger files.

- [ ] **Step 3: Re-read the touched files before handoff**

Confirm the final diff stays inside the file list in this plan and that no pre-implementation placeholder wording remains on the curated public path.

- [ ] **Step 4: Close the bead only after the verification evidence is fresh**

Do not mark `ModularSimulator-szt.4` done until the commands in Steps 1 and 2 have been run successfully on the final diff.
