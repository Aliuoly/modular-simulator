# Task 1 Issues and Caveats

## No Critical Issues

Task 1 completed without blockers. Both acceptance commands passed:
- All 12 required unit files enumerated successfully
- All units matched the required set from the plan

## Minor Observations

### Port Shape Diversity
Units exhibit diverse port configurations:
|- 1->1 (SINGLE_IO): 6 units (HeaterCooler, CSTR, ConversionReactor, PFR, Pump, Valve)
|- 1->2: 3 units (FlashDrum, ShortcutDistillation, ComponentSeparator)
|- 2->2: 1 unit (HeatExchanger)
|- 1->N: 1 unit (Splitter - configurable via n_outlets)
|- N->1: 1 unit (Mixer - configurable via n_inlets)

### CSTR Internal Control Law
CSTR's internal level control loop (reactor_volume setpoint + level_control_gain) is embedded in the physics calculation, not exposed as a separate control element. This creates an implicit control surface that may require special consideration in Pass 1 controller-readiness analysis.

### Pass 1 Edge Cases
Mixer is the only unit excluded from Pass 1 because it has no mode selector, setpoint fields, or controller-binding dependency. This is correct behavior - Mixer is a pure passive mixing element with N->1 port topology.

## No Blockers for Subsequent Tasks

Task 1 artifacts are complete and ready to support:
- Task 2: Extract Pass 1 control-contract surfaces per unit
- Task 3: Map controller-readiness against runtime/subsystem contracts
- Task 4: Build unit-specific Pass 1 test coverage matrix

## Task 3 Issues and Caveats

- `System.add_component()` can install late-added control elements without rerunning the constructor-time `controlled_view` validation, so constant-tag actuation surfaces are technically reachable but not first-class controller surfaces.
- `conversion_reactor` and `heat_exchanger` expose only mode/configuration parameters, not a tested runtime actuator path, so they remain conservative `not-ready` classifications until an explicit adapter or new actuator surface exists.
- `splitter` is direct-ready at the contract layer, but any real controller must still match the vector MV dimensionality enforced during activation.

## Task 4 Issues and Caveats

- Generic controller-framework tests in `tests/components/test_controller_wiring_api.py` and `tests/connection/test_subsystem_scoped_installers.py` are easy false positives for Pass 1 coverage because they use generic `thermal_process_model` fixtures rather than concrete unit classes.
- ShortcutDistillation coverage is incomplete for Pass 1 audit purposes because the explicit `reflux_ratio_setpoint` surface is not exercised in the reviewed unit-specific tests or examples.
- PFR remains the clearest Pass 1 coverage gap: existing reviewed tests cover reactor physics/discretization, but not `jacket_temperature`, `heat_transfer_coeff`, or `jacket_area`.
- Mixer still needs a matrix row even though it is out of Pass 1 scope; the evidence needs to document strong exclusion support rather than a missing controller contract.

## Task 2 Issues and Caveats

- Token-count acceptance probe is intentionally lexical (`setpoint`, `mode`) and overcounts in some files due to helper names and validation strings; task artifact uses anchored field-level evidence to avoid false severity signals.
- Several units expose control-like behavior via `T.CONSTANT` tags instead of explicit MV tags (not a blocker for Task 2, but a key caveat for Task 3 readiness scoring).
- `Mixer` has many `T.CONTROLLED` inlet arrays but no dedicated internal actuator/setpoint contract; this remains a boundary case between upstream-feed control and unit-local control semantics.

## Task 5 Issues and Caveats

- Severity must be interpreted as remediation order for control-contract risk, not as physics-model quality ranking.
- `conversion_reactor` remains high-priority despite strong unit coverage because current tests validate behavior, not a safe runtime controller-actuator contract.
- `shortcut_distillation` is intentionally not escalated to high severity: the contract is direct-ready and the current gap is concentrated in missing explicit `reflux_ratio_setpoint` coverage.
- `mixer` is intentionally excluded from Pass 1 severity ranking; exclusion remains evidence-backed and should not be read as missing analysis.

## Task 6 Issues and Caveats

- No critical blockers encountered; all acceptance checks passed on first run.
- Tasks 7 and 8 must strictly follow the deterministic detection rules to avoid scope drift into Pass 1 actuator redesign territory.
- Severity assignment in Pass 2 is independent of Pass 1 severity ranking; cross-linking in Task 9 is for overlap detection only, not revision.
- The taxonomy assumes all 12 units require Pass 2 audit; Mixer is included despite Pass 1 exclusion because naming/validation/edge-case semantics are relevant even for passive units.
- Cosmetic naming differences (e.g., `*_fraction` vs `*_ratio`) should be classified as low severity only if they remain recognizable as the same concept; otherwise they may be medium severity if they obscure intent.

