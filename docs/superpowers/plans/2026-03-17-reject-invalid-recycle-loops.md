# Reject Invalid Recycle Loops Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reject compile-time-detectable recycle loops that lack supported positive line-installed pump boost, with deterministic and actionable validation diagnostics.

**Architecture:** Extend high-level `Flowsheet` compile validation so recycle-loop checks run during compile configuration validation, enumerate directed loops deterministically, and fail on any invalid loop. Keep this plan limited to validation logic, validation-focused tests, and OpenSpec alignment artifacts; curated example rewrites and final smoke/doc alignment belong to the later `ModularSimulator-szt.4` scaffold.

**Tech Stack:** Python, pytest, ModularSimulator flowsheet API, diagnostic payload helpers, OpenSpec change artifacts

---

## Execution Preconditions

- Do not begin code changes until bead dependency `ModularSimulator-szt.2` is no longer in progress on the execution branch.
- Verify bead state before starting:
  - `bd show ModularSimulator-szt.2 --json`
  - `bd show ModularSimulator-szt.3 --json`
- Expected precondition: `ModularSimulator-szt.2` is landed/closed or otherwise explicitly available on the branch where this plan is executed.

## File Structure

- **Modify:** `src/modular_simulation/flowsheet/flowsheet.py` — compile-time topology validation, directed-loop enumeration, and recycle failure behavior
- **Modify:** `src/modular_simulation/connection/domain/error_catalog.py` — add or reuse deterministic diagnostic error codes/helpers for recycle validation
- **Maybe modify:** `src/modular_simulation/validation/exceptions.py` — only if a dedicated exception materially improves clarity without widening scope
- **Modify:** `tests/unit_process/test_flowsheet_validation.py` — validation regression coverage for invalid/valid/mixed recycle loops
- **Modify:** `tests/integration/test_examples_smoke.py` — temporary placeholder or stub coverage to keep the branch green until `ModularSimulator-szt.4` rewrites the canonical recycle example
- **Reference:** `tests/connection/test_graph_compile_validation.py` — deterministic diagnostic assertion patterns
- **Modify:** `openspec/changes/reject-invalid-recycle-loops/design.md` — keep design language aligned with canonical line-owned semantics if implementation details require minor wording updates
- **Modify:** `openspec/changes/reject-invalid-recycle-loops/specs/recycle-loop-validation/spec.md` — keep requirement wording aligned only if implementation clarifies deterministic reporting details
- **Modify:** `openspec/changes/reject-invalid-recycle-loops/specs/curated-flowsheet-examples/spec.md` — preserve deferred example-rewrite language while aligning recycle validation wording if needed

## Deterministic Validation Contract

- Preferred failure shape: diagnostic-bearing `ValueError` using `src/modular_simulation/connection/domain/error_catalog.py` helpers.
- Tests should assert stable diagnostic payload fields via `extract_diagnostic_payload(...)` where possible.
- For the supported flowsheet-topology scale in this change, report all invalid loop paths in normalized sorted order rather than an arbitrary subset.
- Failure must include stable user-action information:
  - offending ordered loop path text
  - statement that no supported positive line-installed pressure boost was found on that loop
  - actionable hint to add a pump or pressure-boosting stage on the recycle path
- Mixed or multiple invalid loops must be reported deterministically using a stable sort over normalized loop-path text.
- Re-compiling the same invalid topology twice must produce identical payload content and loop-path ordering.
- If loop normalization is implemented via canonical rotation, tests should prove the same loop is not reported multiple times under different start-node rotations.
- This plan does **not** rewrite curated example code or final smoke expectations; those belong to `ModularSimulator-szt.4`.
- This plan **does** own any minimal placeholder or stub smoke adjustment required to prevent a temporary red branch after recycle validation starts failing the pre-migration ammonia example.

### Task 1: Lock failing validation behavior in tests

**Files:**
- Modify: `tests/unit_process/test_flowsheet_validation.py`
- Reference: `tests/unit_process/test_flowsheet_builder.py`
- Reference: `tests/connection/test_error_catalog.py`

- [ ] **Step 1: Replace the old warning expectation with a failing recycle validation test**

```python
def test_cycle_without_positive_pump_boost_fails_compile() -> None:
    context = SimulationRuntimeContext.create(species_names=["water", "ethanol"])
    flowsheet = Flowsheet(context=context)
    flowsheet.add_unit("heater_a", HeaterCooler(n_species=2))
    flowsheet.add_unit("heater_b", HeaterCooler(n_species=2))
    flowsheet.add_feed_from_values("feed", T=300.0, P=101325.0, z=(0.5, 0.5), flow=1.0)
    flowsheet.connect("feed", "heater_a")
    flowsheet.connect("heater_a", "heater_b")
    flowsheet.connect("heater_b", "heater_a")

    with pytest.raises(ValueError, match="positive line-installed pressure boost"):
        _ = flowsheet.compile()
```

