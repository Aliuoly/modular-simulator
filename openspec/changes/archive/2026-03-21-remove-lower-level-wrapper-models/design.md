## Context

The main spec currently enforces wrapper removal only at the canonical high-level surface. That still leaves live lower-level classes, wrapper-specific rejection strings, runtime name defaults, and dedicated lower-level tests that mention the four deleted unit-process wrapper classes by their original names. The user explicitly chose a stronger breaking change: remove those lower-level wrapper models and all live non-archive mentions completely.

The repository already has the replacement topology model in place: explicit junctions, explicit sinks, and line-installed `PumpInstall`, `ValveInstall`, and `HeatInstall` elements. The remaining supported unit-process families (`HeaterCooler`, `HeatExchanger`, `CSTR`, `PFR`, `ConversionReactor`, `FlashDrum`, `ShortcutDistillation`, `ComponentSeparator`) remain the live process-model vocabulary.

## Goals / Non-Goals

**Goals**
- Remove the lower-level wrapper model files and package-level wrapper guidance from the live repository.
- Remove wrapper-name mentions from non-archive docs, tests, serializer/load logic, and runtime default tables.
- Preserve behavior coverage by rewriting tests around supported surfaces, direct hydraulic primitives, or small local synthetic process-model fixtures.
- Update the spec so the stronger full-removal contract is documented in durable OpenSpec artifacts.

**Non-Goals**
- Rework the supported junction-plus-line-install topology model.
- Remove `PumpInstall`, `ValveInstall`, `HeatInstall`, explicit junctions, or explicit sinks.
- Rewrite archived OpenSpec history.
- Absorb unrelated runtime or physics refactors that are not required by wrapper removal.

## Decisions

1. Remove the wrapper-model source files entirely.
   - Delete `src/modular_simulation/unit_processes/flow/pump.py`, `src/modular_simulation/unit_processes/flow/valve.py`, `src/modular_simulation/unit_processes/mixing/mixer.py`, and `src/modular_simulation/unit_processes/separation/splitter.py`.
   - Remove package-level `__getattr__` migration shims that preserve the wrapper model vocabulary in live code.

2. Stop preserving wrapper-specific migration guidance in live source.
   - `ProcessModel.load()` should no longer carry a wrapper-name dispatch table.
   - Live rejection paths may fail generically for removed or unsupported legacy process-model payloads; archive history remains the place that records the old names.

3. Replace wrapper-dependent tests with supported or synthetic coverage.
   - pressure-boost overlay (line-installed pump) behavior checks move to direct hydraulic-element and supported control-surface tests.
   - flow-split and topology-merge (junction) behavior checks are replaced by explicit junction/runtime coverage or removed if they only preserve dead wrapper semantics.
   - Tests that only existed to assert wrapper-removal messages are removed or rewritten to assert supported surfaces without naming the deleted wrappers.

4. Remove wrapper-name defaults from runtime helpers.
   - `default_pipe_resistance_for_unit(...)` and related helper tables must cover only supported live unit names.
   - No live source file should need the wrapper model names as string keys or diagnostics.

5. Scope the first implementation wave to live non-archive repository content.
   - Archived OpenSpec change artifacts may still contain the old wrapper names as historical record.
   - Verification for this change treats only live non-archive files as in-scope.

## Risks / Trade-offs

- Deleting lower-level wrapper files is a harder break than the current state and may invalidate out-of-repo consumers.
  - Mitigation: this is an intentional breaking change, and the spec now documents the stronger contract explicitly.
- Rewriting tests away from wrapper-specific models may reduce some low-level coverage if done carelessly.
  - Mitigation: preserve coverage through direct hydraulic primitives, supported unit families, and explicit junction/runtime tests.
- Generic legacy-payload rejection is less specific than the old wrapper-name messages.
  - Mitigation: the user explicitly prioritized complete removal of live wrapper mentions over preserving tailored migration wording.

## Verification Strategy

- Run targeted regression suites after the rewrite:
  - `uv run pytest tests/connection/test_hydraulic_compile.py tests/connection/test_thermo_coupling_runtime_store.py tests/unit_process/test_flowsheet_validation.py tests/controller_contract_harness.py`
  - `uv run pytest tests/test_rework_examples_review_alignment.py`
- Run repo-wide search verification over live non-archive paths with a Python scanner that fails if the deleted wrapper model names still appear in in-scope docs, source, or tests.
- Run `openspec validate remove-lower-level-wrapper-models --strict` after artifacts and code changes are in place.

Success means the live non-archive repository no longer ships or mentions the removed wrapper model vocabulary, while supported junction-plus-line-install behavior and remaining unit-family behavior still verify cleanly.