## Task 8 Issues and Caveats

- Baseline plan tests (`cstr`, `pfr`, `distillation`) validate nominal reactor and separation behavior, but most actionable Task 8 findings come from constructor/algebraic edge handling rather than explicit edge-case tests.
- `CSTR` and `PFR` rely on runtime clamping in solver paths, so severity should be tied to controller-facing silent coercion risk rather than to missing physics coverage.
- `Pump` zero-flow inconsistency is an internal algebraic-versus-step semantic split, not a physics-quality complaint; keep it framed as deterministic no-flow contract drift.
- `Mixer` zero-flow composition fallback is arbitrary but currently best treated as benign unless Task 9 needs a stronger portfolio-wide contract for undefined-composition states.

## Task 7 Issues and Caveats

- `splitter.split_ratios` and `component_separator.split_fractions` are similar enough to flag as a portfolio coherence mismatch, but not identical physics contracts; severity stayed `medium` to avoid overstating outlet-wise versus species-wise differences.
- `heater_cooler.mode` versus `thermal_mode` in `flash_drum` and `conversion_reactor` is a naming mismatch for scan determinism, not a claim that the encoded mode values are interchangeable.
- `shortcut_distillation` is used as an explicit `*_setpoint` comparator only; Task 7 does not reopen its Pass 1 readiness or coverage ranking.

## Task 9 Issues and Caveats

- Some findings span multiple taxonomy categories (`validation consistency` and `edge-case semantic consistency`), so each row must preserve category pairing to avoid losing Task 6 alignment.
- Pass 1 overlap density is highest for `pfr`, `conversion_reactor`, `heat_exchanger`, `shortcut_distillation`, `cstr`, `pump`, `component_separator`, and `splitter`; missing cross-links on these units would violate Task 9 de-dup guardrails.
- Benign divergences still require explicit low-severity rows; omitting them would flatten Task 8 classification intent and weaken Task 10 prioritization inputs.

## Task 10 Issues and Caveats

- Task 10 must not flatten the two registers into one severity-only list, because that would hide the user-selected pass boundary and could pull Pass 2 naming work ahead of unresolved Pass 1 contract exposure.
- `HeaterCooler`, `FlashDrum`, and `CSTR` are required acceptance anchors, but the backlog also needs the rest of the top-risk set called out explicitly so Task 11 does not infer omitted units as low relevance.
- Pass 2 benign divergences should stay deferred unless new anchored evidence appears. Promoting them now would violate the verified Task 9 classification and weaken rollback discipline.

## Task 11 Issues and Caveats

- Task 11 failed on the first acceptance command, `uv run python -m ruff check src tests`, so per plan guardrails the remaining acceptance commands were not executed.
- The failure appears to be a pre-existing repo/tooling issue rather than an audit-artifact issue: `ruff` reported unused imports in `src/modular_simulation/cli/backend_session.py` and `tests/unit_process/test_hydraulic_elements.py`.
- Because execution stopped at the first gate, there is no verified Task 11 result yet for `mypy`, the targeted regression bundle, or the artifact-index script.

## Task 11 Rerun Issues and Caveats

- The rerun cleared the original `ruff` blocker but failed on the second acceptance command, `uv run --with mypy python -m mypy src`, so Task 11 still cannot verify the later `pytest` bundle or artifact-index step.
- The recorded `mypy` failures are pre-existing repo/tooling issues outside the audit artifacts: assignment-shape mismatches in `src/modular_simulation/unit_processes/flash_drum.py`, `src/modular_simulation/unit_processes/cstr.py`, `src/modular_simulation/unit_processes/conversion_reactor.py`, and `src/modular_simulation/flowsheet/flowsheet.py`, plus type/attribute errors in `src/modular_simulation/thermodynamics/property_package.py`.
- `src/modular_simulation/framework/system.py:237` emitted only a note, not a blocking error; the actual stop condition was the 7 `mypy` errors in 5 files.

## Task 11 Final Rerun Issues and Caveats

- No blocking issues remain for Task 11 after the final rerun; all acceptance commands now exit 0 in the required order.
- `src/modular_simulation/framework/system.py:237` still emits a `mypy` note about unchecked untyped function bodies, but it is informational only and does not affect Task 11 acceptance.
- Markdown and log files still have no configured LSP server in this environment, so diagnostics cleanliness for the updated evidence and notepad artifacts must be reported as unavailable rather than silently assumed.