- [ ] **Step 2: Add a zero-boost regression test**

```python
def test_cycle_with_zero_pump_boost_still_fails_compile() -> None:
    ...
    flowsheet.connect(
        "heater_b",
        "heater_a",
        pump=PumpInstall(initial_pump_speed=0.0),
    )
    with pytest.raises(ValueError, match="positive line-installed pressure boost"):
        _ = flowsheet.compile()
```

- [ ] **Step 3: Add a valid positive-boost regression test**

```python
def test_cycle_with_positive_pump_boost_compiles() -> None:
    ...
    flowsheet.connect(
        "heater_b",
        "heater_a",
        pump=PumpInstall(initial_pump_speed=120000.0),
    )
    _ = flowsheet.compile()
```

- [ ] **Step 4: Add a mixed-validity deterministic regression test**

```python
def test_multiple_invalid_cycles_report_identical_payloads_across_runs() -> None:
    ...
    payloads: list[dict[str, object]] = []
    for _ in range(2):
        with pytest.raises(ValueError) as error:
            _ = flowsheet.compile()
        payload = extract_diagnostic_payload(error.value)
        assert payload is not None
        payloads.append(payload)

    assert payloads[0] == payloads[1]
    assert payloads[0]["code"] == "INVALID_RECYCLE_LOOP"
    assert payloads[0]["path"] == "Flowsheet.compile"
    assert str(payloads[0]["hint"]).startswith("Add a pump")
    message = str(payloads[0]["message"])
    first_loop = "heater_a -> heater_b -> heater_a"
    second_loop = "heater_c -> heater_d -> heater_c"
    assert first_loop in message
    assert second_loop in message
    assert message.index(first_loop) < message.index(second_loop)
```

- [ ] **Step 5: Add a duplicate-cycle-normalization regression test**

```python
def test_cycle_normalization_does_not_report_rotations_as_distinct_loops() -> None:
    ...
    with pytest.raises(ValueError) as error:
        _ = flowsheet.compile()
    payload = extract_diagnostic_payload(error.value)
    assert payload is not None
    message = str(payload["message"])
    assert message.count("heater_a -> heater_b -> heater_c -> heater_a") == 1
```

- [ ] **Step 6: Preserve non-cyclic behavior with a no-new-failures test**

```python
def test_non_cyclic_topology_still_compiles_without_recycle_validation_failure() -> None:
    ...
```

- [ ] **Step 7: Run the focused validation suite and confirm the new tests fail first**

Run: `uv run python -m pytest -q tests/unit_process/test_flowsheet_validation.py`
Expected: FAIL on the new recycle validation assertions because compile still warns instead of failing

- [ ] **Step 8: Commit checkpoint**

```bash
git add tests/unit_process/test_flowsheet_validation.py
git commit -m "test: lock recycle validation failures"
```

### Task 2: Implement deterministic recycle-loop validation in `Flowsheet`

**Files:**
- Modify: `src/modular_simulation/flowsheet/flowsheet.py`
- Modify: `src/modular_simulation/connection/domain/error_catalog.py`
- Maybe modify: `src/modular_simulation/validation/exceptions.py`

- [ ] **Step 1: Introduce a stable recycle-validation entry point in compile validation**

Add a dedicated helper called from compile validation orchestration so recycle checks are no longer warning-only side effects.

- [ ] **Step 2: Replace single-cycle detection with deterministic all-cycle enumeration**

Implement a helper that normalizes loop paths into a stable comparable representation and returns all directed cycles needed for validation.

- [ ] **Step 3: Inspect each cycle for supported positive line-installed pump boost**

Use resolved connection metadata so a loop is valid only when at least one loop edge has supported pump metadata with `initial_pump_speed > 0.0`.

- [ ] **Step 4: Raise deterministic actionable errors on any invalid loop**

Prefer diagnostic-bearing `ValueError` with stable fields:

```python
raise diagnostic_value_error(
    code="INVALID_RECYCLE_LOOP",
    message="recycle loop '<ordered path>' has no supported positive line-installed pressure boost",
    path="Flowsheet.compile",
    hint="Add a pump or pressure-boosting stage on the recycle path.",
)
```

- [ ] **Step 5: Canonicalize loop reporting and cover edge cases the implementation could mishandle**

Ensure the helper normalizes duplicate cycles under rotation, behaves deterministically for overlapping cycles, ignores pump metadata on non-cycle edges, and treats non-positive boost values as invalid.

- [ ] **Step 6: Keep disconnected-topology and dangling-outlet warnings unchanged**

Do not regress existing warning behavior unrelated to recycle validation.

- [ ] **Step 7: Run the focused validation suite and confirm the new tests pass**

Run: `uv run python -m pytest -q tests/unit_process/test_flowsheet_validation.py`
Expected: PASS

- [ ] **Step 8: Run an additional deterministic-pattern check**

Run: `uv run python -m pytest -q tests/connection/test_graph_compile_validation.py`
Expected: PASS

- [ ] **Step 9: Commit checkpoint**

```bash
git add src/modular_simulation/flowsheet/flowsheet.py src/modular_simulation/connection/domain/error_catalog.py src/modular_simulation/validation/exceptions.py tests/unit_process/test_flowsheet_validation.py
git commit -m "feat: reject invalid recycle loops at compile time"
```

### Task 3: Add placeholder smoke coverage so `szt.3` can land without breaking the branch

**Files:**
- Modify: `tests/integration/test_examples_smoke.py`
- Reference: `examples/unit_process_flowsheet/complex_6_ammonia_recycle_loop.py`

- [ ] **Step 1: Write a temporary smoke expectation that reflects the pre-migration ammonia example state**

The placeholder should verify that the curated ammonia example is still tracked, but should not require the pre-`szt.4` example code to pass recycle validation if the example still lacks the post-`szt.2` line-installed pump rewrite.

- [ ] **Step 2: Make the placeholder expectation explicit and actionable**

Example direction:

```python
def test_curated_ammonia_recycle_example_requires_post_api_rewrite() -> None:
    with pytest.raises(ValueError, match="positive line-installed pressure boost"):
        _ = build_ammonia_loop_flowsheet(dt=0.2).compile()
```

or another equally explicit stub that keeps the branch green while pointing follow-up work to `ModularSimulator-szt.4`.

- [ ] **Step 3: Run the smoke suite subset and confirm the branch stays green**

Run: `uv run python -m pytest -q tests/integration/test_examples_smoke.py -k "ammonia or heater or dual_feed"`
Expected: PASS

- [ ] **Step 4: Commit checkpoint**

```bash
git add tests/integration/test_examples_smoke.py
git commit -m "test: keep recycle example smoke green pending api rewrite"
```

### Task 4: Align OpenSpec artifacts with implemented semantics

**Files:**
- Modify: `openspec/changes/reject-invalid-recycle-loops/design.md`
- Modify: `openspec/changes/reject-invalid-recycle-loops/specs/recycle-loop-validation/spec.md`
- Modify: `openspec/changes/reject-invalid-recycle-loops/specs/curated-flowsheet-examples/spec.md`

- [ ] **Step 1: Review the implemented deterministic error contract against the current OpenSpec wording**

Confirm the spec language matches the chosen failure shape, deterministic ordering rule, and deferred example-rewrite boundary.

- [ ] **Step 2: Update spec wording only where implementation clarified behavior**

Keep changes minimal and aligned with the canonical line-owned pump model.

- [ ] **Step 3: Re-read the modified OpenSpec artifacts for consistency with `canonicalize-hydraulic-junction-api` dependency language**

Ensure the docs still say example code rewrites wait for the sibling public API.

- [ ] **Step 4: Run the focused validation suite again after doc/spec edits**

Run: `uv run python -m pytest -q tests/unit_process/test_flowsheet_validation.py`
Expected: PASS

- [ ] **Step 5: Commit checkpoint**

```bash
git add openspec/changes/reject-invalid-recycle-loops/design.md openspec/changes/reject-invalid-recycle-loops/specs/recycle-loop-validation/spec.md openspec/changes/reject-invalid-recycle-loops/specs/curated-flowsheet-examples/spec.md
git commit -m "docs: align recycle validation spec with implementation"
```

### Task 5: Final verification and handoff

**Files:**
- Modify: `tests/unit_process/test_flowsheet_validation.py` (only if final assertion cleanup is needed)
- Modify: `src/modular_simulation/flowsheet/flowsheet.py` (only if verification exposes an issue)

- [ ] **Step 1: Run the combined targeted verification pass**

Run: `uv run python -m pytest -q tests/unit_process/test_flowsheet_validation.py tests/connection/test_graph_compile_validation.py`
Expected: PASS

- [ ] **Step 2: Optionally run a broader flowsheet smoke subset if the recycle tests touch compile wiring broadly**

Run: `uv run python -m pytest -q tests/unit_process/test_flowsheet_builder.py`
Expected: PASS

- [ ] **Step 3: Run the ammonia smoke placeholder coverage**

Run: `uv run python -m pytest -q tests/integration/test_examples_smoke.py -k "ammonia"`
Expected: PASS

- [ ] **Step 4: Confirm no curated example rewrite work slipped into this task**

Check that ammonia example code, public docs, and final smoke alignment remain reserved for `ModularSimulator-szt.4`.

- [ ] **Step 5: Commit final polish if needed**

```bash
git add src/modular_simulation/flowsheet/flowsheet.py src/modular_simulation/connection/domain/error_catalog.py tests/unit_process/test_flowsheet_validation.py openspec/changes/reject-invalid-recycle-loops/
git commit -m "chore: finalize recycle validation coverage"
```
